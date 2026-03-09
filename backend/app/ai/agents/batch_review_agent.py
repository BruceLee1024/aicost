"""Batch Review Agent — scans all project bindings and produces audit report.

Checks for:
- Missing bindings (unbound BOQ items)
- Unit mismatches between BOQ and quota
- Abnormal coefficients (too high or too low)
- Duplicate bindings
- Zero-consumption quotas
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.ai.providers import AIProviderError, get_ai_provider
from app.db.session import get_db
from app.models.boq_item import BoqItem
from app.models.line_item_quota_binding import LineItemQuotaBinding
from app.models.project import Project
from app.models.quota_item import QuotaItem
from app.services.validation_service import normalize_unit

logger = logging.getLogger(__name__)


@dataclass
class ReviewIssue:
    boq_item_id: int
    boq_code: str
    boq_name: str
    severity: str  # "error" | "warning" | "info"
    issue_type: str  # "unbound" | "unit_mismatch" | "coeff_abnormal" | "zero_consumption" | "duplicate"
    message: str
    suggestion: str = ""


@dataclass
class BatchReviewResult:
    project_id: int
    total_items: int
    bound_count: int
    unbound_count: int
    issues: list[ReviewIssue] = field(default_factory=list)
    ai_summary: str | None = None
    error: str | None = None


def run_batch_review(*, project_id: int) -> BatchReviewResult:
    """Scan all project bindings and produce an audit report."""
    db: Session = next(get_db())
    try:
        return _review(db, project_id)
    finally:
        db.close()


def _review(db: Session, project_id: int) -> BatchReviewResult:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return BatchReviewResult(
            project_id=project_id, total_items=0, bound_count=0, unbound_count=0,
            error="project_not_found",
        )

    boq_items = (
        db.query(BoqItem)
        .filter(BoqItem.project_id == project_id)
        .order_by(BoqItem.sort_order, BoqItem.id)
        .all()
    )
    if not boq_items:
        return BatchReviewResult(
            project_id=project_id, total_items=0, bound_count=0, unbound_count=0,
        )

    boq_ids = [b.id for b in boq_items]
    bindings = (
        db.query(LineItemQuotaBinding)
        .filter(LineItemQuotaBinding.boq_item_id.in_(boq_ids))
        .all()
    )

    # Build lookup maps
    binding_map: dict[int, list[LineItemQuotaBinding]] = {}
    for b in bindings:
        binding_map.setdefault(b.boq_item_id, []).append(b)

    quota_ids = {b.quota_item_id for b in bindings}
    quotas = {q.id: q for q in db.query(QuotaItem).filter(QuotaItem.id.in_(quota_ids)).all()} if quota_ids else {}

    issues: list[ReviewIssue] = []
    bound_count = 0

    for boq in boq_items:
        item_bindings = binding_map.get(boq.id, [])

        if not item_bindings:
            issues.append(ReviewIssue(
                boq_item_id=boq.id, boq_code=boq.code, boq_name=boq.name,
                severity="warning", issue_type="unbound",
                message=f"清单项 [{boq.code}] {boq.name} 尚未绑定定额",
                suggestion="建议使用AI匹配或手动搜索绑定合适的定额",
            ))
            continue

        bound_count += 1

        # Check each binding
        seen_quota_ids: set[int] = set()
        for b in item_bindings:
            q = quotas.get(b.quota_item_id)
            if not q:
                issues.append(ReviewIssue(
                    boq_item_id=boq.id, boq_code=boq.code, boq_name=boq.name,
                    severity="error", issue_type="missing_quota",
                    message=f"绑定的定额ID {b.quota_item_id} 不存在",
                    suggestion="请解绑并重新匹配定额",
                ))
                continue

            # Duplicate binding check
            if q.id in seen_quota_ids:
                issues.append(ReviewIssue(
                    boq_item_id=boq.id, boq_code=boq.code, boq_name=boq.name,
                    severity="warning", issue_type="duplicate",
                    message=f"定额 [{q.quota_code}] {q.name} 被重复绑定",
                    suggestion="如非组合定额需要，建议删除重复绑定",
                ))
            seen_quota_ids.add(q.id)

            # Unit mismatch
            if normalize_unit(boq.unit) != normalize_unit(q.unit):
                issues.append(ReviewIssue(
                    boq_item_id=boq.id, boq_code=boq.code, boq_name=boq.name,
                    severity="warning", issue_type="unit_mismatch",
                    message=f"清单单位 '{boq.unit}' 与定额 [{q.quota_code}] 单位 '{q.unit}' 不一致",
                    suggestion="请确认是否需要设置换算系数",
                ))

            # Coefficient abnormality
            if b.coefficient <= 0:
                issues.append(ReviewIssue(
                    boq_item_id=boq.id, boq_code=boq.code, boq_name=boq.name,
                    severity="error", issue_type="coeff_abnormal",
                    message=f"定额 [{q.quota_code}] 系数为 {b.coefficient}，不合理",
                    suggestion="系数应为正数，通常在 0.5~3.0 范围",
                ))
            elif b.coefficient > 5.0:
                issues.append(ReviewIssue(
                    boq_item_id=boq.id, boq_code=boq.code, boq_name=boq.name,
                    severity="warning", issue_type="coeff_abnormal",
                    message=f"定额 [{q.quota_code}] 系数 {b.coefficient} 偏高（>5.0）",
                    suggestion="请确认是否确实需要如此高的系数调整",
                ))

            # Zero consumption
            if q.labor_qty == 0 and q.material_qty == 0 and q.machine_qty == 0:
                issues.append(ReviewIssue(
                    boq_item_id=boq.id, boq_code=boq.code, boq_name=boq.name,
                    severity="warning", issue_type="zero_consumption",
                    message=f"定额 [{q.quota_code}] 人材机消耗量均为0",
                    suggestion="此定额可能缺少消耗量数据，请核实或更换定额",
                ))

    result = BatchReviewResult(
        project_id=project_id,
        total_items=len(boq_items),
        bound_count=bound_count,
        unbound_count=len(boq_items) - bound_count,
        issues=issues,
    )

    # Try to get AI summary
    result.ai_summary = _generate_ai_summary(result)
    return result


def _generate_ai_summary(result: BatchReviewResult) -> str | None:
    """Use AI to generate a human-readable summary of the review."""
    provider = get_ai_provider()
    if not provider.is_enabled() or not provider.is_configured():
        return None

    issue_data = [
        {"type": i.issue_type, "severity": i.severity, "message": i.message}
        for i in result.issues[:30]  # Limit context
    ]

    prompt = (
        f"项目共 {result.total_items} 个清单项，已绑定 {result.bound_count} 个，"
        f"未绑定 {result.unbound_count} 个。\n"
        f"发现 {len(result.issues)} 个问题：\n"
        f"{json.dumps(issue_data, ensure_ascii=False, indent=2)}\n\n"
        "请用2-3句话总结审查结果，给出改进建议。"
    )

    try:
        return provider.generate_text(
            task="batch_review_summary",
            messages=[
                {"role": "system", "content": "你是工程计价审查助手，请简洁总结审查报告。"},
                {"role": "user", "content": prompt},
            ],
        )
    except AIProviderError:
        return None
