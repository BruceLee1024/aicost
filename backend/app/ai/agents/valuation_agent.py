"""Valuation Agent — multi-step reasoning with tool calling for smart pricing.

This agent can:
1. Search quota database for matching quotas
2. Inspect quota details (labor/material/machine quantities)
3. Bind multiple quotas to a BOQ item (with coefficients)
4. Unbind quotas
5. Calculate cost for a BOQ item
6. Look up material prices

The agent runs an iterative loop:
  system prompt → model thinks → calls tools → observe results → repeat
  until the model returns a final text response (no more tool calls).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.ai.providers import AIProviderError, ToolCallRequest, get_ai_provider
from app.db.session import get_db
from app.models.boq_item import BoqItem
from app.models.boq_standard_code import BoqStandardCode
from app.models.line_item_quota_binding import LineItemQuotaBinding
from app.models.quota_item import QuotaItem
from app.services.quota_match_service import _name_similarity, _units_compatible
from app.services.validation_service import normalize_unit

logger = logging.getLogger(__name__)

MAX_AGENT_TURNS = 12

# ════════════════════════════════════════════════════════════════
# Tool definitions (OpenAI function calling schema)
# ════════════════════════════════════════════════════════════════

AGENT_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_quotas",
            "description": "搜索定额库，根据关键词、名称或编码查找候选定额。返回最多10条匹配结果。",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "搜索关键词（定额名称、编码或描述的一部分）",
                    },
                    "unit_filter": {
                        "type": "string",
                        "description": "可选：按单位筛选，如 m3, m2, t 等",
                    },
                    "top_n": {
                        "type": "integer",
                        "description": "返回数量，默认10",
                    },
                },
                "required": ["keyword"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_quota_detail",
            "description": "查看一条定额的详细信息，包括人工/材料/机械消耗量。",
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
    {
        "type": "function",
        "function": {
            "name": "bind_quota",
            "description": "将一条定额绑定到当前清单项，支持设置系数。一条清单可以绑定多条定额（组合定额）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "quota_item_id": {
                        "type": "integer",
                        "description": "要绑定的定额ID",
                    },
                    "coefficient": {
                        "type": "number",
                        "description": "系数，默认1.0。用于调整定额消耗量。",
                    },
                },
                "required": ["quota_item_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "unbind_quota",
            "description": "解除一条定额与当前清单项的绑定。",
            "parameters": {
                "type": "object",
                "properties": {
                    "binding_id": {
                        "type": "integer",
                        "description": "绑定记录ID",
                    },
                },
                "required": ["binding_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_current_bindings",
            "description": "查看当前清单项已绑定的所有定额。",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_cost",
            "description": "基于当前绑定的所有定额，计算清单项的综合单价和合价。",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_material_prices",
            "description": "查询当前项目区域的材料信息价（人工费、材料费、机械费单价）。",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_standard_codes",
            "description": "搜索GB50500标准清单编码库，获取标准名称、单位、计量规则和项目特征模板。用于确认编码合规性和获取专业参考。",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "搜索关键词（编码或名称）",
                    },
                },
                "required": ["keyword"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "validate_binding",
            "description": "校验当前清单项的绑定状态，检查单位一致性、消耗量合理性等。",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
]


# ════════════════════════════════════════════════════════════════
# Agent step tracking
# ════════════════════════════════════════════════════════════════

@dataclass
class AgentStep:
    """One step in the agent reasoning chain."""
    type: str  # "thinking" | "tool_call" | "tool_result" | "answer"
    content: str = ""
    tool_name: str = ""
    tool_args: dict[str, Any] = field(default_factory=dict)
    tool_result: str = ""


@dataclass
class AgentResult:
    """Complete result of an agent run."""
    answer: str
    steps: list[AgentStep] = field(default_factory=list)
    bindings_changed: bool = False
    error: str | None = None


# ════════════════════════════════════════════════════════════════
# Tool implementations
# ════════════════════════════════════════════════════════════════

def _tool_search_quotas(
    db: Session,
    boq: BoqItem,
    *,
    keyword: str,
    unit_filter: str = "",
    top_n: int = 10,
) -> str:
    """Search quota database by keyword similarity."""
    quotas = db.query(QuotaItem).all()
    if not quotas:
        return json.dumps({"results": [], "message": "定额库为空"}, ensure_ascii=False)

    scored: list[tuple[float, QuotaItem]] = []
    kw_lower = keyword.lower()
    for q in quotas:
        name_sim = _name_similarity(keyword, q.name)
        code_sim = SequenceMatcher(None, kw_lower, q.quota_code.lower()).ratio()
        score = name_sim * 0.7 + code_sim * 0.3
        if unit_filter and not _units_compatible(unit_filter, q.unit):
            score *= 0.3
        if score > 0.05:
            scored.append((score, q))

    scored.sort(key=lambda x: x[0], reverse=True)
    results = []
    for score, q in scored[:top_n]:
        results.append({
            "quota_item_id": q.id,
            "quota_code": q.quota_code,
            "name": q.name,
            "unit": q.unit,
            "labor_qty": q.labor_qty,
            "material_qty": q.material_qty,
            "machine_qty": q.machine_qty,
            "relevance": round(score, 3),
        })
    return json.dumps({"results": results, "total_in_db": len(quotas)}, ensure_ascii=False)


def _tool_get_quota_detail(db: Session, *, quota_item_id: int) -> str:
    q = db.query(QuotaItem).filter(QuotaItem.id == quota_item_id).first()
    if not q:
        return json.dumps({"error": f"定额ID {quota_item_id} 不存在"}, ensure_ascii=False)
    return json.dumps({
        "quota_item_id": q.id,
        "quota_code": q.quota_code,
        "name": q.name,
        "unit": q.unit,
        "labor_qty": q.labor_qty,
        "material_qty": q.material_qty,
        "machine_qty": q.machine_qty,
    }, ensure_ascii=False)


def _tool_bind_quota(
    db: Session,
    boq: BoqItem,
    *,
    quota_item_id: int,
    coefficient: float = 1.0,
) -> str:
    q = db.query(QuotaItem).filter(QuotaItem.id == quota_item_id).first()
    if not q:
        return json.dumps({"error": f"定额ID {quota_item_id} 不存在"}, ensure_ascii=False)

    existing = (
        db.query(LineItemQuotaBinding)
        .filter(
            LineItemQuotaBinding.boq_item_id == boq.id,
            LineItemQuotaBinding.quota_item_id == quota_item_id,
        )
        .first()
    )
    if existing:
        existing.coefficient = coefficient
        db.commit()
        return json.dumps({
            "action": "updated",
            "binding_id": existing.id,
            "quota_code": q.quota_code,
            "quota_name": q.name,
            "coefficient": coefficient,
            "message": f"已更新绑定系数为 {coefficient}",
        }, ensure_ascii=False)

    binding = LineItemQuotaBinding(
        boq_item_id=boq.id,
        quota_item_id=quota_item_id,
        coefficient=coefficient,
    )
    db.add(binding)
    boq.is_dirty = 1
    db.commit()
    db.refresh(binding)
    return json.dumps({
        "action": "created",
        "binding_id": binding.id,
        "quota_code": q.quota_code,
        "quota_name": q.name,
        "coefficient": coefficient,
        "message": f"已绑定定额 [{q.quota_code}] {q.name}，系数={coefficient}",
    }, ensure_ascii=False)


def _tool_unbind_quota(db: Session, boq: BoqItem, *, binding_id: int) -> str:
    binding = (
        db.query(LineItemQuotaBinding)
        .filter(
            LineItemQuotaBinding.id == binding_id,
            LineItemQuotaBinding.boq_item_id == boq.id,
        )
        .first()
    )
    if not binding:
        return json.dumps({"error": f"绑定ID {binding_id} 不存在或不属于当前清单"}, ensure_ascii=False)

    db.delete(binding)
    boq.is_dirty = 1
    db.commit()
    return json.dumps({"action": "deleted", "binding_id": binding_id, "message": "已解除绑定"}, ensure_ascii=False)


def _tool_list_bindings(db: Session, boq: BoqItem) -> str:
    bindings = (
        db.query(LineItemQuotaBinding)
        .filter(LineItemQuotaBinding.boq_item_id == boq.id)
        .all()
    )
    if not bindings:
        return json.dumps({"bindings": [], "message": "当前无绑定定额"}, ensure_ascii=False)

    results = []
    for b in bindings:
        q = db.query(QuotaItem).filter(QuotaItem.id == b.quota_item_id).first()
        results.append({
            "binding_id": b.id,
            "quota_item_id": b.quota_item_id,
            "quota_code": q.quota_code if q else "?",
            "quota_name": q.name if q else "未知",
            "unit": q.unit if q else "",
            "coefficient": b.coefficient,
            "labor_qty": round(q.labor_qty * b.coefficient, 4) if q else 0,
            "material_qty": round(q.material_qty * b.coefficient, 4) if q else 0,
            "machine_qty": round(q.machine_qty * b.coefficient, 4) if q else 0,
        })
    return json.dumps({"bindings": results, "count": len(results)}, ensure_ascii=False)


def _tool_calculate_cost(db: Session, boq: BoqItem, project_region: str) -> str:
    from app.services.project_calc_service import (
        _compose_quota_quantities,
        _lookup_price,
        _resolve_fee_config,
    )
    from app.services.pricing_engine import calculate_line_item

    bindings = (
        db.query(LineItemQuotaBinding)
        .filter(LineItemQuotaBinding.boq_item_id == boq.id)
        .all()
    )
    if not bindings:
        return json.dumps({"error": "当前无绑定定额，无法计算"}, ensure_ascii=False)

    quota_by_id = {
        q.id: q
        for q in db.query(QuotaItem)
        .filter(QuotaItem.id.in_([b.quota_item_id for b in bindings]))
        .all()
    }

    labor_qty, material_qty, machine_qty = _compose_quota_quantities(bindings, quota_by_id)
    labor_price = _lookup_price(db, category="人工费", region=project_region)
    material_price = _lookup_price(db, category="材料费", region=project_region)
    machine_price = _lookup_price(db, category="机械费", region=project_region)

    fee_config = _resolve_fee_config(boq.project_id, db)
    result = calculate_line_item(
        labor_qty=labor_qty,
        labor_price=labor_price,
        material_qty=material_qty,
        material_price=material_price,
        machine_qty=machine_qty,
        machine_price=machine_price,
        quantity=boq.quantity,
        fee_config=fee_config,
    )

    return json.dumps({
        "boq_quantity": boq.quantity,
        "composed_labor_qty": round(labor_qty, 4),
        "composed_material_qty": round(material_qty, 4),
        "composed_machine_qty": round(machine_qty, 4),
        "labor_price": labor_price,
        "material_price": material_price,
        "machine_price": machine_price,
        "labor_cost": result.labor_cost,
        "material_cost": result.material_cost,
        "machine_cost": result.machine_cost,
        "direct_cost": result.direct_cost,
        "management_fee": result.management_fee,
        "profit": result.profit,
        "regulatory_fee": result.regulatory_fee,
        "pre_tax_total": result.pre_tax_total,
        "tax": result.tax,
        "total": result.total,
        "unit_price": round(result.total / boq.quantity, 2) if boq.quantity else 0,
    }, ensure_ascii=False)


def _tool_get_material_prices(db: Session, project_region: str) -> str:
    from app.services.project_calc_service import _lookup_price

    labor = _lookup_price(db, category="人工费", region=project_region)
    material = _lookup_price(db, category="材料费", region=project_region)
    machine = _lookup_price(db, category="机械费", region=project_region)
    return json.dumps({
        "region": project_region,
        "labor_price": labor,
        "material_price": material,
        "machine_price": machine,
    }, ensure_ascii=False)


def _tool_search_standard_codes(db: Session, *, keyword: str) -> str:
    """Search GB50500 standard codes by keyword."""
    from difflib import SequenceMatcher as SM

    all_codes = db.query(BoqStandardCode).all()
    if not all_codes:
        return json.dumps({"results": [], "message": "标准编码库为空"}, ensure_ascii=False)

    scored = []
    kw = keyword.strip()
    for sc in all_codes:
        name_sim = SM(None, kw, sc.name).ratio()
        code_sim = SM(None, kw, sc.standard_code).ratio()
        score = max(name_sim, code_sim)
        if kw in sc.name or kw in sc.standard_code:
            score = max(score, 0.8)
        if score > 0.2:
            scored.append((score, sc))

    scored.sort(key=lambda x: x[0], reverse=True)
    results = []
    for score, sc in scored[:8]:
        results.append({
            "standard_code": sc.standard_code,
            "name": sc.name,
            "standard_unit": sc.standard_unit,
            "division": sc.division,
            "measurement_rule": sc.measurement_rule[:100] if sc.measurement_rule else "",
            "common_characteristics": sc.common_characteristics,
            "relevance": round(score, 3),
        })
    return json.dumps({"results": results}, ensure_ascii=False)


def _tool_validate_binding(db: Session, boq: BoqItem) -> str:
    """Validate current bindings for issues."""
    bindings = (
        db.query(LineItemQuotaBinding)
        .filter(LineItemQuotaBinding.boq_item_id == boq.id)
        .all()
    )
    if not bindings:
        return json.dumps({"valid": False, "issues": ["无绑定定额"]}, ensure_ascii=False)

    issues = []
    for b in bindings:
        q = db.query(QuotaItem).filter(QuotaItem.id == b.quota_item_id).first()
        if not q:
            issues.append(f"绑定ID {b.id} 的定额不存在")
            continue
        if normalize_unit(boq.unit) != normalize_unit(q.unit):
            issues.append(
                f"定额 [{q.quota_code}] 单位 '{q.unit}' 与清单单位 '{boq.unit}' 不一致，请确认是否需要换算系数"
            )
        if q.labor_qty == 0 and q.material_qty == 0 and q.machine_qty == 0:
            issues.append(f"定额 [{q.quota_code}] 人材机含量均为0")

    # Check against standard code
    code_prefix = boq.code.split("-")[0].strip()
    std = db.query(BoqStandardCode).filter(BoqStandardCode.standard_code == code_prefix).first()
    if not std and len(code_prefix) >= 9:
        std = db.query(BoqStandardCode).filter(BoqStandardCode.standard_code == code_prefix[:9]).first()
    if std and normalize_unit(boq.unit) != normalize_unit(std.standard_unit):
        issues.append(f"清单单位 '{boq.unit}' 与GB50500标准单位 '{std.standard_unit}' 不一致")

    return json.dumps({
        "valid": len(issues) == 0,
        "binding_count": len(bindings),
        "issues": issues,
        "standard_code_match": std.name if std else None,
    }, ensure_ascii=False)


# ════════════════════════════════════════════════════════════════
# Tool dispatcher
# ════════════════════════════════════════════════════════════════

def _execute_tool(
    tool_name: str,
    tool_args: dict[str, Any],
    db: Session,
    boq: BoqItem,
    project_region: str,
) -> str:
    """Execute a tool call and return the result as a JSON string."""
    try:
        if tool_name == "search_quotas":
            return _tool_search_quotas(
                db, boq,
                keyword=tool_args.get("keyword", ""),
                unit_filter=tool_args.get("unit_filter", ""),
                top_n=tool_args.get("top_n", 10),
            )
        elif tool_name == "get_quota_detail":
            return _tool_get_quota_detail(db, quota_item_id=tool_args["quota_item_id"])
        elif tool_name == "bind_quota":
            return _tool_bind_quota(
                db, boq,
                quota_item_id=tool_args["quota_item_id"],
                coefficient=tool_args.get("coefficient", 1.0),
            )
        elif tool_name == "unbind_quota":
            return _tool_unbind_quota(db, boq, binding_id=tool_args["binding_id"])
        elif tool_name == "list_current_bindings":
            return _tool_list_bindings(db, boq)
        elif tool_name == "calculate_cost":
            return _tool_calculate_cost(db, boq, project_region)
        elif tool_name == "get_material_prices":
            return _tool_get_material_prices(db, project_region)
        elif tool_name == "search_standard_codes":
            return _tool_search_standard_codes(db, keyword=tool_args.get("keyword", ""))
        elif tool_name == "validate_binding":
            return _tool_validate_binding(db, boq)
        else:
            return json.dumps({"error": f"未知工具: {tool_name}"}, ensure_ascii=False)
    except Exception as exc:
        logger.error("Tool %s execution failed: %s", tool_name, exc)
        return json.dumps({"error": f"工具执行失败: {exc}"}, ensure_ascii=False)


# ════════════════════════════════════════════════════════════════
# System prompt
# ════════════════════════════════════════════════════════════════

_SYSTEM_PROMPT = """\
你是一位专业的工程计价AI助手，精通GB50500清单计价规范和定额组价方法。

## 你的任务
为指定的工程量清单项匹配合适的定额并完成组价。一条清单项可以绑定多条定额（组合定额），每条定额可设置系数来调整消耗量。

## 工作流程
1. **分析清单项** — 理解清单项的名称、特征、单位和工程量
2. **查询标准** — 使用 search_standard_codes 查询GB50500标准编码，确认计量规则和项目特征要求
3. **搜索定额** — 使用 search_quotas 工具搜索相关定额
4. **评估候选** — 查看定额详情，评估是否匹配
5. **绑定定额** — 使用 bind_quota 绑定合适的定额，必要时绑定多条并设置系数
6. **校验绑定** — 使用 validate_binding 检查绑定单位一致性等问题
7. **验证计算** — 使用 calculate_cost 计算综合单价，确认合理性

## 组价原则
- 清单项的工作内容可能需要多条定额组合才能完整描述
- 例如：混凝土清单 = 混凝土浇筑定额 + 模板定额 + 钢筋定额
- 系数用于调整定额消耗量（如楼层系数、难度系数等）
- 单位不一致时要特别注意换算
- 优先选择名称和单位都匹配的定额

## 输出要求
- 每一步操作都要简要说明理由
- 最终给出组价结论：绑定了哪些定额、综合单价是多少
- 如果无法找到合适定额，说明原因
"""


# ════════════════════════════════════════════════════════════════
# Agent runner
# ════════════════════════════════════════════════════════════════

def run_valuation_agent(
    *,
    project_id: int,
    boq_item_id: int,
    user_instruction: str = "",
    on_step: Callable[[AgentStep], None] | None = None,
) -> AgentResult:
    """Run the valuation agent for a single BOQ item.

    Args:
        project_id: Project ID
        boq_item_id: BOQ item to valuate
        user_instruction: Optional user instruction (e.g. "用混凝土C30定额")
        on_step: Optional callback for streaming steps to client

    Returns:
        AgentResult with the final answer and all intermediate steps.
    """
    provider = get_ai_provider()
    if not provider.is_enabled() or not provider.is_configured():
        return AgentResult(answer="AI 服务未配置，无法执行智能组价。", error="ai_not_configured")

    db: Session = next(get_db())
    try:
        return _run_agent_loop(
            provider=provider,
            db=db,
            project_id=project_id,
            boq_item_id=boq_item_id,
            user_instruction=user_instruction,
            on_step=on_step,
        )
    finally:
        db.close()


def _run_agent_loop(
    *,
    provider: Any,
    db: Session,
    project_id: int,
    boq_item_id: int,
    user_instruction: str,
    on_step: Callable[[AgentStep], None] | None,
) -> AgentResult:
    from app.models.project import Project

    boq = db.query(BoqItem).filter(BoqItem.id == boq_item_id, BoqItem.project_id == project_id).first()
    if not boq:
        return AgentResult(answer="清单项不存在。", error="boq_not_found")

    project = db.query(Project).filter(Project.id == project_id).first()
    project_region = project.region if project else ""

    # Build initial user message with BOQ context
    boq_context = {
        "boq_item_id": boq.id,
        "code": boq.code,
        "name": boq.name,
        "characteristics": boq.characteristics,
        "unit": boq.unit,
        "quantity": boq.quantity,
        "division": boq.division,
        "project_region": project_region,
    }

    user_msg = f"请为以下清单项进行智能组价：\n{json.dumps(boq_context, ensure_ascii=False, indent=2)}"
    if user_instruction:
        user_msg += f"\n\n用户补充说明：{user_instruction}"

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]

    steps: list[AgentStep] = []
    bindings_changed = False

    for turn in range(MAX_AGENT_TURNS):
        try:
            response = provider.generate_with_tools(
                task="valuation_agent",
                messages=messages,
                tools=AGENT_TOOLS,
            )
        except AIProviderError as exc:
            logger.error("Agent provider error at turn %d: %s", turn, exc)
            return AgentResult(
                answer=f"AI 调用失败: {exc}",
                steps=steps,
                bindings_changed=bindings_changed,
                error="provider_error",
            )

        # If model returned text with no tool calls, it's the final answer
        if not response["tool_calls"]:
            answer = response["content"] or "组价完成。"
            step = AgentStep(type="answer", content=answer)
            steps.append(step)
            if on_step:
                on_step(step)
            return AgentResult(
                answer=answer,
                steps=steps,
                bindings_changed=bindings_changed,
            )

        # Model wants to think first (content + tool_calls)
        if response["content"]:
            thinking_step = AgentStep(type="thinking", content=response["content"])
            steps.append(thinking_step)
            if on_step:
                on_step(thinking_step)

        # Build assistant message with tool calls for conversation history
        assistant_msg: dict[str, Any] = {"role": "assistant", "content": response["content"] or ""}
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

        # Execute each tool call
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
                boq=boq,
                project_region=project_region,
            )

            tool_step.tool_result = result_str
            tool_step.type = "tool_result"
            steps.append(tool_step)
            if on_step:
                on_step(tool_step)

            # Track if bindings were modified
            if tc["name"] in ("bind_quota", "unbind_quota"):
                bindings_changed = True

            # Add tool result to conversation
            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": result_str,
            })

    # Exceeded max turns
    return AgentResult(
        answer="组价过程超过最大步数限制，请查看已完成的步骤。",
        steps=steps,
        bindings_changed=bindings_changed,
        error="max_turns_exceeded",
    )
