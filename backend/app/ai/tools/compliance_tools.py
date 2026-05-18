"""Compliance tools — M6 agent adaptation for GB/T 50500-2024.

New tools:
- search_quotas_2024       Search quota items from the 2024 standard only
- get_other_items_summary  List 其他项目费 category totals for a project
- add_other_item           Create an 其他项目费 entry
- get_regulatory_fees      Calculate 规费明细 from BOQ labor fees
- parse_boq_code           Parse a 12-digit BOQ code into structured segments
- calculate_five_fees      Full GB五费 breakdown using PricingEngineV2
"""

from __future__ import annotations

import json

from app.ai.framework.context import AgentContext
from app.ai.framework.tool_def import tool
from app.ai.framework.tool_registry import registry
from app.models.boq_item import BoqItem
from app.models.line_item_quota_binding import LineItemQuotaBinding
from app.models.other_item import OtherItem
from app.models.pricing_standard import PricingStandard
from app.models.quota_item import QuotaItem


# ─── Constants ───────────────────────────────────────────────────────────────

_VALID_CATEGORIES = {"provisional_sum", "provisional_price", "daywork", "gc_service"}

_CATEGORY_ZH = {
    "provisional_sum": "暂列金额",
    "provisional_price": "暂估价",
    "daywork": "计日工",
    "gc_service": "总承包服务费",
}


# ─── Read-only tools ─────────────────────────────────────────────────────────

@tool(
    name="search_quotas_2024",
    description=(
        "搜索2024版房建定额库（GBT50500-2024标准），按关键词、章节查询定额，"
        "返回人工费/材料费/机械费单价（非消耗量）。"
        "与 search_quotas 的区别：结果仅限2024标准，并暴露费用单价字段。"
    ),
    read_only=True,
)
def search_quotas_2024(
    ctx: AgentContext,
    *,
    keyword: str,
    chapter_filter: str = "",
    top_n: int = 10,
) -> str:
    """Search GBT50500-2024 quota items by keyword."""
    from difflib import SequenceMatcher
    from app.services.quota_match_service import _name_similarity

    std = ctx.db.query(PricingStandard).filter_by(code="GBT50500-2024").first()
    q = ctx.db.query(QuotaItem)
    if std:
        q = q.filter(QuotaItem.pricing_standard_id == std.id)
    if chapter_filter:
        q = q.filter(QuotaItem.chapter.ilike(f"%{chapter_filter}%"))
    if len(keyword) >= 2:
        q = q.filter(
            (QuotaItem.name.ilike(f"%{keyword}%"))
            | (QuotaItem.quota_code.ilike(f"%{keyword}%"))
        )
    candidates = q.all()
    if not candidates and std:
        candidates = ctx.db.query(QuotaItem).filter(
            QuotaItem.pricing_standard_id == std.id
        ).all()

    scored = []
    kw_lower = keyword.lower()
    for item in candidates:
        name_sim = _name_similarity(keyword, item.name)
        code_sim = SequenceMatcher(None, kw_lower, item.quota_code.lower()).ratio()
        score = name_sim * 0.7 + code_sim * 0.3
        if score > 0.05:
            scored.append((score, item))

    scored.sort(key=lambda x: x[0], reverse=True)
    results = []
    for score, item in scored[:top_n]:
        results.append({
            "quota_item_id": item.id,
            "quota_code": item.quota_code,
            "name": item.name,
            "unit": item.unit,
            "chapter": item.chapter or "",
            "labor_fee": item.labor_fee or 0.0,
            "material_fee": item.material_fee or 0.0,
            "machine_fee": item.machine_fee or 0.0,
            "base_price": item.base_price or 0.0,
            "relevance": round(score, 3),
        })
    return json.dumps({
        "standard": "GBT50500-2024",
        "results": results,
        "candidates_scanned": len(candidates),
    }, ensure_ascii=False)


@tool(
    name="get_other_items_summary",
    description=(
        "查询项目的【其他项目费】汇总：按四大类（暂列金额/暂估价/计日工/总承包服务费）"
        "返回合计和明细条目列表。"
    ),
    read_only=True,
)
def get_other_items_summary(ctx: AgentContext) -> str:
    """Return 其他项目费 category totals and item list for the current project."""
    rows = (
        ctx.db.query(OtherItem)
        .filter(OtherItem.project_id == ctx.project_id)
        .order_by(OtherItem.category, OtherItem.sort_order)
        .all()
    )
    if not rows:
        return json.dumps({
            "project_id": ctx.project_id,
            "grand_total": 0.0,
            "categories": [],
            "message": "当前项目暂无其他项目费条目",
        }, ensure_ascii=False)

    totals: dict[str, float] = {cat: 0.0 for cat in _VALID_CATEGORIES}
    items_by_cat: dict[str, list] = {cat: [] for cat in _VALID_CATEGORIES}

    for r in rows:
        amt = r.amount if r.is_fixed else round(r.quantity * r.unit_price, 2)
        if r.category in totals:
            totals[r.category] += amt
            items_by_cat[r.category].append({
                "id": r.id,
                "name": r.name,
                "unit": r.unit,
                "quantity": r.quantity,
                "unit_price": r.unit_price,
                "amount": amt,
                "is_fixed": r.is_fixed,
            })

    grand = round(sum(totals.values()), 2)
    return json.dumps({
        "project_id": ctx.project_id,
        "grand_total": grand,
        "categories": [
            {
                "category": cat,
                "category_zh": _CATEGORY_ZH[cat],
                "total": round(totals[cat], 2),
                "items": items_by_cat[cat],
            }
            for cat in _VALID_CATEGORIES
        ],
    }, ensure_ascii=False)


@tool(
    name="get_regulatory_fees",
    description=(
        "计算项目【规费明细】：社会保险费 + 住房公积金，以分部分项人工费合计为计算基础。"
        "可选 social_insurance_rate（默认0.285）和 housing_fund_rate（默认0.08）。"
    ),
    read_only=True,
)
def get_regulatory_fees(
    ctx: AgentContext,
    *,
    social_insurance_rate: float = 0.285,
    housing_fund_rate: float = 0.08,
) -> str:
    """Calculate 规费 (social insurance + housing fund) from BOQ labor fees."""
    from app.services.labor_cost_service import calc_project_labor
    total_labor = calc_project_labor(ctx.db, ctx.project_id)
    si = round(total_labor * social_insurance_rate, 2)
    hf = round(total_labor * housing_fund_rate, 2)
    total = round(si + hf, 2)

    return json.dumps({
        "project_id": ctx.project_id,
        "labor_base": total_labor,
        "social_insurance_fee": si,
        "housing_fund_fee": hf,
        "regulatory_fee_total": total,
        "rates": {
            "social_insurance": social_insurance_rate,
            "housing_fund": housing_fund_rate,
        },
        "formula": "规费 = 人工费合计 × (社保率 + 公积金率)",
    }, ensure_ascii=False)


@tool(
    name="parse_boq_code",
    description=(
        "解析清单12位编码，返回结构化的专业/章节/节/子目/变体五段信息。"
        "例如 '010301001001' → 专业=01, 章=03, 节=01, 子目=001, 变体=001。"
    ),
    read_only=True,
)
def parse_boq_code(ctx: AgentContext, *, code: str) -> str:
    """Parse a 12-digit GB50500 BOQ code into structured segments."""
    from app.services.code_parser import parse_code, validate_code

    code = code.strip().replace("-", "").replace(" ", "")
    vr = validate_code(code)
    if not vr.valid:
        return json.dumps({
            "ok": False,
            "code": code,
            "error": f"编码 '{code}' 格式无效（须为12位数字）",
        }, ensure_ascii=False)

    segments = parse_code(code)
    return json.dumps({
        "ok": True,
        **segments.to_dict(),
    }, ensure_ascii=False)


@tool(
    name="calculate_five_fees",
    description=(
        "使用 PricingEngineV2 计算项目的完整五费（分部分项/措施/其他/规费/税金）合计。"
        "可选 standard_code（'GB50500-2013' 或 'GBT50500-2024'，默认自动从项目读取），"
        "tax_method（'general' 9% 一般计税 或 'simple' 3% 简易计税）。"
    ),
    read_only=True,
)
def calculate_five_fees(
    ctx: AgentContext,
    *,
    standard_code: str = "",
    tax_method: str = "general",
) -> str:
    """Calculate the full GB五费 breakdown for the current project."""
    from app.services.pricing_engine_v2 import (
        PricingEngineV2,
        PricingStandardCode,
        TaxMethod,
        BoqLineInput,
        OtherItemInput,
        make_engine_from_project,
    )
    from app.models.project import Project

    project = ctx.db.query(Project).filter(Project.id == ctx.project_id).first()
    if not project:
        return json.dumps({"error": f"项目 {ctx.project_id} 不存在"}, ensure_ascii=False)

    # Build engine from project defaults, then apply caller overrides
    try:
        base = make_engine_from_project(project)
        std = base.standard
        if standard_code:
            try:
                std = PricingStandardCode(standard_code)
            except ValueError:
                pass
        tm = TaxMethod.SIMPLE if tax_method == "simple" else TaxMethod.GENERAL
        engine = PricingEngineV2(
            standard=std,
            tax_method=tm,
            labor_index=base.labor_index,
            fee_config=base.fee_config,
        )
    except Exception as e:
        return json.dumps({"error": f"引擎初始化失败: {e}"}, ensure_ascii=False)

    # Collect BOQ line inputs
    boq_rows = ctx.db.query(BoqItem).filter(BoqItem.project_id == ctx.project_id).all()
    boq_lines: list[BoqLineInput] = []
    for boq in boq_rows:
        bindings = (
            ctx.db.query(LineItemQuotaBinding)
            .filter(LineItemQuotaBinding.boq_item_id == boq.id)
            .all()
        )
        total_labor = total_material = total_machine = 0.0
        for b in bindings:
            q = ctx.db.query(QuotaItem).filter(QuotaItem.id == b.quota_item_id).first()
            if q:
                coef = b.coefficient or 1.0
                if q.labor_fee:
                    total_labor += q.labor_fee * coef
                else:
                    total_labor += (q.labor_qty or 0.0) * 80.0 * coef
                total_material += (q.material_fee or (q.material_qty or 0.0) * 60.0) * coef
                total_machine += (q.machine_fee or (q.machine_qty or 0.0) * 50.0) * coef
        if total_labor + total_material + total_machine > 0:
            boq_lines.append(BoqLineInput(
                boq_item_id=boq.id,
                code=boq.code or "",
                name=boq.name or "",
                unit=boq.unit or "项",
                quantity=boq.quantity or 0.0,
                labor_fee=total_labor,
                material_fee=total_material,
                machine_fee=total_machine,
            ))

    # Collect other items
    other_rows = ctx.db.query(OtherItem).filter(OtherItem.project_id == ctx.project_id).all()
    other_inputs = [
        OtherItemInput(
            name=r.name,
            category=r.category,
            amount=r.amount if r.is_fixed else round(r.quantity * r.unit_price, 2),
        )
        for r in other_rows
    ]

    try:
        result = engine.calculate(
            boq_lines=boq_lines,
            measure_items=[],
            other_items=other_inputs,
        )
    except Exception as e:
        return json.dumps({"error": f"计算失败: {e}"}, ensure_ascii=False)

    return json.dumps({
        "project_id": ctx.project_id,
        "standard": engine.standard.value,
        "tax_method": tax_method,
        "fen_bu_xiangmu": result.fen_bu_total,
        "cuo_shi_fei": result.cuo_shi_total,
        "other_xiangmu": result.other_total,
        "gui_fei": result.gui_fei_total,
        "shui_jin": result.tax_total,
        "grand_total": result.grand_total,
        "provenance": result.provenance,
    }, ensure_ascii=False)


# ─── Write tools ─────────────────────────────────────────────────────────────

@tool(
    name="add_other_item",
    description=(
        "为项目添加【其他项目费】条目。"
        "category 必须是以下之一：'provisional_sum'（暂列金额）、'provisional_price'（暂估价）、"
        "'daywork'（计日工）、'gc_service'（总承包服务费）。"
        "is_fixed=1 时 amount 为权威金额；is_fixed=0 时金额 = quantity × unit_price 自动计算。"
    ),
    destructive=True,
)
def add_other_item(
    ctx: AgentContext,
    *,
    category: str,
    name: str,
    unit: str = "项",
    quantity: float = 1.0,
    unit_price: float = 0.0,
    amount: float = 0.0,
    is_fixed: int = 0,
    note: str = "",
) -> str:
    """Create an OtherItem for the current project."""
    if category not in _VALID_CATEGORIES:
        return json.dumps({
            "ok": False,
            "error": f"无效类别 '{category}'，有效值: {sorted(_VALID_CATEGORIES)}",
        }, ensure_ascii=False)

    computed = amount if is_fixed else round(quantity * unit_price, 2)
    item = OtherItem(
        project_id=ctx.project_id,
        category=category,
        name=name,
        unit=unit,
        quantity=quantity,
        unit_price=unit_price,
        amount=computed,
        is_fixed=is_fixed,
        note=note,
    )
    ctx.db.add(item)
    ctx.db.commit()
    ctx.db.refresh(item)

    return json.dumps({
        "ok": True,
        "id": item.id,
        "category": category,
        "category_zh": _CATEGORY_ZH[category],
        "name": name,
        "amount": computed,
        "message": f"已添加{_CATEGORY_ZH[category]}条目：{name}，金额={computed}",
    }, ensure_ascii=False)


# ─── Register all tools into the global registry ─────────────────────────────

registry.register_many(
    search_quotas_2024,
    get_other_items_summary,
    get_regulatory_fees,
    parse_boq_code,
    calculate_five_fees,
    add_other_item,
)
