"""Measure-item (措施项目) tools — for MeasuresAgent.

Wraps CRUD on ``MeasureItem`` plus a small "propose standard preliminaries"
helper that returns a GB50500-typical preliminaries kit based on project
attributes. All tools register themselves into the global ToolRegistry
on import.
"""

from __future__ import annotations

import json
from typing import Any

from app.ai.framework.context import AgentContext
from app.ai.framework.tool_def import tool
from app.ai.framework.tool_registry import registry
from app.models.measure_item import MeasureItem
from app.models.boq_item import BoqItem
from app.services.project_calc_service import run_project_calculation


# ---------------------------------------------------------------------------
# Read tools
# ---------------------------------------------------------------------------

@tool(
    name="list_measures",
    description="列出当前项目所有措施项目（含费率/金额/计算基础）。无参数。",
    read_only=True,
)
def list_measures(ctx: AgentContext) -> str:
    rows = (
        ctx.db.query(MeasureItem)
        .filter(MeasureItem.project_id == ctx.project_id)
        .order_by(MeasureItem.id)
        .all()
    )
    items = [
        {
            "id": r.id,
            "name": r.name,
            "calc_base": r.calc_base,  # "direct" | "pre_tax"
            "rate": r.rate,
            "amount": r.amount,
            "is_fixed": bool(r.is_fixed),
        }
        for r in rows
    ]
    return json.dumps(
        {"project_id": ctx.project_id, "total": len(items), "measures": items},
        ensure_ascii=False,
    )


@tool(
    name="get_measures_total",
    description="返回当前项目措施费合计与按计算基础分组的明细（直接费基/税前基/固定金额）。",
    read_only=True,
)
def get_measures_total(ctx: AgentContext) -> str:
    # incremental=True reuses cached CalcResult rows; only dirty items recompute.
    summary, _ = run_project_calculation(
        ctx.project_id, ctx.db, incremental=True,
    )
    rows = (
        ctx.db.query(MeasureItem)
        .filter(MeasureItem.project_id == ctx.project_id)
        .all()
    )

    by_base: dict[str, float] = {"direct": 0.0, "pre_tax": 0.0, "fixed": 0.0}
    for r in rows:
        if r.is_fixed:
            by_base["fixed"] += r.amount
        elif r.calc_base == "pre_tax":
            base = summary.total_pre_tax
            by_base["pre_tax"] += round(base * r.rate, 2)
        else:
            base = summary.total_direct
            by_base["direct"] += round(base * r.rate, 2)

    return json.dumps(
        {
            "project_id": ctx.project_id,
            "count": len(rows),
            "total_measures": summary.total_measures,
            "by_base": {k: round(v, 2) for k, v in by_base.items()},
            "base_values": {
                "total_direct": summary.total_direct,
                "total_pre_tax": summary.total_pre_tax,
            },
        },
        ensure_ascii=False,
    )


# ---------------------------------------------------------------------------
# Write tools
# ---------------------------------------------------------------------------

@tool(
    name="create_measure",
    description=(
        "创建一条措施项目。calc_base 取值：'direct'（按直接费乘费率）|"
        "'pre_tax'（按税前合计乘费率）。is_fixed=true 时使用 amount 作为固定金额，rate 忽略。"
    ),
    read_only=False,
)
def create_measure(
    ctx: AgentContext,
    *,
    name: str,
    calc_base: str = "direct",
    rate: float = 0.0,
    amount: float = 0.0,
    is_fixed: bool = False,
) -> str:
    if calc_base not in ("direct", "pre_tax"):
        return json.dumps(
            {"error": f"非法 calc_base: {calc_base}，只能是 'direct' 或 'pre_tax'"},
            ensure_ascii=False,
        )
    if not name or not name.strip():
        return json.dumps({"error": "name 不能为空"}, ensure_ascii=False)

    m = MeasureItem(
        project_id=ctx.project_id,
        name=name.strip(),
        calc_base=calc_base,
        rate=float(rate),
        amount=float(amount),
        is_fixed=1 if is_fixed else 0,
    )
    ctx.db.add(m)
    ctx.db.commit()
    ctx.db.refresh(m)
    return json.dumps(
        {
            "ok": True,
            "id": m.id,
            "name": m.name,
            "calc_base": m.calc_base,
            "rate": m.rate,
            "amount": m.amount,
            "is_fixed": bool(m.is_fixed),
        },
        ensure_ascii=False,
    )


@tool(
    name="update_measure",
    description="更新某条措施项目。只更新传入的字段，未传入字段保持不变。",
    read_only=False,
)
def update_measure(
    ctx: AgentContext,
    *,
    measure_id: int,
    name: str | None = None,
    calc_base: str | None = None,
    rate: float | None = None,
    amount: float | None = None,
    is_fixed: bool | None = None,
) -> str:
    m = (
        ctx.db.query(MeasureItem)
        .filter(
            MeasureItem.id == measure_id,
            MeasureItem.project_id == ctx.project_id,
        )
        .first()
    )
    if not m:
        return json.dumps(
            {"error": f"措施项目 id={measure_id} 不存在或不属于当前项目"},
            ensure_ascii=False,
        )
    if name is not None:
        m.name = name.strip()
    if calc_base is not None:
        if calc_base not in ("direct", "pre_tax"):
            return json.dumps(
                {"error": f"非法 calc_base: {calc_base}"}, ensure_ascii=False
            )
        m.calc_base = calc_base
    if rate is not None:
        m.rate = float(rate)
    if amount is not None:
        m.amount = float(amount)
    if is_fixed is not None:
        m.is_fixed = 1 if is_fixed else 0
    ctx.db.commit()
    return json.dumps({"ok": True, "id": m.id}, ensure_ascii=False)


@tool(
    name="delete_measure",
    description="删除一条措施项目（按 measure_id）。",
    read_only=False,
)
def delete_measure(ctx: AgentContext, *, measure_id: int) -> str:
    m = (
        ctx.db.query(MeasureItem)
        .filter(
            MeasureItem.id == measure_id,
            MeasureItem.project_id == ctx.project_id,
        )
        .first()
    )
    if not m:
        return json.dumps(
            {"error": f"措施项目 id={measure_id} 不存在或不属于当前项目"},
            ensure_ascii=False,
        )
    ctx.db.delete(m)
    ctx.db.commit()
    return json.dumps({"ok": True, "deleted_id": measure_id}, ensure_ascii=False)


@tool(
    name="batch_create_measures",
    description=(
        "批量创建措施项目。items 为 JSON 字符串，数组每项含 "
        "{name, calc_base, rate?, amount?, is_fixed?}。"
        "适合一次性导入标准措施项目套餐。"
    ),
    read_only=False,
)
def batch_create_measures(ctx: AgentContext, *, items: str) -> str:
    try:
        rows: list[dict[str, Any]] = json.loads(items)
    except json.JSONDecodeError as e:
        return json.dumps(
            {"error": f"items 解析失败：{e}"}, ensure_ascii=False
        )
    if not isinstance(rows, list) or not rows:
        return json.dumps({"error": "items 必须是非空数组"}, ensure_ascii=False)

    created = []
    for r in rows:
        name = (r.get("name") or "").strip()
        if not name:
            continue
        calc_base = r.get("calc_base", "direct")
        if calc_base not in ("direct", "pre_tax"):
            calc_base = "direct"
        m = MeasureItem(
            project_id=ctx.project_id,
            name=name,
            calc_base=calc_base,
            rate=float(r.get("rate") or 0),
            amount=float(r.get("amount") or 0),
            is_fixed=1 if r.get("is_fixed") else 0,
        )
        ctx.db.add(m)
        created.append(name)
    ctx.db.commit()
    return json.dumps(
        {"ok": True, "created_count": len(created), "names": created},
        ensure_ascii=False,
    )


# ---------------------------------------------------------------------------
# Domain helper — propose standard preliminaries
# ---------------------------------------------------------------------------

# GB50500 typical preliminaries (措施项目) catalog. Rates are mid-range
# defaults; the agent should adjust based on project type/region.
STANDARD_GB_PRELIMINARIES: list[dict[str, Any]] = [
    {"name": "安全文明施工费", "calc_base": "direct", "rate": 0.025,
     "is_fixed": False, "note": "不可竞争费，地区差异大，0.020~0.035"},
    {"name": "夜间施工增加费", "calc_base": "direct", "rate": 0.003,
     "is_fixed": False, "note": "夜间作业项目按需"},
    {"name": "二次搬运费", "calc_base": "direct", "rate": 0.005,
     "is_fixed": False, "note": "市区/远距离场地"},
    {"name": "冬雨季施工增加费", "calc_base": "direct", "rate": 0.003,
     "is_fixed": False, "note": "北方/雨季多发地区按需"},
    {"name": "已完工程及设备保护费", "calc_base": "direct", "rate": 0.0015,
     "is_fixed": False, "note": "装饰阶段较常见"},
    {"name": "施工排水/降水费", "calc_base": "direct", "rate": 0.004,
     "is_fixed": False, "note": "地下水位高时使用"},
    {"name": "脚手架工程", "calc_base": "direct", "rate": 0.025,
     "is_fixed": False, "note": "按建筑面积也可计费"},
    {"name": "模板工程", "calc_base": "direct", "rate": 0.040,
     "is_fixed": False, "note": "若已分项计入清单则去除"},
    {"name": "垂直运输", "calc_base": "direct", "rate": 0.020,
     "is_fixed": False, "note": "高层项目偏高"},
    {"name": "大型机械设备进出场及安拆", "calc_base": "direct",
     "rate": 0.0, "amount": 0, "is_fixed": True,
     "note": "按实际进出场次数计算固定金额"},
]


@tool(
    name="propose_standard_measures",
    description=(
        "根据 GB50500 国标返回典型措施项目套餐建议（含费率/计算基础/备注）。"
        "Agent 需根据项目实际情况筛选/调整后再用 batch_create_measures 写入。"
        "结果不会写库。"
    ),
    read_only=True,
)
def propose_standard_measures(ctx: AgentContext) -> str:
    # Provide minimal project context to help the agent reason.
    boq_count = (
        ctx.db.query(BoqItem)
        .filter(BoqItem.project_id == ctx.project_id)
        .count()
    )
    project = ctx.get_project()
    return json.dumps(
        {
            "project_id": ctx.project_id,
            "project_type": getattr(project, "project_type", None),
            "region": getattr(project, "region", None),
            "boq_count": boq_count,
            "standard": "GB50500",
            "candidate_measures": STANDARD_GB_PRELIMINARIES,
            "guidance": (
                "根据项目类型/地区/规模选择适用项；高层项目'垂直运输'费率提高；"
                "南方雨季多发地区'冬雨季施工增加费'保留；安全文明施工费"
                "为不可竞争费用，必须保留。"
            ),
        },
        ensure_ascii=False,
    )


# ── Register ──

registry.register_many(
    list_measures,
    get_measures_total,
    create_measure,
    update_measure,
    delete_measure,
    batch_create_measures,
    propose_standard_measures,
)
