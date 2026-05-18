"""Enterprise quota precipitation analyzer.

Scans all snapshots + active BOQ-quota bindings to discover frequently used
(BOQ code prefix, name, unit) clusters and generate ``EnterpriseQuotaCandidate``
rows with weighted-average suggestions.

Algorithm summary
-----------------
1. Iterate every Snapshot.data_json's ``lines`` and pull each line's
   ``bindings`` array (snapshot of which quotas were used).
2. Cluster key = (boq_code[:9], unit, name_canonical), where name_canonical
   strips numeric suffixes / whitespace / common punctuation.
3. For each cluster, accumulate:
     - sum_qty (line qty), sum_total (line total)
     - per quota: usage count, sum_coefficient, sum_labor_qty, etc.
4. Compute weighted means:
     - suggested_unit_price = Σ(line.total) / Σ(line.qty)
     - suggested_labor/material/machine_qty = weighted by usage frequency
       across the top quotas linked in this cluster
     - suggested_coefficient = mean coefficient
5. Compute confidence ∈ [0,1] from sample_count + dispersion + recency.
6. Upsert into EnterpriseQuotaCandidate (unique on the cluster key).
"""

from __future__ import annotations

import json
import re
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.boq_item import BoqItem
from app.models.enterprise_quota_candidate import (
    CANDIDATE_DISMISSED,
    CANDIDATE_PENDING,
    CANDIDATE_PROMOTED,
    EnterpriseQuotaCandidate,
)
from app.models.enterprise_quota_item import (
    SOURCE_PRECIPITATED,
    STATUS_DRAFT,
    EnterpriseQuotaItem,
)
from app.models.line_item_quota_binding import LineItemQuotaBinding
from app.models.quota_item import QuotaItem
from app.models.snapshot import Snapshot


MIN_SAMPLES = 3
MIN_CONFIDENCE = 0.4


# ─── Name canonicalisation ──────────────────────────────────────────


_PUNCT_RE = re.compile(r"[\s\u3000,，。、:：;；()（）\[\]【】<>《》\"'`~!@#$%^&*+=|\\/?]+")
_DIGITS_RE = re.compile(r"\d+(?:\.\d+)?")


def _canonical_name(name: str) -> str:
    """Strip whitespace/punctuation/numbers to produce a stable cluster key."""
    if not name:
        return ""
    s = _PUNCT_RE.sub("", name)
    s = _DIGITS_RE.sub("#", s)  # collapse numbers to placeholder
    return s[:120]


def _code_prefix(code: str) -> str:
    """First 9 chars of the BOQ code, padded if shorter."""
    return (code or "").strip()[:9]


# ─── Aggregator ──────────────────────────────────────────────────────


class _Cluster:
    __slots__ = (
        "boq_code_pattern", "name_canonical", "unit",
        "lines",  # list of (qty, total, project_id)
        "quota_usage",  # dict[quota_id] → list of dict(coefficient, labor_qty, ...)
        "project_ids",
    )

    def __init__(self, boq_code_pattern: str, name_canonical: str, unit: str) -> None:
        self.boq_code_pattern = boq_code_pattern
        self.name_canonical = name_canonical
        self.unit = unit
        self.lines: list[tuple[float, float, int]] = []
        self.quota_usage: dict[int, list[dict[str, float]]] = defaultdict(list)
        self.project_ids: set[int] = set()


def _ingest_snapshot(
    db: Session,
    snap: Snapshot,
    clusters: dict[tuple[str, str, str], _Cluster],
) -> int:
    """Parse one snapshot, mutate ``clusters``. Returns number of lines processed."""
    try:
        data = json.loads(snap.data_json or "{}")
    except (ValueError, TypeError):
        return 0
    lines = data.get("lines") or []

    boq_ids = [int(line.get("boq_item_id")) for line in lines if line.get("boq_item_id")]
    boq_rows = (
        db.query(BoqItem.id, BoqItem.code, BoqItem.name, BoqItem.unit)
        .filter(BoqItem.id.in_(boq_ids))
        .all()
        if boq_ids else []
    )
    boq_lookup = {row.id: row for row in boq_rows}

    line_count = 0
    for line in lines:
        boq_id = line.get("boq_item_id")
        bindings = line.get("bindings") or []
        if not boq_id or not bindings:
            continue
        boq_row = boq_lookup.get(int(boq_id))
        if not boq_row:
            continue

        code = boq_row.code or line.get("code") or ""
        name = boq_row.name or line.get("name") or ""
        unit = boq_row.unit or line.get("unit") or ""

        key = (_code_prefix(code), _canonical_name(name), unit.strip())
        if not key[0] or not key[1]:
            continue

        cluster = clusters.get(key)
        if cluster is None:
            cluster = _Cluster(*key)
            clusters[key] = cluster

        qty = float(line.get("quantity", 0) or 0)
        total = float(line.get("total", 0) or 0)
        cluster.lines.append((qty, total, snap.project_id))
        cluster.project_ids.add(snap.project_id)

        # Pull quota IDs by code (since snapshot stores quota_code, not id)
        for b in bindings:
            qcode = b.get("quota_code")
            if not qcode:
                continue
            quota = (
                db.query(QuotaItem.id, QuotaItem.labor_qty,
                         QuotaItem.material_qty, QuotaItem.machine_qty)
                .filter(QuotaItem.quota_code == qcode)
                .first()
            )
            if not quota:
                continue
            cluster.quota_usage[quota.id].append({
                "coefficient": float(b.get("coefficient", 1.0) or 1.0),
                "labor_qty": float(b.get("labor_qty", quota.labor_qty) or 0),
                "material_qty": float(b.get("material_qty", quota.material_qty) or 0),
                "machine_qty": float(b.get("machine_qty", quota.machine_qty) or 0),
            })
        line_count += 1
    return line_count


def _ingest_live_bindings(
    db: Session,
    clusters: dict[tuple[str, str, str], _Cluster],
) -> int:
    """Augment with current (non-snapshot) bindings — useful when no snapshots yet."""
    rows = (
        db.query(
            BoqItem.id, BoqItem.code, BoqItem.name, BoqItem.unit,
            BoqItem.quantity, BoqItem.project_id,
            LineItemQuotaBinding.quota_item_id, LineItemQuotaBinding.coefficient,
            QuotaItem.labor_qty, QuotaItem.material_qty, QuotaItem.machine_qty,
            QuotaItem.base_price,
        )
        .join(LineItemQuotaBinding, LineItemQuotaBinding.boq_item_id == BoqItem.id)
        .join(QuotaItem, QuotaItem.id == LineItemQuotaBinding.quota_item_id)
        .all()
    )
    count = 0
    for row in rows:
        key = (_code_prefix(row.code), _canonical_name(row.name), (row.unit or "").strip())
        if not key[0] or not key[1]:
            continue
        cluster = clusters.get(key)
        if cluster is None:
            cluster = _Cluster(*key)
            clusters[key] = cluster

        coeff = float(row.coefficient or 1.0)
        # Approximate line total: qty × (labor+material+machine) base_price proxy
        approx_total = float(row.quantity or 0) * float(row.base_price or 0) * coeff
        cluster.lines.append((float(row.quantity or 0), approx_total, row.project_id))
        cluster.project_ids.add(row.project_id)
        cluster.quota_usage[row.quota_item_id].append({
            "coefficient": coeff,
            "labor_qty": float(row.labor_qty or 0),
            "material_qty": float(row.material_qty or 0),
            "machine_qty": float(row.machine_qty or 0),
        })
        count += 1
    return count


# ─── Confidence scoring ──────────────────────────────────────────────


def _confidence(sample_count: int, dispersion: float, project_count: int) -> float:
    """Higher sample count + lower dispersion + more projects → higher confidence."""
    # Sigmoid-ish saturation on samples (cap at ~20)
    sample_score = min(sample_count / 20.0, 1.0)
    # Dispersion: 0 = identical, 1 = highly varied. Invert.
    dispersion_score = max(0.0, 1.0 - dispersion)
    # Project diversity bonus
    project_score = min(project_count / 5.0, 1.0)

    return round(0.5 * sample_score + 0.3 * dispersion_score + 0.2 * project_score, 3)


def _dispersion(values: list[float]) -> float:
    """Coefficient of variation (CV), clamped to [0,1]."""
    if len(values) < 2:
        return 0.0
    mean = statistics.mean(values)
    if mean == 0:
        return 0.0
    try:
        sd = statistics.stdev(values)
    except statistics.StatisticsError:
        return 0.0
    return min(sd / abs(mean), 1.0)


def _summarise_cluster(cluster: _Cluster) -> dict[str, Any] | None:
    """Compute weighted suggestions; return None if cluster too small."""
    sample_count = len(cluster.lines)
    if sample_count < MIN_SAMPLES:
        return None

    qtys = [q for q, _, _ in cluster.lines if q > 0]
    totals = [t for _, t, _ in cluster.lines if t > 0]
    sum_qty = sum(qtys)
    sum_total = sum(totals)
    suggested_unit_price = (sum_total / sum_qty) if sum_qty > 0 else 0.0
    unit_prices = [t / q for q, t, _ in cluster.lines if q > 0 and t > 0]

    # Weight quotas by their usage frequency in this cluster.
    usage_counts = Counter({qid: len(rows) for qid, rows in cluster.quota_usage.items()})
    top_quota_ids = [qid for qid, _ in usage_counts.most_common(3)]

    # Weighted means across the top-N most-used quotas
    labor_vals: list[float] = []
    material_vals: list[float] = []
    machine_vals: list[float] = []
    coeff_vals: list[float] = []
    for qid in top_quota_ids:
        for row in cluster.quota_usage[qid]:
            labor_vals.append(row["labor_qty"] * row["coefficient"])
            material_vals.append(row["material_qty"] * row["coefficient"])
            machine_vals.append(row["machine_qty"] * row["coefficient"])
            coeff_vals.append(row["coefficient"])

    suggested_labor_qty = statistics.fmean(labor_vals) if labor_vals else 0.0
    suggested_material_qty = statistics.fmean(material_vals) if material_vals else 0.0
    suggested_machine_qty = statistics.fmean(machine_vals) if machine_vals else 0.0
    suggested_coefficient = statistics.fmean(coeff_vals) if coeff_vals else 1.0

    dispersion = _dispersion(unit_prices) if unit_prices else 0.0
    confidence = _confidence(sample_count, dispersion, len(cluster.project_ids))
    if confidence < MIN_CONFIDENCE:
        return None

    return {
        "boq_code_pattern": cluster.boq_code_pattern,
        "name_canonical": cluster.name_canonical,
        "unit": cluster.unit,
        "suggested_labor_qty": round(suggested_labor_qty, 4),
        "suggested_material_qty": round(suggested_material_qty, 4),
        "suggested_machine_qty": round(suggested_machine_qty, 4),
        "suggested_unit_price": round(suggested_unit_price, 2),
        "suggested_coefficient": round(suggested_coefficient, 3),
        "sample_count": sample_count,
        "confidence": confidence,
        "source_quota_ids": top_quota_ids,
        "source_project_ids": sorted(cluster.project_ids),
        "evidence": {
            "unit_price_min": round(min(unit_prices), 2) if unit_prices else 0,
            "unit_price_max": round(max(unit_prices), 2) if unit_prices else 0,
            "unit_price_median": round(statistics.median(unit_prices), 2) if unit_prices else 0,
            "dispersion": round(dispersion, 3),
            "project_count": len(cluster.project_ids),
        },
    }


# ─── Persistence ─────────────────────────────────────────────────────


def _upsert_candidate(
    db: Session,
    summary: dict[str, Any],
) -> tuple[bool, EnterpriseQuotaCandidate]:
    """Returns (created_new, candidate_row)."""
    existing = (
        db.query(EnterpriseQuotaCandidate)
        .filter(
            EnterpriseQuotaCandidate.boq_code_pattern == summary["boq_code_pattern"],
            EnterpriseQuotaCandidate.name_canonical == summary["name_canonical"],
            EnterpriseQuotaCandidate.unit == summary["unit"],
        )
        .first()
    )
    now = datetime.now(timezone.utc)
    if existing:
        # Don't overwrite if already promoted/dismissed
        if existing.status != CANDIDATE_PENDING:
            return False, existing
        existing.suggested_labor_qty = summary["suggested_labor_qty"]
        existing.suggested_material_qty = summary["suggested_material_qty"]
        existing.suggested_machine_qty = summary["suggested_machine_qty"]
        existing.suggested_unit_price = summary["suggested_unit_price"]
        existing.suggested_coefficient = summary["suggested_coefficient"]
        existing.sample_count = summary["sample_count"]
        existing.confidence = summary["confidence"]
        existing.source_quota_ids_json = json.dumps(summary["source_quota_ids"])
        existing.source_project_ids_json = json.dumps(summary["source_project_ids"])
        existing.evidence_json = json.dumps(summary["evidence"], ensure_ascii=False)
        existing.last_analyzed_at = now
        return False, existing

    candidate = EnterpriseQuotaCandidate(
        boq_code_pattern=summary["boq_code_pattern"],
        name_canonical=summary["name_canonical"],
        unit=summary["unit"],
        suggested_labor_qty=summary["suggested_labor_qty"],
        suggested_material_qty=summary["suggested_material_qty"],
        suggested_machine_qty=summary["suggested_machine_qty"],
        suggested_unit_price=summary["suggested_unit_price"],
        suggested_coefficient=summary["suggested_coefficient"],
        sample_count=summary["sample_count"],
        confidence=summary["confidence"],
        source_quota_ids_json=json.dumps(summary["source_quota_ids"]),
        source_project_ids_json=json.dumps(summary["source_project_ids"]),
        evidence_json=json.dumps(summary["evidence"], ensure_ascii=False),
        status=CANDIDATE_PENDING,
        last_analyzed_at=now,
    )
    db.add(candidate)
    return True, candidate


# ─── Public API ──────────────────────────────────────────────────────


def analyze_all(db: Session) -> dict[str, int]:
    """Run a full analysis across all snapshots + live bindings."""
    clusters: dict[tuple[str, str, str], _Cluster] = {}

    snapshots = db.query(Snapshot).all()
    bindings_count = _ingest_live_bindings(db, clusters)
    lines_count = 0
    for snap in snapshots:
        lines_count += _ingest_snapshot(db, snap, clusters)

    created = 0
    updated = 0
    for cluster in clusters.values():
        summary = _summarise_cluster(cluster)
        if not summary:
            continue
        is_new, _ = _upsert_candidate(db, summary)
        if is_new:
            created += 1
        else:
            updated += 1
    db.commit()

    return {
        "snapshots_scanned": len(snapshots),
        "bindings_scanned": bindings_count + lines_count,
        "candidates_created": created,
        "candidates_updated": updated,
    }


def list_candidates(
    db: Session,
    *,
    status: str | None = CANDIDATE_PENDING,
    min_confidence: float = 0.0,
    keyword: str | None = None,
    skip: int = 0,
    limit: int = 50,
) -> tuple[int, list[EnterpriseQuotaCandidate]]:
    q = db.query(EnterpriseQuotaCandidate)
    if status:
        q = q.filter(EnterpriseQuotaCandidate.status == status)
    if min_confidence:
        q = q.filter(EnterpriseQuotaCandidate.confidence >= min_confidence)
    if keyword:
        kw = f"%{keyword}%"
        q = q.filter(
            (EnterpriseQuotaCandidate.name_canonical.like(kw))
            | (EnterpriseQuotaCandidate.boq_code_pattern.like(kw)),
        )
    total = q.count()
    rows = (
        q.order_by(EnterpriseQuotaCandidate.confidence.desc(), EnterpriseQuotaCandidate.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return total, rows


def candidate_to_dict(c: EnterpriseQuotaCandidate) -> dict[str, Any]:
    return {
        "id": c.id,
        "boq_code_pattern": c.boq_code_pattern,
        "name_canonical": c.name_canonical,
        "unit": c.unit,
        "suggested_labor_qty": c.suggested_labor_qty,
        "suggested_material_qty": c.suggested_material_qty,
        "suggested_machine_qty": c.suggested_machine_qty,
        "suggested_unit_price": c.suggested_unit_price,
        "suggested_coefficient": c.suggested_coefficient,
        "sample_count": c.sample_count,
        "confidence": c.confidence,
        "source_quota_ids": json.loads(c.source_quota_ids_json or "[]"),
        "source_project_ids": json.loads(c.source_project_ids_json or "[]"),
        "evidence": json.loads(c.evidence_json or "{}"),
        "status": c.status,
        "promoted_to_id": c.promoted_to_id,
        "dismiss_reason": c.dismiss_reason,
        "created_at": c.created_at,
        "last_analyzed_at": c.last_analyzed_at,
    }


def promote_candidate(
    db: Session,
    *,
    candidate_id: int,
    actor: str = "",
    quota_code_override: str | None = None,
) -> EnterpriseQuotaItem:
    """Generate a draft EnterpriseQuotaItem from a candidate."""
    c = (
        db.query(EnterpriseQuotaCandidate)
        .filter(EnterpriseQuotaCandidate.id == candidate_id)
        .first()
    )
    if not c:
        raise LookupError(f"候选 {candidate_id} 不存在")
    if c.status != CANDIDATE_PENDING:
        raise ValueError(f"候选当前状态为 {c.status}，不可重复提升")

    # Generate a stable enterprise code from the pattern
    quota_code = (
        quota_code_override
        or f"ENT-{c.boq_code_pattern}-{c.id:04d}"
    )

    # If somehow the code already exists (unlikely), bump
    if (
        db.query(EnterpriseQuotaItem)
        .filter(EnterpriseQuotaItem.quota_code == quota_code)
        .first()
    ):
        quota_code = f"{quota_code}-A"

    source_ids = json.loads(c.source_quota_ids_json or "[]")
    project_ids = json.loads(c.source_project_ids_json or "[]")

    item = EnterpriseQuotaItem(
        quota_code=quota_code,
        name=c.name_canonical or f"沉淀-{c.boq_code_pattern}",
        unit=c.unit or "项",
        labor_qty=c.suggested_labor_qty,
        material_qty=c.suggested_material_qty,
        machine_qty=c.suggested_machine_qty,
        labor_fee=0.0,
        material_fee=0.0,
        machine_fee=0.0,
        base_price=c.suggested_unit_price,
        coefficient_default=c.suggested_coefficient,
        chapter="",
        profession="房建",
        version="v2026.1",
        work_content=f"由 {c.sample_count} 条历史项目数据沉淀生成 (置信度 {c.confidence:.0%})",
        applicable_scope="",
        tags_json=json.dumps(["沉淀", "智能推荐"], ensure_ascii=False),
        status=STATUS_DRAFT,
        source_type=SOURCE_PRECIPITATED,
        source_ref_json=json.dumps({
            "candidate_id": c.id,
            "source_quota_ids": source_ids,
            "source_project_ids": project_ids,
            "confidence": c.confidence,
            "sample_count": c.sample_count,
        }, ensure_ascii=False),
        created_by=actor,
    )
    db.add(item)
    db.flush()  # ensure item.id is populated

    c.status = CANDIDATE_PROMOTED
    c.promoted_to_id = item.id
    db.commit()
    db.refresh(item)
    return item


def dismiss_candidate(
    db: Session,
    *,
    candidate_id: int,
    reason: str = "",
    actor: str = "",  # noqa: ARG001 — kept for future audit trail
) -> EnterpriseQuotaCandidate:
    c = (
        db.query(EnterpriseQuotaCandidate)
        .filter(EnterpriseQuotaCandidate.id == candidate_id)
        .first()
    )
    if not c:
        raise LookupError(f"候选 {candidate_id} 不存在")
    if c.status != CANDIDATE_PENDING:
        raise ValueError(f"候选当前状态为 {c.status}，不可忽略")
    c.status = CANDIDATE_DISMISSED
    c.dismiss_reason = reason
    db.commit()
    db.refresh(c)
    return c
