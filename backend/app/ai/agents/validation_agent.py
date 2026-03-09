"""Validation Agent — AI-powered project data validation with tool calling.

This agent can:
1. Check BOQ code compliance against GB50500 standard codes
2. Detect price/consumption anomalies
3. Find similar historical items for comparison
4. Explain validation issues with professional context
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.ai.providers import AIProviderError, get_ai_provider
from app.db.session import get_db
from app.models.boq_item import BoqItem
from app.models.boq_standard_code import BoqStandardCode
from app.models.line_item_quota_binding import LineItemQuotaBinding
from app.models.material_price import MaterialPrice
from app.models.project import Project
from app.models.quota_item import QuotaItem
from app.models.quota_resource_detail import QuotaResourceDetail
from app.services.validation_service import (
    Severity,
    ValidationIssue,
    normalize_unit,
    validate_project,
)

logger = logging.getLogger(__name__)

MAX_AGENT_TURNS = 8


# ════════════════════════════════════════════════════════════════
# Tool definitions
# ════════════════════════════════════════════════════════════════

AGENT_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "check_code_compliance",
            "description": "检查一个清单编码是否符合GB50500标准，返回标准编码信息、计量规则和项目特征模板。",
            "parameters": {
                "type": "object",
                "properties": {
                    "boq_code": {
                        "type": "string",
                        "description": "清单项编码",
                    },
                    "boq_unit": {
                        "type": "string",
                        "description": "清单项单位",
                    },
                },
                "required": ["boq_code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "detect_price_anomaly",
            "description": "检测一个清单项的定额消耗量是否存在异常（与同类项目对比）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "boq_item_id": {
                        "type": "integer",
                        "description": "清单项ID",
                    },
                },
                "required": ["boq_item_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_similar_historical_items",
            "description": "在所有项目中查找与指定清单项相似的历史项（名称/编码/单位匹配），用于参考对比。",
            "parameters": {
                "type": "object",
                "properties": {
                    "name_keyword": {
                        "type": "string",
                        "description": "清单项名称关键词",
                    },
                    "unit": {
                        "type": "string",
                        "description": "单位筛选",
                    },
                    "top_n": {
                        "type": "integer",
                        "description": "返回数量，默认5",
                    },
                },
                "required": ["name_keyword"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_full_validation",
            "description": "对指定项目执行完整的校验引擎，返回所有校验问题。",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {
                        "type": "integer",
                        "description": "项目ID",
                    },
                },
                "required": ["project_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_resource_details",
            "description": "查看某条定额的人材机资源明细。",
            "parameters": {
                "type": "object",
                "properties": {
                    "quota_item_id": {
                        "type": "integer",
                        "description": "定额ID",
                    },
                },
                "required": ["quota_item_id"],
            },
        },
    },
]


# ════════════════════════════════════════════════════════════════
# Step tracking (shared structure with valuation_agent)
# ════════════════════════════════════════════════════════════════

@dataclass
class AgentStep:
    type: str  # "thinking" | "tool_call" | "tool_result" | "answer"
    content: str = ""
    tool_name: str = ""
    tool_args: dict[str, Any] = field(default_factory=dict)
    tool_result: str = ""


@dataclass
class ValidationAgentResult:
    answer: str
    steps: list[AgentStep] = field(default_factory=list)
    issues_found: int = 0
    error: str | None = None


# ════════════════════════════════════════════════════════════════
# Tool implementations
# ════════════════════════════════════════════════════════════════

def _tool_check_code_compliance(
    db: Session, *, boq_code: str, boq_unit: str = ""
) -> str:
    code_prefix = boq_code.split("-")[0].strip()
    match = (
        db.query(BoqStandardCode)
        .filter(BoqStandardCode.standard_code == code_prefix)
        .first()
    )
    if not match and len(code_prefix) >= 9:
        match = (
            db.query(BoqStandardCode)
            .filter(BoqStandardCode.standard_code == code_prefix[:9])
            .first()
        )

    if not match:
        return json.dumps({
            "compliant": None,
            "message": f"编码 {boq_code} 未在GB50500标准库中找到匹配项",
            "suggestion": "可能是非标编码或地方标准编码",
        }, ensure_ascii=False)

    issues = []
    if boq_unit and normalize_unit(boq_unit) != normalize_unit(match.standard_unit):
        issues.append(f"单位 '{boq_unit}' 与标准单位 '{match.standard_unit}' 不一致")

    return json.dumps({
        "compliant": len(issues) == 0,
        "standard_code": match.standard_code,
        "standard_name": match.name,
        "standard_unit": match.standard_unit,
        "division": match.division,
        "measurement_rule": match.measurement_rule,
        "common_characteristics": match.common_characteristics,
        "issues": issues,
    }, ensure_ascii=False)


def _tool_detect_price_anomaly(db: Session, project_id: int, *, boq_item_id: int) -> str:
    boq = db.query(BoqItem).filter(BoqItem.id == boq_item_id).first()
    if not boq:
        return json.dumps({"error": f"清单项 {boq_item_id} 不存在"}, ensure_ascii=False)

    # Get this item's consumption
    bindings = (
        db.query(LineItemQuotaBinding)
        .filter(LineItemQuotaBinding.boq_item_id == boq.id)
        .all()
    )
    if not bindings:
        return json.dumps({
            "boq_code": boq.code,
            "message": "无绑定定额，无法分析消耗量异常",
        }, ensure_ascii=False)

    quota_ids = [b.quota_item_id for b in bindings]
    quotas = {q.id: q for q in db.query(QuotaItem).filter(QuotaItem.id.in_(quota_ids)).all()}

    total_l = total_m = total_mc = 0.0
    for b in bindings:
        q = quotas.get(b.quota_item_id)
        if q:
            coeff = getattr(b, "coefficient", 1.0) or 1.0
            total_l += q.labor_qty * coeff
            total_m += q.material_qty * coeff
            total_mc += q.machine_qty * coeff

    # Find peers in same project with same division + unit
    peers = (
        db.query(BoqItem)
        .filter(
            BoqItem.project_id == boq.project_id,
            BoqItem.division == boq.division,
            BoqItem.id != boq.id,
        )
        .all()
    )
    peer_data = []
    for p in peers:
        if normalize_unit(p.unit) != normalize_unit(boq.unit):
            continue
        p_bindings = (
            db.query(LineItemQuotaBinding)
            .filter(LineItemQuotaBinding.boq_item_id == p.id)
            .all()
        )
        if not p_bindings:
            continue
        p_qids = [pb.quota_item_id for pb in p_bindings]
        p_quotas = {q.id: q for q in db.query(QuotaItem).filter(QuotaItem.id.in_(p_qids)).all()}
        pl = pm = pmc = 0.0
        for pb in p_bindings:
            pq = p_quotas.get(pb.quota_item_id)
            if pq:
                pc = getattr(pb, "coefficient", 1.0) or 1.0
                pl += pq.labor_qty * pc
                pm += pq.material_qty * pc
                pmc += pq.machine_qty * pc
        peer_data.append({"code": p.code, "name": p.name, "labor": pl, "material": pm, "machine": pmc})

    return json.dumps({
        "boq_code": boq.code,
        "boq_name": boq.name,
        "current": {"labor": round(total_l, 4), "material": round(total_m, 4), "machine": round(total_mc, 4)},
        "peer_count": len(peer_data),
        "peers": peer_data[:10],
    }, ensure_ascii=False)


def _tool_find_similar_items(
    db: Session, *, name_keyword: str, unit: str = "", top_n: int = 5
) -> str:
    all_items = db.query(BoqItem).all()
    scored = []
    for item in all_items:
        sim = SequenceMatcher(None, name_keyword, item.name).ratio()
        if unit and normalize_unit(unit) != normalize_unit(item.unit):
            sim *= 0.5
        if sim > 0.2:
            scored.append((sim, item))
    scored.sort(key=lambda x: x[0], reverse=True)

    results = []
    for sim, item in scored[:top_n]:
        bindings = (
            db.query(LineItemQuotaBinding)
            .filter(LineItemQuotaBinding.boq_item_id == item.id)
            .all()
        )
        quota_codes = []
        for b in bindings:
            q = db.query(QuotaItem).filter(QuotaItem.id == b.quota_item_id).first()
            if q:
                quota_codes.append(f"{q.quota_code}({q.name})")
        results.append({
            "project_id": item.project_id,
            "boq_item_id": item.id,
            "code": item.code,
            "name": item.name,
            "unit": item.unit,
            "quantity": item.quantity,
            "bound_quotas": quota_codes,
            "similarity": round(sim, 3),
        })
    return json.dumps({"results": results, "total_searched": len(all_items)}, ensure_ascii=False)


def _tool_run_full_validation(db: Session, *, project_id: int) -> str:
    issues = validate_project(project_id=project_id, db=db)
    summary = {
        "total": len(issues),
        "errors": sum(1 for i in issues if i.severity == Severity.ERROR),
        "warnings": sum(1 for i in issues if i.severity == Severity.WARNING),
        "info": sum(1 for i in issues if i.severity == Severity.INFO),
        "issues": [
            {
                "code": i.code,
                "severity": i.severity.value,
                "boq_item_id": i.boq_item_id,
                "message": i.message,
                "suggestion": i.suggestion,
            }
            for i in issues[:30]  # limit to avoid token explosion
        ],
    }
    if len(issues) > 30:
        summary["truncated"] = True
        summary["message"] = f"显示前30条，共{len(issues)}条"
    return json.dumps(summary, ensure_ascii=False)


def _tool_get_resource_details(db: Session, *, quota_item_id: int) -> str:
    quota = db.query(QuotaItem).filter(QuotaItem.id == quota_item_id).first()
    if not quota:
        return json.dumps({"error": f"定额 {quota_item_id} 不存在"}, ensure_ascii=False)

    details = (
        db.query(QuotaResourceDetail)
        .filter(QuotaResourceDetail.quota_item_id == quota_item_id)
        .all()
    )
    return json.dumps({
        "quota_code": quota.quota_code,
        "quota_name": quota.name,
        "has_resource_details": getattr(quota, "has_resource_details", 0),
        "details": [
            {
                "category": d.category,
                "resource_code": d.resource_code,
                "resource_name": d.resource_name,
                "spec": d.spec,
                "unit": d.unit,
                "quantity": d.quantity,
                "unit_price": d.unit_price,
                "is_main_material": d.is_main_material,
            }
            for d in details
        ],
    }, ensure_ascii=False)


# ════════════════════════════════════════════════════════════════
# Tool dispatcher
# ════════════════════════════════════════════════════════════════

def _execute_tool(
    tool_name: str,
    tool_args: dict[str, Any],
    db: Session,
    project_id: int,
) -> str:
    try:
        if tool_name == "check_code_compliance":
            return _tool_check_code_compliance(
                db,
                boq_code=tool_args["boq_code"],
                boq_unit=tool_args.get("boq_unit", ""),
            )
        elif tool_name == "detect_price_anomaly":
            return _tool_detect_price_anomaly(
                db, project_id, boq_item_id=tool_args["boq_item_id"]
            )
        elif tool_name == "find_similar_historical_items":
            return _tool_find_similar_items(
                db,
                name_keyword=tool_args["name_keyword"],
                unit=tool_args.get("unit", ""),
                top_n=tool_args.get("top_n", 5),
            )
        elif tool_name == "run_full_validation":
            return _tool_run_full_validation(db, project_id=tool_args["project_id"])
        elif tool_name == "get_resource_details":
            return _tool_get_resource_details(db, quota_item_id=tool_args["quota_item_id"])
        else:
            return json.dumps({"error": f"未知工具: {tool_name}"}, ensure_ascii=False)
    except Exception as exc:
        logger.error("Validation tool %s failed: %s", tool_name, exc)
        return json.dumps({"error": f"工具执行失败: {exc}"}, ensure_ascii=False)


# ════════════════════════════════════════════════════════════════
# System prompt
# ════════════════════════════════════════════════════════════════

_SYSTEM_PROMPT = """\
你是一位专业的工程造价审核AI助手，精通GB50500工程量清单计价规范。

## 你的职责
对工程造价数据进行专业审核，发现问题、解释原因、给出改进建议。

## 审核能力
1. **编码合规性** — 检查清单编码是否符合GB50500标准，单位是否正确
2. **消耗量异常** — 对比同类项目数据，发现人工/材料/机械消耗量的异常值
3. **历史对比** — 查找相似历史清单项，对比组价方案
4. **资源明细** — 检查定额资源明细的完整性和合理性
5. **综合校验** — 运行完整校验引擎，系统化发现问题

## 输出要求
- 用专业但易懂的语言解释每个问题
- 给出具体可操作的改进建议
- 对问题按严重程度排序
- 给出置信度评估（高/中/低）
- 引用具体数据和标准依据
"""


# ════════════════════════════════════════════════════════════════
# Agent runner
# ════════════════════════════════════════════════════════════════

def run_validation_agent(
    *,
    project_id: int,
    scope: str = "full",  # "full" | "item"
    boq_item_id: int | None = None,
    user_question: str = "",
    on_step: Callable[[AgentStep], None] | None = None,
) -> ValidationAgentResult:
    """Run the validation agent.

    Args:
        project_id: Project to validate
        scope: "full" for whole project, "item" for single item
        boq_item_id: Required when scope="item"
        user_question: Optional specific question
        on_step: Streaming callback
    """
    provider = get_ai_provider()
    if not provider.is_enabled() or not provider.is_configured():
        return ValidationAgentResult(
            answer="AI 服务未配置，无法执行智能审核。", error="ai_not_configured"
        )

    db: Session = next(get_db())
    try:
        return _run_loop(
            provider=provider,
            db=db,
            project_id=project_id,
            scope=scope,
            boq_item_id=boq_item_id,
            user_question=user_question,
            on_step=on_step,
        )
    finally:
        db.close()


def _run_loop(
    *,
    provider: Any,
    db: Session,
    project_id: int,
    scope: str,
    boq_item_id: int | None,
    user_question: str,
    on_step: Callable[[AgentStep], None] | None,
) -> ValidationAgentResult:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return ValidationAgentResult(answer="项目不存在。", error="project_not_found")

    # Build user message
    if scope == "item" and boq_item_id:
        boq = db.query(BoqItem).filter(
            BoqItem.id == boq_item_id, BoqItem.project_id == project_id
        ).first()
        if not boq:
            return ValidationAgentResult(answer="清单项不存在。", error="boq_not_found")
        user_msg = (
            f"请审核以下清单项:\n"
            f"编码: {boq.code}, 名称: {boq.name}, 单位: {boq.unit}, "
            f"工程量: {boq.quantity}, 特征: {boq.characteristics or '无'}\n"
            f"项目ID: {project_id}"
        )
    else:
        item_count = db.query(BoqItem).filter(BoqItem.project_id == project_id).count()
        user_msg = f"请对项目 {project.name}（ID={project_id}）进行全面审核，共{item_count}条清单项。"

    if user_question:
        user_msg += f"\n\n用户问题：{user_question}"

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]

    steps: list[AgentStep] = []
    issues_found = 0

    for turn in range(MAX_AGENT_TURNS):
        try:
            response = provider.generate_with_tools(
                task="validation_agent",
                messages=messages,
                tools=AGENT_TOOLS,
            )
        except AIProviderError as exc:
            logger.error("Validation agent error at turn %d: %s", turn, exc)
            return ValidationAgentResult(
                answer=f"AI 调用失败: {exc}",
                steps=steps,
                error="provider_error",
            )

        if not response["tool_calls"]:
            answer = response["content"] or "审核完成。"
            step = AgentStep(type="answer", content=answer)
            steps.append(step)
            if on_step:
                on_step(step)
            return ValidationAgentResult(
                answer=answer, steps=steps, issues_found=issues_found
            )

        if response["content"]:
            thinking_step = AgentStep(type="thinking", content=response["content"])
            steps.append(thinking_step)
            if on_step:
                on_step(thinking_step)

        assistant_msg: dict[str, Any] = {
            "role": "assistant",
            "content": response["content"] or "",
        }
        assistant_msg["tool_calls"] = [
            {
                "id": tc["id"],
                "type": "function",
                "function": {
                    "name": tc["name"],
                    "arguments": json.dumps(tc["arguments"], ensure_ascii=False),
                },
            }
            for tc in response["tool_calls"]
        ]
        messages.append(assistant_msg)

        for tc in response["tool_calls"]:
            tool_step = AgentStep(
                type="tool_call",
                tool_name=tc["name"],
                tool_args=tc["arguments"],
            )

            result_str = _execute_tool(
                tool_name=tc["name"],
                tool_args=tc["arguments"],
                db=db,
                project_id=project_id,
            )

            # Count issues from validation runs
            if tc["name"] == "run_full_validation":
                try:
                    result_data = json.loads(result_str)
                    issues_found = result_data.get("total", 0)
                except (json.JSONDecodeError, KeyError):
                    pass

            tool_step.tool_result = result_str
            tool_step.type = "tool_result"
            steps.append(tool_step)
            if on_step:
                on_step(tool_step)

            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": result_str,
            })

    return ValidationAgentResult(
        answer="审核过程超过最大步数限制，请查看已完成的步骤。",
        steps=steps,
        issues_found=issues_found,
        error="max_turns_exceeded",
    )
