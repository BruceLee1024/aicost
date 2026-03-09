"""Sprint 2 integration tests: AI matching, provenance, export, validation.

DB fixtures provided by conftest.py.
"""

from app.models.boq_item import BoqItem
from app.models.line_item_quota_binding import LineItemQuotaBinding
from app.models.quota_item import QuotaItem


def _seed(db, project_id):
    """Seed BOQ items and quota items for testing."""
    boq1 = BoqItem(project_id=project_id, code="010101", name="混凝土浇筑C30", unit="m3", quantity=100)
    boq2 = BoqItem(project_id=project_id, code="010201", name="钢筋制安", unit="t", quantity=5)
    q1 = QuotaItem(quota_code="D-C30", name="混凝土浇筑C30", unit="m3",
                   labor_qty=2.0, material_qty=5.0, machine_qty=1.0)
    q2 = QuotaItem(quota_code="D-RB01", name="钢筋制作安装", unit="t",
                   labor_qty=10.0, material_qty=1.0, machine_qty=0.5)
    q3 = QuotaItem(quota_code="D-MIX", name="混凝土搅拌", unit="m3",
                   labor_qty=1.0, material_qty=3.0, machine_qty=2.0)
    db.add_all([boq1, boq2, q1, q2, q3])
    db.commit()
    db.refresh(boq1)
    db.refresh(boq2)
    db.refresh(q1)
    db.refresh(q2)
    return boq1, boq2, q1, q2


# ---------------------------------------------------------------------------
# AI matching
# ---------------------------------------------------------------------------

def test_quota_candidates(client, db):
    """AI match should return candidates ranked by relevance."""
    r = client.post("/api/projects", json={"name": "Match", "region": "sh"})
    pid = r.json()["id"]

    boq1, boq2, q1, q2 = _seed(db, pid)

    # Get candidates for the concrete BOQ item
    r = client.post(f"/api/boq-items/{boq1.id}/quota-candidates?top_n=3")
    assert r.status_code == 200
    candidates = r.json()
    assert len(candidates) <= 3
    assert len(candidates) > 0
    # Best match should be the concrete quota (same name & unit)
    assert candidates[0]["quota_code"] == "D-C30"
    assert candidates[0]["confidence"] > 0.5
    assert len(candidates[0]["reasons"]) > 0


def test_quota_candidates_404(client):
    r = client.post("/api/boq-items/9999/quota-candidates")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Provenance
# ---------------------------------------------------------------------------

def test_provenance_with_binding(client, db):
    r = client.post("/api/projects", json={"name": "Prov", "region": "bj"})
    pid = r.json()["id"]

    boq1, _, q1, _ = _seed(db, pid)
    db.add(LineItemQuotaBinding(boq_item_id=boq1.id, quota_item_id=q1.id))
    db.commit()

    # Calculate first
    client.post(f"/api/projects/{pid}/calculate")

    # Get provenance
    r = client.get(f"/api/calc-results/{boq1.id}/provenance")
    assert r.status_code == 200
    prov = r.json()
    assert prov["boq_item_id"] == boq1.id
    assert len(prov["bindings"]) == 1
    assert prov["bindings"][0]["quota"]["quota_code"] == "D-C30"
    assert prov["calc_total"] is not None
    assert prov["calc_total"] > 0
    assert "fee_config_snapshot" in prov
    assert "混凝土" in prov["explanation"]


def test_provenance_no_binding(client, db):
    r = client.post("/api/projects", json={"name": "P2", "region": "gd"})
    pid = r.json()["id"]

    boq = BoqItem(project_id=pid, code="X01", name="Test", unit="m", quantity=1)
    db.add(boq)
    db.commit()
    db.refresh(boq)

    r = client.get(f"/api/calc-results/{boq.id}/provenance")
    assert r.status_code == 200
    assert r.json()["calc_total"] is None
    assert "尚未绑定" in r.json()["explanation"]


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def test_export_valuation_report(client, db):
    r = client.post("/api/projects", json={"name": "Export", "region": "js"})
    pid = r.json()["id"]

    boq1, _, q1, _ = _seed(db, pid)
    db.add(LineItemQuotaBinding(boq_item_id=boq1.id, quota_item_id=q1.id))
    db.commit()

    r = client.post(f"/api/exports/valuation-report?project_id={pid}")
    assert r.status_code == 200
    assert "spreadsheetml" in r.headers["content-type"]
    assert len(r.content) > 100  # should be a non-trivial Excel file


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def test_validation_no_items(client):
    r = client.post("/api/projects", json={"name": "Empty", "region": "bj"})
    pid = r.json()["id"]

    r = client.get(f"/api/projects/{pid}/validation-issues")
    assert r.status_code == 200
    report = r.json()
    assert report["errors"] >= 1
    assert any(i["code"] == "NO_BOQ_ITEMS" for i in report["issues"])


def test_validation_no_binding(client, db):
    r = client.post("/api/projects", json={"name": "NoBind", "region": "sh"})
    pid = r.json()["id"]

    boq = BoqItem(project_id=pid, code="V01", name="Unbound", unit="m", quantity=10)
    db.add(boq)
    db.commit()

    r = client.get(f"/api/projects/{pid}/validation-issues")
    report = r.json()
    assert any(i["code"] == "NO_BINDING" for i in report["issues"])


def test_validation_unit_mismatch(client, db):
    r = client.post("/api/projects", json={"name": "UnitMM", "region": "sh"})
    pid = r.json()["id"]

    boq = BoqItem(project_id=pid, code="V02", name="Item", unit="m2", quantity=10)
    quota = QuotaItem(quota_code="Q-UNIT", name="Item", unit="m3",
                      labor_qty=1, material_qty=1, machine_qty=1)
    db.add_all([boq, quota])
    db.commit()
    db.refresh(boq)
    db.refresh(quota)
    db.add(LineItemQuotaBinding(boq_item_id=boq.id, quota_item_id=quota.id))
    db.commit()

    r = client.get(f"/api/projects/{pid}/validation-issues")
    report = r.json()
    assert any(i["code"] == "UNIT_MISMATCH" for i in report["issues"])
