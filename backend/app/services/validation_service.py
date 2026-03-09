"""Validation engine: structured checks on project data."""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from enum import Enum

from collections import Counter, defaultdict

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.boq_item import BoqItem
from app.models.boq_standard_code import BoqStandardCode
from app.models.line_item_quota_binding import LineItemQuotaBinding
from app.models.material_price import MaterialPrice
from app.models.project import Project
from app.models.quota_item import QuotaItem
from app.models.quota_resource_detail import QuotaResourceDetail


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationIssue:
    code: str
    severity: Severity
    boq_item_id: int | None
    message: str
    suggestion: str


def validate_project(project_id: int, db: Session) -> list[ValidationIssue]:
    """Run all validation rules for a project. Returns a list of issues."""
    issues: list[ValidationIssue] = []

    boq_items = db.query(BoqItem).filter(BoqItem.project_id == project_id).all()

    if not boq_items:
        issues.append(ValidationIssue(
            code="NO_BOQ_ITEMS",
            severity=Severity.ERROR,
            boq_item_id=None,
            message="项目无清单项",
            suggestion="请先导入清单",
        ))
        return issues

    project = db.query(Project).filter(Project.id == project_id).first()
    project_region = project.region if project else ""
    if project and not project.rule_package_id:
        issues.append(ValidationIssue(
            code="NO_RULE_PACKAGE",
            severity=Severity.WARNING,
            boq_item_id=None,
            message="项目未绑定规则包，将使用默认费率",
            suggestion="请绑定规则包以确保费率正确",
        ))

    code_counts = Counter(b.code for b in boq_items)
    dup_codes = {c for c, cnt in code_counts.items() if cnt > 1}
    for boq in boq_items:
        if boq.code in dup_codes:
            issues.append(ValidationIssue(
                code="DUPLICATE_CODE",
                severity=Severity.WARNING,
                boq_item_id=boq.id,
                message=f"编码 [{boq.code}] 在项目中重复出现",
                suggestion="请检查是否为同一清单项重复导入",
            ))

    boq_ids = [b.id for b in boq_items]
    bindings_by_boq: dict[int, list[LineItemQuotaBinding]] = defaultdict(list)
    quota_by_id: dict[int, QuotaItem] = {}
    if boq_ids:
        binding_rows = (
            db.query(LineItemQuotaBinding)
            .filter(LineItemQuotaBinding.boq_item_id.in_(boq_ids))
            .all()
        )
        for row in binding_rows:
            bindings_by_boq[row.boq_item_id].append(row)

        quota_ids = {b.quota_item_id for b in binding_rows}
        if quota_ids:
            quota_by_id = {
                q.id: q
                for q in db.query(QuotaItem).filter(QuotaItem.id.in_(quota_ids)).all()
            }

    for category in ["人工费", "材料费", "机械费"]:
        exists = (
            db.query(MaterialPrice)
            .filter(
                MaterialPrice.name == category,
                or_(MaterialPrice.region == project_region, MaterialPrice.region == ""),
            )
            .first()
        )
        if not exists:
            issues.append(ValidationIssue(
                code="MISSING_MATERIAL_PRICE",
                severity=Severity.WARNING,
                boq_item_id=None,
                message=f"材料价表缺少 [{category}] 记录，计算将使用默认单价 1.0",
                suggestion=f"请导入 {category} 的价格数据",
            ))

    for boq in boq_items:
        if boq.quantity <= 0:
            issues.append(ValidationIssue(
                code="ZERO_QUANTITY",
                severity=Severity.ERROR,
                boq_item_id=boq.id,
                message=f"[{boq.code}] {boq.name} 工程量为 {boq.quantity}",
                suggestion="请确认工程量是否正确",
            ))

        bindings = bindings_by_boq.get(boq.id, [])
        if not bindings:
            issues.append(ValidationIssue(
                code="NO_BINDING",
                severity=Severity.ERROR,
                boq_item_id=boq.id,
                message=f"[{boq.code}] {boq.name} 未绑定定额",
                suggestion="请为此清单项绑定定额子目",
            ))
            continue

        for b in bindings:
            quota = quota_by_id.get(b.quota_item_id)
            if quota and boq.unit.strip() != quota.unit.strip():
                issues.append(ValidationIssue(
                    code="UNIT_MISMATCH",
                    severity=Severity.WARNING,
                    boq_item_id=boq.id,
                    message=f"[{boq.code}] 清单单位 '{boq.unit}' 与定额 [{quota.quota_code}] 单位 '{quota.unit}' 不一致",
                    suggestion="请核实单位是否需要换算",
                ))

            if quota and quota.labor_qty == 0 and quota.material_qty == 0 and quota.machine_qty == 0:
                issues.append(ValidationIssue(
                    code="ZERO_QUOTA_CONTENT",
                    severity=Severity.WARNING,
                    boq_item_id=boq.id,
                    message=f"[{boq.code}] 绑定的定额 [{quota.quota_code}] 人材机含量均为 0",
                    suggestion="请确认定额数据是否完整",
                ))

    # ── Code compliance against standard BOQ codes ──
    std_codes = {sc.standard_code: sc for sc in db.query(BoqStandardCode).all()}
    if std_codes:
        for boq in boq_items:
            code_prefix = boq.code.split("-")[0].strip()  # handle variants like "010401001-001"
            match = std_codes.get(code_prefix)
            if not match:
                # Try fuzzy: first 9 digits
                match = std_codes.get(code_prefix[:9]) if len(code_prefix) >= 9 else None
            if match:
                if boq.unit.strip() != match.standard_unit.strip():
                    issues.append(ValidationIssue(
                        code="UNIT_STANDARD_MISMATCH",
                        severity=Severity.WARNING,
                        boq_item_id=boq.id,
                        message=(
                            f"[{boq.code}] 单位 '{boq.unit}' 与国标 '{match.standard_unit}' 不一致"
                        ),
                        suggestion=f"GB50500标准: {match.name} 应使用 {match.standard_unit}。"
                                   f"计量规则: {match.measurement_rule[:60] if match.measurement_rule else '—'}",
                    ))
                # Check missing characteristics
                if match.common_characteristics and not boq.characteristics.strip():
                    issues.append(ValidationIssue(
                        code="MISSING_CHARACTERISTICS",
                        severity=Severity.INFO,
                        boq_item_id=boq.id,
                        message=f"[{boq.code}] {boq.name} 缺少项目特征描述",
                        suggestion=f"标准项目特征模板:\n{match.common_characteristics}",
                    ))

    # ── Resource detail completeness check ──
    for boq in boq_items:
        bindings = bindings_by_boq.get(boq.id, [])
        for b in bindings:
            quota = quota_by_id.get(b.quota_item_id)
            if quota and getattr(quota, "has_resource_details", 0) == 1:
                detail_count = (
                    db.query(QuotaResourceDetail)
                    .filter(QuotaResourceDetail.quota_item_id == quota.id)
                    .count()
                )
                if detail_count == 0:
                    issues.append(ValidationIssue(
                        code="RESOURCE_DETAILS_DECLARED_BUT_EMPTY",
                        severity=Severity.ERROR,
                        boq_item_id=boq.id,
                        message=(
                            f"[{boq.code}] 定额 [{quota.quota_code}] 标记有人材机明细但数据为空"
                        ),
                        suggestion="请导入定额资源明细或取消has_resource_details标记",
                    ))

    # ── Price anomaly detection (cross-item outlier) ──
    _detect_price_anomalies(boq_items, bindings_by_boq, quota_by_id, issues)

    return issues


# ---------------------------------------------------------------------------
# Unit equivalence helpers
# ---------------------------------------------------------------------------
_UNIT_EQUIVALENCES: dict[str, set[str]] = {
    "m²": {"m2", "㎡", "平方米", "平米"},
    "m³": {"m3", "㎥", "立方米", "方"},
    "m": {"米", "延长米"},
    "t": {"吨", "T"},
    "kg": {"千克", "公斤", "Kg", "KG"},
    "个": {"只", "块", "套"},
    "台": {"台班"},
}


def normalize_unit(unit: str) -> str:
    """Return a canonical unit string for comparison."""
    u = unit.strip()
    for canonical, aliases in _UNIT_EQUIVALENCES.items():
        if u == canonical or u in aliases:
            return canonical
    return u


def _detect_price_anomalies(
    boq_items: list[BoqItem],
    bindings_by_boq: dict[int, list[LineItemQuotaBinding]],
    quota_by_id: dict[int, QuotaItem],
    issues: list[ValidationIssue],
) -> None:
    """Flag items whose unit-consumption is an outlier vs same-category peers.

    For each (division, unit) group, compute median labor/material/machine
    consumption. Items >3× or <⅓ of median are flagged.
    """
    # Group items by (division, unit) for peer comparison
    groups: dict[tuple[str, str], list[tuple[BoqItem, float, float, float]]] = defaultdict(list)
    for boq in boq_items:
        bindings = bindings_by_boq.get(boq.id, [])
        total_l = total_m = total_mc = 0.0
        for b in bindings:
            q = quota_by_id.get(b.quota_item_id)
            if q:
                coeff = getattr(b, "coefficient", 1.0) or 1.0
                total_l += q.labor_qty * coeff
                total_m += q.material_qty * coeff
                total_mc += q.machine_qty * coeff
        key = (boq.division or "_unknown_", normalize_unit(boq.unit))
        groups[key].append((boq, total_l, total_m, total_mc))

    for (_div, _unit), members in groups.items():
        if len(members) < 3:  # need ≥3 peers for meaningful comparison
            continue
        for idx, label in [(1, "人工"), (2, "材料"), (3, "机械")]:
            values = [m[idx] for m in members if m[idx] > 0]
            if len(values) < 3:
                continue
            med = statistics.median(values)
            if med == 0:
                continue
            for boq, *consumptions in members:
                val = consumptions[idx - 1]
                if val <= 0:
                    continue
                ratio = val / med
                if ratio > 3.0:
                    issues.append(ValidationIssue(
                        code="CONSUMPTION_ANOMALY_HIGH",
                        severity=Severity.WARNING,
                        boq_item_id=boq.id,
                        message=(
                            f"[{boq.code}] {label}消耗量 {val:.3f} 显著高于同类中位值 {med:.3f} ({ratio:.1f}×)"
                        ),
                        suggestion=f"请核实定额绑定和系数是否正确，同分部({_div})同单位({_unit})共 {len(members)} 项",
                    ))
                elif ratio < 1 / 3.0:
                    issues.append(ValidationIssue(
                        code="CONSUMPTION_ANOMALY_LOW",
                        severity=Severity.WARNING,
                        boq_item_id=boq.id,
                        message=(
                            f"[{boq.code}] {label}消耗量 {val:.3f} 显著低于同类中位值 {med:.3f} ({ratio:.1f}×)"
                        ),
                        suggestion=f"请核实定额绑定和系数是否正确，同分部({_div})同单位({_unit})共 {len(members)} 项",
                    ))
