"""Labor / Material / Machine (人材机) aggregation tools.

Aggregates resource consumption across all bindings of a project, producing:
- ``aggregate_lmm_summary``: totals per category (人工/材料/机械) + grand total
- ``aggregate_lmm_by_resource``: per-resource ranked totals (for cost driver analysis)
- ``find_main_materials``: lists the project's main-material items (主材) and
  whether they have an 信息价 mapping

These tools are *read-only*: they do not mutate any data.
"""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

from app.ai.framework.context import AgentContext
from app.ai.framework.tool_def import tool
from app.ai.framework.tool_registry import registry
from app.models.boq_item import BoqItem
from app.models.line_item_quota_binding import LineItemQuotaBinding
from app.models.material_price import MaterialPrice
from app.models.quota_item import QuotaItem
from app.models.quota_resource_detail import QuotaResourceDetail
from app.models.quota_resource_material_mapping import QuotaResourceMaterialMapping


# ---------------------------------------------------------------------------
# Internal aggregation helper
# ---------------------------------------------------------------------------


def _aggregate(ctx: AgentContext) -> dict[str, Any]:
    """Walk all bindings of the current project and collapse resource details."""
    db = ctx.db

    boq_items = (
        db.query(BoqItem)
        .filter(BoqItem.project_id == ctx.project_id)
        .all()
    )
    boq_qty_by_id = {b.id: float(b.quantity or 0) for b in boq_items}
    boq_ids = list(boq_qty_by_id.keys())
    if not boq_ids:
        return {"resources": [], "by_category": {}, "grand_total": 0.0,
                "boq_count": 0, "binding_count": 0}

    bindings = (
        db.query(LineItemQuotaBinding)
        .filter(LineItemQuotaBinding.boq_item_id.in_(boq_ids))
        .all()
    )
    if not bindings:
        return {"resources": [], "by_category": {}, "grand_total": 0.0,
                "boq_count": len(boq_ids), "binding_count": 0}

    quota_ids = {b.quota_item_id for b in bindings}
    details = (
        db.query(QuotaResourceDetail)
        .filter(QuotaResourceDetail.quota_item_id.in_(quota_ids))
        .all()
    )
    details_by_quota: dict[int, list[QuotaResourceDetail]] = defaultdict(list)
    for d in details:
        details_by_quota[d.quota_item_id].append(d)

    # Resolve material-price mappings for main materials
    main_detail_ids = {d.id for d in details if d.is_main_material}
    market_price_by_detail: dict[int, tuple[float, str]] = {}
    if main_detail_ids:
        mappings = (
            db.query(QuotaResourceMaterialMapping)
            .filter(QuotaResourceMaterialMapping.resource_detail_id.in_(main_detail_ids))
            .all()
        )
        mp_ids = {m.material_price_id for m in mappings}
        prices = {
            mp.id: mp.unit_price
            for mp in db.query(MaterialPrice).filter(MaterialPrice.id.in_(mp_ids)).all()
        }
        for m in mappings:
            if m.material_price_id in prices:
                market_price_by_detail[m.resource_detail_id] = (
                    prices[m.material_price_id], "信息价",
                )

    # Aggregate
    # Key: (category, resource_name, spec, unit)
    bucket: dict[tuple[str, str, str, str], dict[str, Any]] = {}

    for b in bindings:
        boq_qty = boq_qty_by_id.get(b.boq_item_id, 0.0)
        if boq_qty <= 0:
            continue
        coeff = float(b.coefficient or 1.0)
        for d in details_by_quota.get(b.quota_item_id, []):
            qty = float(d.quantity or 0) * coeff * boq_qty
            if qty == 0:
                continue
            if d.id in market_price_by_detail:
                price, src = market_price_by_detail[d.id]
            else:
                price, src = float(d.unit_price or 0), "定额基价"

            key = (d.category, d.resource_name, d.spec or "", d.unit or "")
            agg = bucket.get(key)
            if agg is None:
                agg = {
                    "category": d.category,
                    "resource_name": d.resource_name,
                    "spec": d.spec or "",
                    "unit": d.unit or "",
                    "total_quantity": 0.0,
                    "weighted_price_sum": 0.0,
                    "total_amount": 0.0,
                    "is_main_material": bool(d.is_main_material),
                    "price_sources": set(),
                }
                bucket[key] = agg
            agg["total_quantity"] += qty
            agg["weighted_price_sum"] += qty * price
            agg["total_amount"] += qty * price
            if d.is_main_material:
                agg["is_main_material"] = True
            agg["price_sources"].add(src)

    resources = []
    for agg in bucket.values():
        avg_price = (
            agg["weighted_price_sum"] / agg["total_quantity"]
            if agg["total_quantity"] > 0
            else 0.0
        )
        resources.append(
            {
                "category": agg["category"],
                "resource_name": agg["resource_name"],
                "spec": agg["spec"],
                "unit": agg["unit"],
                "total_quantity": round(agg["total_quantity"], 4),
                "avg_unit_price": round(avg_price, 2),
                "total_amount": round(agg["total_amount"], 2),
                "is_main_material": agg["is_main_material"],
                "price_sources": sorted(agg["price_sources"]),
            }
        )
    resources.sort(key=lambda r: r["total_amount"], reverse=True)

    by_cat: dict[str, dict[str, float]] = defaultdict(
        lambda: {"total_amount": 0.0, "item_count": 0},
    )
    for r in resources:
        by_cat[r["category"]]["total_amount"] += r["total_amount"]
        by_cat[r["category"]]["item_count"] += 1
    grand_total = round(sum(c["total_amount"] for c in by_cat.values()), 2)
    by_category = {
        cat: {
            "total_amount": round(c["total_amount"], 2),
            "item_count": int(c["item_count"]),
            "share": round(c["total_amount"] / grand_total, 4) if grand_total else 0.0,
        }
        for cat, c in by_cat.items()
    }

    return {
        "resources": resources,
        "by_category": by_category,
        "grand_total": grand_total,
        "boq_count": len(boq_ids),
        "binding_count": len(bindings),
    }


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@tool(
    name="aggregate_lmm_summary",
    description=(
        "返回当前项目的人材机汇总：按类别（人工/材料/机械）分组的总金额、占比、"
        "条目数；以及合计。无参数。"
    ),
    read_only=True,
)
def aggregate_lmm_summary(ctx: AgentContext) -> str:
    data = _aggregate(ctx)
    return json.dumps(
        {
            "project_id": ctx.project_id,
            "boq_count": data["boq_count"],
            "binding_count": data["binding_count"],
            "by_category": data["by_category"],
            "grand_total": data["grand_total"],
        },
        ensure_ascii=False,
    )


@tool(
    name="aggregate_lmm_by_resource",
    description=(
        "返回项目人材机明细：按资源粒度（人工种类/材料/机械型号）汇总总耗量、"
        "加权平均单价、金额，按金额降序。可按 category 过滤、限制 top_n。"
    ),
    read_only=True,
)
def aggregate_lmm_by_resource(
    ctx: AgentContext,
    *,
    category: str = "",
    top_n: int = 30,
) -> str:
    data = _aggregate(ctx)
    items = data["resources"]
    if category:
        items = [r for r in items if r["category"] == category]
    items = items[:max(1, top_n)]
    return json.dumps(
        {
            "project_id": ctx.project_id,
            "category_filter": category or "(全部)",
            "total_resources": len(items),
            "grand_total": data["grand_total"],
            "resources": items,
        },
        ensure_ascii=False,
    )


@tool(
    name="find_main_materials",
    description=(
        "列出项目所有主材（is_main_material=true），并标注是否已挂接信息价。"
        "未挂接信息价的主材会被高亮，便于运维补全市场价。可按金额阈值 min_amount 过滤。"
    ),
    read_only=True,
)
def find_main_materials(
    ctx: AgentContext,
    *,
    min_amount: float = 0.0,
) -> str:
    data = _aggregate(ctx)
    mains = [r for r in data["resources"] if r["is_main_material"]]
    if min_amount > 0:
        mains = [r for r in mains if r["total_amount"] >= min_amount]

    needs_market_price = [
        r for r in mains if "信息价" not in r["price_sources"]
    ]
    return json.dumps(
        {
            "project_id": ctx.project_id,
            "main_material_count": len(mains),
            "needs_market_price_count": len(needs_market_price),
            "main_materials": mains,
            "needs_market_price_top": needs_market_price[:20],
            "guidance": (
                "needs_market_price 内的主材尚未挂接信息价（用的是定额基价），"
                "建议运维 / Agent 用 get_material_prices 查询并补建映射；"
                "金额越大优先级越高。"
            ),
        },
        ensure_ascii=False,
    )


# ── Register ──

registry.register_many(
    aggregate_lmm_summary,
    aggregate_lmm_by_resource,
    find_main_materials,
)
