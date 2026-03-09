"""Snapshot & diff service."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.boq_item import BoqItem
from app.models.snapshot import Snapshot
from app.services.project_calc_service import run_project_calculation


# ---------------------------------------------------------------------------
# Create snapshot
# ---------------------------------------------------------------------------

def create_snapshot(
    project_id: int,
    label: str,
    db: Session,
) -> Snapshot:
    """Run calculation, persist results as a snapshot."""
    from app.models.line_item_quota_binding import LineItemQuotaBinding
    from app.models.quota_item import QuotaItem
    from app.services.project_calc_service import _lookup_price, _resolve_fee_config
    from app.models.project import Project

    summary, line_results = run_project_calculation(project_id=project_id, db=db)

    project = db.query(Project).filter(Project.id == project_id).first()
    region = project.region if project else ""
    fee_config = _resolve_fee_config(project_id, db)

    line_data = []
    for boq, result in line_results:
        # Capture binding/quota snapshot for diff attribution
        bindings = (
            db.query(LineItemQuotaBinding)
            .filter(LineItemQuotaBinding.boq_item_id == boq.id)
            .all()
        )
        binding_snap = []
        for b in bindings:
            q = db.query(QuotaItem).filter(QuotaItem.id == b.quota_item_id).first()
            if q:
                binding_snap.append({
                    "quota_code": q.quota_code,
                    "coefficient": b.coefficient,
                    "labor_qty": q.labor_qty,
                    "material_qty": q.material_qty,
                    "machine_qty": q.machine_qty,
                })

        line_data.append({
            "boq_item_id": boq.id,
            "code": boq.code,
            "name": boq.name,
            "unit": boq.unit,
            "quantity": boq.quantity,
            "direct_cost": result.direct_cost,
            "management_fee": result.management_fee,
            "profit": result.profit,
            "regulatory_fee": result.regulatory_fee,
            "pre_tax_total": result.pre_tax_total,
            "tax": result.tax,
            "total": result.total,
            # Attribution metadata
            "bindings": binding_snap,
        })

    snapshot_data = {
        "summary": {
            "total_direct": summary.total_direct,
            "total_management": summary.total_management,
            "total_profit": summary.total_profit,
            "total_regulatory": summary.total_regulatory,
            "total_pre_tax": summary.total_pre_tax,
            "total_tax": summary.total_tax,
            "grand_total": summary.grand_total,
        },
        "lines": line_data,
        "prices": {
            "labor": _lookup_price(db, category="人工费", region=region),
            "material": _lookup_price(db, category="材料费", region=region),
            "machine": _lookup_price(db, category="机械费", region=region),
        },
        "fee_config": {
            "management_rate": fee_config.management_rate,
            "profit_rate": fee_config.profit_rate,
            "regulatory_rate": fee_config.regulatory_rate,
            "tax_rate": fee_config.tax_rate,
        },
    }

    # Mark all boq items as clean
    boq_items = db.query(BoqItem).filter(BoqItem.project_id == project_id).all()
    for item in boq_items:
        item.is_dirty = 0

    snap = Snapshot(
        project_id=project_id,
        label=label,
        created_at=datetime.now(timezone.utc).isoformat(),
        grand_total=summary.grand_total,
        data_json=json.dumps(snapshot_data, ensure_ascii=False),
    )
    db.add(snap)
    db.commit()
    db.refresh(snap)
    return snap


# ---------------------------------------------------------------------------
# Diff two snapshots
# ---------------------------------------------------------------------------

@dataclass
class ChangeAttribution:
    """Multi-dimensional attribution of a line item change."""
    quantity_change: bool = False  # 工程量变化
    quota_change: bool = False  # 定额绑定/系数变化
    material_price_change: bool = False  # 材料价格变化
    fee_rate_change: bool = False  # 费率变化
    reasons: list[str] = field(default_factory=list)


@dataclass
class LineDiff:
    boq_code: str
    boq_name: str
    change_type: str  # "added" | "removed" | "modified" | "unchanged"
    old_total: float | None
    new_total: float | None
    delta: float
    attribution: ChangeAttribution | None = None


@dataclass
class DiffReport:
    snapshot_a_id: int
    snapshot_b_id: int
    old_grand_total: float
    new_grand_total: float
    grand_total_delta: float
    lines: list[LineDiff]
    price_changed: bool = False
    fee_rate_changed: bool = False


def generate_diff_explanation(report: "DiffReport") -> str:
    """Generate a natural-language explanation of the diff (rule-based, no LLM)."""
    parts: list[str] = []

    added = [l for l in report.lines if l.change_type == "added"]
    removed = [l for l in report.lines if l.change_type == "removed"]
    modified = [l for l in report.lines if l.change_type == "modified"]
    unchanged = [l for l in report.lines if l.change_type == "unchanged"]

    total_lines = len(report.lines)
    parts.append(f"共 {total_lines} 条清单项：")

    if added:
        parts.append(f"新增 {len(added)} 项（{', '.join(l.boq_name for l in added[:3])}{'等' if len(added) > 3 else ''}）")
    if removed:
        parts.append(f"删除 {len(removed)} 项（{', '.join(l.boq_name for l in removed[:3])}{'等' if len(removed) > 3 else ''}）")
    if modified:
        parts.append(f"变更 {len(modified)} 项")
        # Top 3 by absolute delta
        top = sorted(modified, key=lambda l: abs(l.delta), reverse=True)[:3]
        for l in top:
            sign = "+" if l.delta > 0 else ""
            parts.append(f"  · {l.boq_name}：{l.old_total} → {l.new_total}（{sign}{l.delta}）")
    if unchanged:
        parts.append(f"未变 {len(unchanged)} 项")

    delta = report.grand_total_delta
    sign = "+" if delta > 0 else ""
    parts.append(f"总价变动：{report.old_grand_total} → {report.new_grand_total}（{sign}{delta}）")

    return "\n".join(parts)


def _attribute_change(la: dict, lb: dict, price_changed: bool, fee_changed: bool) -> ChangeAttribution:
    """Determine *why* a line item's total changed."""
    attr = ChangeAttribution()
    reasons = []

    # Quantity change?
    if la.get("quantity", 0) != lb.get("quantity", 0):
        attr.quantity_change = True
        reasons.append(
            f"工程量: {la.get('quantity',0)} → {lb.get('quantity',0)}"
        )

    # Quota binding change?
    old_bindings = la.get("bindings", [])
    new_bindings = lb.get("bindings", [])
    old_codes = {b["quota_code"]: b for b in old_bindings}
    new_codes = {b["quota_code"]: b for b in new_bindings}
    if set(old_codes.keys()) != set(new_codes.keys()):
        attr.quota_change = True
        added = set(new_codes.keys()) - set(old_codes.keys())
        removed = set(old_codes.keys()) - set(new_codes.keys())
        if added:
            reasons.append(f"新增定额: {', '.join(added)}")
        if removed:
            reasons.append(f"删除定额: {', '.join(removed)}")
    else:
        for code in old_codes:
            ob, nb = old_codes[code], new_codes.get(code, {})
            if (ob.get("coefficient") != nb.get("coefficient")
                    or ob.get("labor_qty") != nb.get("labor_qty")
                    or ob.get("material_qty") != nb.get("material_qty")
                    or ob.get("machine_qty") != nb.get("machine_qty")):
                attr.quota_change = True
                reasons.append(f"定额 {code} 参数变化")
                break

    if price_changed:
        attr.material_price_change = True
        reasons.append("材料价格变动")

    if fee_changed:
        attr.fee_rate_change = True
        reasons.append("费率变动")

    if not reasons:
        reasons.append("计算精度/进位差异")

    attr.reasons = reasons
    return attr


def diff_snapshots(snap_a: Snapshot, snap_b: Snapshot) -> DiffReport:
    """Compare two snapshots and produce a structured diff with change attribution."""
    data_a = json.loads(snap_a.data_json)
    data_b = json.loads(snap_b.data_json)

    lines_a = {line["boq_item_id"]: line for line in data_a.get("lines", [])}
    lines_b = {line["boq_item_id"]: line for line in data_b.get("lines", [])}

    # Detect global price/fee changes
    prices_a = data_a.get("prices", {})
    prices_b = data_b.get("prices", {})
    price_changed = prices_a != prices_b and bool(prices_a) and bool(prices_b)

    fees_a = data_a.get("fee_config", {})
    fees_b = data_b.get("fee_config", {})
    fee_changed = fees_a != fees_b and bool(fees_a) and bool(fees_b)

    all_ids = set(lines_a.keys()) | set(lines_b.keys())
    diffs: list[LineDiff] = []

    for bid in sorted(all_ids):
        la = lines_a.get(bid)
        lb = lines_b.get(bid)

        if la and not lb:
            diffs.append(LineDiff(
                boq_code=la["code"], boq_name=la["name"],
                change_type="removed",
                old_total=la["total"], new_total=None,
                delta=-la["total"],
            ))
        elif lb and not la:
            diffs.append(LineDiff(
                boq_code=lb["code"], boq_name=lb["name"],
                change_type="added",
                old_total=None, new_total=lb["total"],
                delta=lb["total"],
            ))
        else:
            assert la is not None and lb is not None
            delta = round(lb["total"] - la["total"], 2)
            change_type = "modified" if delta != 0 else "unchanged"
            attribution = (
                _attribute_change(la, lb, price_changed, fee_changed)
                if change_type == "modified" else None
            )
            diffs.append(LineDiff(
                boq_code=la["code"], boq_name=la["name"],
                change_type=change_type,
                old_total=la["total"], new_total=lb["total"],
                delta=delta,
                attribution=attribution,
            ))

    sum_a = data_a.get("summary", {}).get("grand_total", 0)
    sum_b = data_b.get("summary", {}).get("grand_total", 0)

    return DiffReport(
        snapshot_a_id=snap_a.id,
        snapshot_b_id=snap_b.id,
        old_grand_total=sum_a,
        new_grand_total=sum_b,
        grand_total_delta=round(sum_b - sum_a, 2),
        lines=diffs,
        price_changed=price_changed,
        fee_rate_changed=fee_changed,
    )
