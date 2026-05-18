"""Tests for the enterprise quota precipitation analyzer."""

import json

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
from app.models.project import Project
from app.models.quota_item import QuotaItem
from app.services import enterprise_quota_precipitation_service as precip


def _seed_project_with_bindings(
    db, *, name: str, region: str = "全国", count: int = 5,
    boq_code: str = "010101001001", boq_name: str = "现浇混凝土柱 C30",
    quota_code: str = "1-1-1", coefficient: float = 1.0,
) -> Project:
    proj = Project(name=name, region=region, project_type="房建", status="active")
    db.add(proj)
    db.flush()

    quota = (
        db.query(QuotaItem).filter(QuotaItem.quota_code == quota_code).first()
    )
    if not quota:
        quota = QuotaItem(
            quota_code=quota_code, name="C30 混凝土柱定额", unit="m³",
            labor_qty=0.5, material_qty=1.05, machine_qty=0.08,
            base_price=560.0,
        )
        db.add(quota)
        db.flush()

    for i in range(count):
        boq = BoqItem(
            project_id=proj.id,
            code=boq_code,
            name=boq_name,
            characteristics="",
            unit="m³",
            quantity=10.0 + i,
        )
        db.add(boq)
        db.flush()
        binding = LineItemQuotaBinding(
            boq_item_id=boq.id,
            quota_item_id=quota.id,
            coefficient=coefficient,
        )
        db.add(binding)
    db.commit()
    return proj


# ─── Canonicalisation ────────────────────────────────────────────────


def test_canonical_name_collapses_numbers_and_punct():
    a = precip._canonical_name("C30 现浇混凝土柱 (300x400)")
    b = precip._canonical_name("C30 现浇混凝土柱（500x600）")
    # Numbers are normalised, punctuation removed
    assert a == b
    assert "现浇混凝土柱" in a


def test_code_prefix_truncates():
    assert precip._code_prefix("010101001001") == "010101001"


# ─── Analysis ────────────────────────────────────────────────────────


def test_analyze_creates_candidate_for_repeated_pattern(db):
    _seed_project_with_bindings(db, name="P1", count=4)

    result = precip.analyze_all(db)
    assert result["candidates_created"] >= 1

    candidates = db.query(EnterpriseQuotaCandidate).all()
    assert len(candidates) == 1
    c = candidates[0]
    assert c.status == CANDIDATE_PENDING
    assert c.sample_count >= 4
    assert c.confidence > 0
    assert c.unit == "m³"
    assert "010101001" in c.boq_code_pattern


def test_analyze_skips_below_min_samples(db):
    _seed_project_with_bindings(db, name="P1", count=2)  # below MIN_SAMPLES=3
    result = precip.analyze_all(db)
    assert result["candidates_created"] == 0
    assert db.query(EnterpriseQuotaCandidate).count() == 0


def test_re_analyze_updates_existing_candidate(db):
    _seed_project_with_bindings(db, name="P1", count=4)
    precip.analyze_all(db)
    first = db.query(EnterpriseQuotaCandidate).first()
    first_count = first.sample_count

    # Add more bindings → re-analyze should update, not duplicate
    _seed_project_with_bindings(db, name="P2", count=5)
    result = precip.analyze_all(db)

    assert db.query(EnterpriseQuotaCandidate).count() == 1
    updated = db.query(EnterpriseQuotaCandidate).first()
    assert updated.sample_count > first_count
    assert result["candidates_updated"] >= 1


# ─── Promote / dismiss ───────────────────────────────────────────────


def test_promote_creates_draft_enterprise_quota(db):
    _seed_project_with_bindings(db, name="P1", count=4)
    precip.analyze_all(db)
    c = db.query(EnterpriseQuotaCandidate).first()

    item = precip.promote_candidate(db, candidate_id=c.id, actor="alice")
    assert isinstance(item, EnterpriseQuotaItem)
    assert item.status == STATUS_DRAFT
    assert item.source_type == SOURCE_PRECIPITATED
    assert item.created_by == "alice"
    ref = json.loads(item.source_ref_json)
    assert ref["candidate_id"] == c.id

    db.refresh(c)
    assert c.status == CANDIDATE_PROMOTED
    assert c.promoted_to_id == item.id


def test_dismiss_marks_candidate(db):
    _seed_project_with_bindings(db, name="P1", count=4)
    precip.analyze_all(db)
    c = db.query(EnterpriseQuotaCandidate).first()

    precip.dismiss_candidate(db, candidate_id=c.id, reason="价格不准")
    db.refresh(c)
    assert c.status == CANDIDATE_DISMISSED
    assert c.dismiss_reason == "价格不准"


def test_promote_twice_raises(db):
    _seed_project_with_bindings(db, name="P1", count=4)
    precip.analyze_all(db)
    c = db.query(EnterpriseQuotaCandidate).first()
    precip.promote_candidate(db, candidate_id=c.id)
    import pytest
    with pytest.raises(ValueError):
        precip.promote_candidate(db, candidate_id=c.id)
