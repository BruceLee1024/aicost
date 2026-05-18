"""Project lifecycle tools — create project, batch-create BOQ items,
recognize drawings, and run project-level calculations.

These tools enable the ProjectSetupAgent and FullPipelineAgent to
drive the entire workflow from project creation to cost calculation.
"""

from __future__ import annotations

import json
from typing import Any

from app.ai.framework.context import AgentContext
from app.ai.framework.tool_def import tool
from app.ai.framework.tool_registry import registry
from app.models.boq_item import BoqItem
from app.models.project import Project


# ────────────────────────────────────────────────
# Project creation
# ────────────────────────────────────────────────


@tool(
    name="create_project",
    description=(
        "创建一个新项目。返回新项目的 id。"
        "必需参数: name, region。可选: description, project_type, budget, "
        "standard_type(GB50500|HKSMM4), language(zh|en|bilingual), currency(CNY|HKD)。"
    ),
    destructive=True,
    requires_confirmation=True,
)
def create_project(
    ctx: AgentContext,
    *,
    name: str,
    region: str,
    description: str = "",
    project_type: str = "住宅",
    budget: float = 0,
    standard_type: str = "GB50500",
    language: str = "zh",
    currency: str = "CNY",
) -> str:
    # Guard: prevent duplicate names in same region
    exists = (
        ctx.db.query(Project.id)
        .filter(Project.name == name.strip(), Project.region == region.strip())
        .first()
    )
    if exists:
        return json.dumps(
            {"warning": "同名同地区项目已存在", "existing_project_id": exists[0]},
            ensure_ascii=False,
        )

    project = Project(
        name=name.strip(),
        region=region.strip(),
        description=description.strip() or None,
        project_type=project_type,
        budget=budget or None,
        standard_type=standard_type,
        language=language,
        currency=currency,
    )
    ctx.db.add(project)
    ctx.db.commit()
    ctx.db.refresh(project)

    # Auto-update context so subsequent tools can use the new project_id
    ctx.project_id = project.id
    ctx.metadata["standard_type"] = project.standard_type

    return json.dumps(
        {
            "action": "created",
            "project_id": project.id,
            "name": project.name,
            "region": project.region,
            "standard_type": project.standard_type,
            "currency": project.currency,
        },
        ensure_ascii=False,
    )


# ────────────────────────────────────────────────
# Batch BOQ creation
# ────────────────────────────────────────────────


@tool(
    name="batch_create_boq_items",
    description=(
        "批量创建清单项并写入项目。参数 items 是 JSON 数组，每项包含: "
        "code(编码), name(名称), unit(单位), quantity(工程量), "
        "division(分部,可选), characteristics(特征,可选)。"
        "返回创建数量和 id 列表。"
    ),
    destructive=True,
    requires_confirmation=True,
)
def batch_create_boq_items(
    ctx: AgentContext,
    *,
    items: str,
) -> str:
    """Accept a JSON-encoded list of BOQ item dicts and insert them."""
    MAX_ITEMS = 200  # safety limit

    try:
        item_list = json.loads(items) if isinstance(items, str) else items
    except (json.JSONDecodeError, TypeError) as e:
        return json.dumps({"error": f"items 参数 JSON 解析失败: {e}"}, ensure_ascii=False)

    if not isinstance(item_list, list) or len(item_list) == 0:
        return json.dumps({"error": "items 必须是非空数组"}, ensure_ascii=False)

    if len(item_list) > MAX_ITEMS:
        return json.dumps(
            {"error": f"单次最多创建 {MAX_ITEMS} 项，当前 {len(item_list)} 项，请分批调用"},
            ensure_ascii=False,
        )

    # Determine next sort_order
    max_sort = (
        ctx.db.query(BoqItem.sort_order)
        .filter(BoqItem.project_id == ctx.project_id)
        .order_by(BoqItem.sort_order.desc())
        .first()
    )
    next_sort = (max_sort[0] + 1) if max_sort and max_sort[0] is not None else 1

    # Detect duplicate codes within this batch + existing
    existing_codes = set()
    rows = (
        ctx.db.query(BoqItem.code)
        .filter(BoqItem.project_id == ctx.project_id)
        .all()
    )
    for (c,) in rows:
        existing_codes.add(c)

    created_ids = []
    errors = []
    division_counter: dict[str, int] = {}

    for i, raw in enumerate(item_list):
        if not isinstance(raw, dict):
            errors.append(f"第 {i} 项不是对象")
            continue
        name = raw.get("name", "").strip()
        code = raw.get("code", "").strip()
        unit = raw.get("unit", "").strip()
        if not name:
            errors.append(f"第 {i} 项缺少 name")
            continue

        # De-dup: skip if code already exists
        final_code = code or f"AUTO-{next_sort:04d}"
        if final_code in existing_codes:
            errors.append(f"第 {i} 项编码 {final_code} 已存在，已跳过")
            continue
        existing_codes.add(final_code)

        division = raw.get("division", "") or ""
        division_counter[division or "未分类"] = division_counter.get(division or "未分类", 0) + 1

        boq = BoqItem(
            project_id=ctx.project_id,
            code=final_code,
            name=name,
            unit=unit or "项",
            quantity=float(raw.get("quantity", 0) or 0),
            division=division,
            characteristics=raw.get("characteristics", "") or "",
            remark=raw.get("remark", "") or "",
            sort_order=next_sort,
        )
        ctx.db.add(boq)
        ctx.db.flush()  # get id
        created_ids.append(boq.id)
        next_sort += 1

    ctx.db.commit()

    return json.dumps(
        {
            "action": "batch_created",
            "created_count": len(created_ids),
            "created_ids": created_ids,
            "division_summary": division_counter,
            "errors": errors,
            "project_id": ctx.project_id,
        },
        ensure_ascii=False,
    )


# ────────────────────────────────────────────────
# Drawing recognition (wraps existing service)
# ────────────────────────────────────────────────


@tool(
    name="recognize_drawing_tool",
    description=(
        "识别工程图纸中的构件并返回 BOQ 建议。"
        "参数 image_base64 为图片的 base64 编码字符串，"
        "project_context 为可选的项目上下文描述。"
        "返回识别到的构件列表和 BOQ 建议。"
    ),
    read_only=True,
)
def recognize_drawing_tool(
    ctx: AgentContext,
    *,
    image_base64: str,
    project_context: str = "",
) -> str:
    import base64

    try:
        from app.services.drawing_recognition_service import (
            components_to_boq_suggestions,
            recognize_drawing,
        )
    except ImportError:
        return json.dumps({"error": "drawing_recognition_service 不可用"}, ensure_ascii=False)

    try:
        image_bytes = base64.b64decode(image_base64)
    except Exception:
        return json.dumps({"error": "image_base64 解码失败"}, ensure_ascii=False)

    result = recognize_drawing(
        image_bytes=image_bytes,
        content_type="image/png",
        project_context=project_context,
    )

    suggestions = components_to_boq_suggestions(result.components) if result.components else []

    return json.dumps(
        {
            "drawing_type": result.drawing_type,
            "summary": result.summary,
            "components": [
                {
                    "id": c.id,
                    "type": c.type,
                    "count": c.count,
                    "spec": c.spec,
                    "confidence": c.confidence,
                    "material": c.material,
                    "unit": c.unit,
                    "quantity_estimate": c.quantity_estimate,
                }
                for c in (result.components or [])
            ],
            "boq_suggestions": suggestions[:30],
            "error": result.error,
        },
        ensure_ascii=False,
    )


# ────────────────────────────────────────────────
# Batch project calculation
# ────────────────────────────────────────────────


@tool(
    name="batch_calculate_project",
    description=(
        "对当前项目执行全量计算：遍历所有已绑定定额的清单项，"
        "计算综合单价和合价，写入 calc_result 表。"
        "返回计算汇总（总价、分部合计、成功/失败数）。"
    ),
    destructive=True,
)
def batch_calculate_project(ctx: AgentContext) -> str:
    from app.services.project_calc_service import run_project_calculation

    try:
        summary, line_results = run_project_calculation(
            project_id=ctx.project_id, db=ctx.db,
        )
    except Exception as e:
        return json.dumps({"error": f"计算失败: {e}"}, ensure_ascii=False)

    lines_out = []
    for boq, result in line_results:
        lines_out.append({
            "boq_item_id": boq.id,
            "code": boq.code,
            "name": boq.name,
            "total": result.total,
        })

    return json.dumps(
        {
            "action": "calculated",
            "calculated_items": len(line_results),
            "grand_total": summary.grand_total,
            "total_direct": summary.total_direct,
            "total_management": summary.total_management,
            "total_profit": summary.total_profit,
            "total_tax": summary.total_tax,
            "total_measures": summary.total_measures,
            "line_results": lines_out[:50],
        },
        ensure_ascii=False,
    )


@tool(
    name="recalculate_dirty",
    description=(
        "增量重算：只重新计算 is_dirty=1 的清单项（绑定修改后自动标脏）。"
        "比 batch_calculate_project 快，适合绑定后局部更新。返回重算数量和总价。"
    ),
    destructive=True,
)
def recalculate_dirty(ctx: AgentContext) -> str:
    from app.services.project_calc_service import run_project_calculation

    # Count dirty before recalc
    dirty_count = ctx.db.query(BoqItem).filter(
        BoqItem.project_id == ctx.project_id, BoqItem.is_dirty == 1,
    ).count()

    if dirty_count == 0:
        return json.dumps({"message": "无需重算，所有清单项均为最新", "dirty_count": 0}, ensure_ascii=False)

    try:
        summary, line_results = run_project_calculation(
            project_id=ctx.project_id, db=ctx.db, incremental=True,
        )
    except Exception as e:
        return json.dumps({"error": f"增量计算失败: {e}"}, ensure_ascii=False)

    return json.dumps({
        "action": "incremental_recalculated",
        "dirty_recalculated": dirty_count,
        "total_items_in_result": len(line_results),
        "grand_total": summary.grand_total,
        "total_direct": summary.total_direct,
        "message": f"已增量重算 {dirty_count} 个脏项，总价 ¥{summary.grand_total:,.2f}",
    }, ensure_ascii=False)


@tool(
    name="update_boq_item",
    description=(
        "修改已有清单项的属性（名称、单位、工程量、分部、项目特征、备注等）。"
        "只传需要修改的字段，未传字段保持不变。必须传 boq_item_id。"
    ),
    destructive=True,
    requires_confirmation=True,
)
def update_boq_item(
    ctx: AgentContext,
    *,
    boq_item_id: int,
    name: str = "",
    unit: str = "",
    quantity: float | None = None,
    division: str = "",
    characteristics: str = "",
    remark: str = "",
    code: str = "",
) -> str:
    """Update fields on an existing BOQ item."""
    item = ctx.db.query(BoqItem).filter(
        BoqItem.id == boq_item_id, BoqItem.project_id == ctx.project_id,
    ).first()
    if not item:
        return json.dumps({"error": f"清单项 {boq_item_id} 不存在"}, ensure_ascii=False)

    updated_fields: list[str] = []
    if name:
        item.name = name
        updated_fields.append("name")
    if unit:
        item.unit = unit
        updated_fields.append("unit")
    if quantity is not None:
        item.quantity = quantity
        updated_fields.append("quantity")
    if division:
        item.division = division
        updated_fields.append("division")
    if characteristics:
        item.characteristics = characteristics
        updated_fields.append("characteristics")
    if remark:
        item.remark = remark
        updated_fields.append("remark")
    if code:
        item.code = code
        updated_fields.append("code")

    if not updated_fields:
        return json.dumps({"message": "未提供需要修改的字段"}, ensure_ascii=False)

    item.is_dirty = 1
    ctx.db.commit()
    return json.dumps({
        "action": "updated",
        "boq_item_id": item.id,
        "updated_fields": updated_fields,
        "current": {
            "code": item.code, "name": item.name, "unit": item.unit,
            "quantity": item.quantity, "division": item.division,
        },
        "message": f"已更新清单项 [{item.code}] 的 {', '.join(updated_fields)}",
    }, ensure_ascii=False)


@tool(
    name="delete_boq_items",
    description="批量删除清单项（按ID列表）。同时清理关联的绑定和计算结果。",
    destructive=True,
    requires_confirmation=True,
)
def delete_boq_items(
    ctx: AgentContext,
    *,
    boq_item_ids: list[int],
) -> str:
    """Delete BOQ items and their related bindings/calc results."""
    from app.models.line_item_quota_binding import LineItemQuotaBinding
    from app.models.calc_result import CalcResult

    items = ctx.db.query(BoqItem).filter(
        BoqItem.id.in_(boq_item_ids), BoqItem.project_id == ctx.project_id,
    ).all()
    if not items:
        return json.dumps({"error": "未找到匹配的清单项"}, ensure_ascii=False)

    found_ids = [i.id for i in items]
    # Cascade delete bindings and calc results
    ctx.db.query(LineItemQuotaBinding).filter(
        LineItemQuotaBinding.boq_item_id.in_(found_ids)
    ).delete(synchronize_session="fetch")
    ctx.db.query(CalcResult).filter(
        CalcResult.boq_item_id.in_(found_ids)
    ).delete(synchronize_session="fetch")
    for item in items:
        ctx.db.delete(item)
    ctx.db.commit()

    return json.dumps({
        "action": "deleted",
        "deleted_count": len(found_ids),
        "deleted_ids": found_ids,
        "message": f"已删除 {len(found_ids)} 个清单项及其关联数据",
    }, ensure_ascii=False)


# ────────────────────────────────────────────────
# Sprint 9 — Phase 2: Draft (propose) instead of direct write
# ────────────────────────────────────────────────


@tool(
    name="propose_boq_items",
    description=(
        "提议清单草稿（不写入数据库）。用法与 batch_create_boq_items 相同，"
        "但仅生成草稿供用户预览/编辑/确认。前端会把草稿渲染成可编辑表格，"
        "用户确认后再调用 batch_create_boq_items 写入。"
        "参数 items 是 JSON 数组，每项含: code, name, unit, quantity, division, characteristics。"
        "返回草稿 token、项数、按分部统计。**用户已要求草稿确认流程时优先用本工具**。"
    ),
    read_only=True,  # cacheable — same items → same draft
)
def propose_boq_items(
    ctx: AgentContext,
    *,
    items: str,
) -> str:
    """Generate an editable BOQ draft. Stored on ctx.metadata for retrieval."""
    MAX_ITEMS = 200

    try:
        item_list = json.loads(items) if isinstance(items, str) else items
    except (json.JSONDecodeError, TypeError) as e:
        return json.dumps({"error": f"items 参数 JSON 解析失败: {e}"}, ensure_ascii=False)

    if not isinstance(item_list, list) or len(item_list) == 0:
        return json.dumps({"error": "items 必须是非空数组"}, ensure_ascii=False)

    if len(item_list) > MAX_ITEMS:
        return json.dumps(
            {"error": f"单次最多草拟 {MAX_ITEMS} 项，当前 {len(item_list)} 项，请分批"},
            ensure_ascii=False,
        )

    # Normalize each item (no DB writes)
    cleaned: list[dict[str, Any]] = []
    division_counter: dict[str, int] = {}
    errors: list[str] = []

    for i, raw in enumerate(item_list):
        if not isinstance(raw, dict):
            errors.append(f"第 {i} 项不是对象")
            continue
        name = (raw.get("name") or "").strip()
        if not name:
            errors.append(f"第 {i} 项缺少 name")
            continue
        code = (raw.get("code") or "").strip() or f"AUTO-{i + 1:04d}"
        unit = (raw.get("unit") or "").strip() or "项"
        try:
            quantity = float(raw.get("quantity", 0) or 0)
        except (TypeError, ValueError):
            quantity = 0.0
        division = (raw.get("division") or "").strip()
        cleaned.append(
            {
                "draft_id": f"d{i + 1}",
                "code": code,
                "name": name,
                "unit": unit,
                "quantity": quantity,
                "division": division,
                "characteristics": (raw.get("characteristics") or "").strip(),
                "remark": (raw.get("remark") or "").strip(),
            }
        )
        division_counter[division or "未分类"] = (
            division_counter.get(division or "未分类", 0) + 1
        )

    # Persist to ctx.metadata (per-run) AND the process-level draft store
    # so a separate HTTP request from the BoqDraftEditor can retrieve it
    # after the orchestrator thread terminates.
    draft_token = f"draft_{ctx.project_id or 0}_{len(cleaned)}_{hash(json.dumps(cleaned, sort_keys=True)) & 0xFFFFFFFF:08x}"
    ctx.metadata.setdefault("boq_drafts", {})[draft_token] = cleaned
    from app.ai.framework.draft_store import get_draft_store
    get_draft_store().put(draft_token, ctx.project_id or 0, cleaned)

    return json.dumps(
        {
            "action": "drafted",
            "draft_token": draft_token,
            "draft_count": len(cleaned),
            "division_summary": division_counter,
            "errors": errors,
            "preview": cleaned[:5],
            "next_step": (
                "请告诉用户草稿已就绪，前端将弹出编辑器。"
                "用户编辑确认后会触发 batch_create_boq_items 写入。"
                "你的最终回复应说明分部数量与总条数，**不要再调任何工具**。"
            ),
        },
        ensure_ascii=False,
    )


# ────────────────────────────────────────────────
# Register
# ────────────────────────────────────────────────

registry.register_many(
    create_project,
    batch_create_boq_items,
    propose_boq_items,
    recognize_drawing_tool,
    batch_calculate_project,
    recalculate_dirty,
    update_boq_item,
    delete_boq_items,
)
