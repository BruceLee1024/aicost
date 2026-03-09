"""Sprint 4 integration tests: rule packages, material prices, diff export, audit logs.

DB fixtures provided by conftest.py.
"""

from app.models.boq_item import BoqItem
from app.models.line_item_quota_binding import LineItemQuotaBinding
from app.models.material_price import MaterialPrice
from app.models.quota_item import QuotaItem


def _seed(db, project_id):
    """Seed BOQ + quota + bindings for a project."""
    boq1 = BoqItem(project_id=project_id, code="010101", name="混凝土浇筑C30", unit="m3", quantity=100)
    q1 = QuotaItem(quota_code="D-C30", name="混凝土浇筑C30", unit="m3",
                   labor_qty=2.0, material_qty=5.0, machine_qty=1.0)
    db.add_all([boq1, q1])
    db.commit()
    db.refresh(boq1)
    db.refresh(q1)
    db.add(LineItemQuotaBinding(boq_item_id=boq1.id, quota_item_id=q1.id))
    db.commit()
    return boq1, q1


# ---------------------------------------------------------------------------
# Rule Packages
# ---------------------------------------------------------------------------

def test_create_rule_package(client):
    r = client.post("/api/rule-packages", json={
        "name": "上海2024", "region": "sh",
        "management_rate": 0.10, "profit_rate": 0.06,
        "regulatory_rate": 0.04, "tax_rate": 0.09,
    })
    assert r.status_code == 200
    rp = r.json()
    assert rp["name"] == "上海2024"
    assert rp["management_rate"] == 0.10


def test_list_rule_packages(client):
    client.post("/api/rule-packages", json={"name": "A", "region": "bj"})
    client.post("/api/rule-packages", json={"name": "B", "region": "sh"})
    r = client.get("/api/rule-packages")
    assert r.status_code == 200
    assert len(r.json()) >= 2


def test_bind_rule_package(client):
    # Create project
    r = client.post("/api/projects", json={"name": "RuleBind", "region": "bj"})
    pid = r.json()["id"]
    # Create rule package
    r = client.post("/api/rule-packages", json={"name": "BJ2024", "region": "bj"})
    rp_id = r.json()["id"]
    # Bind
    r = client.post(f"/api/projects/{pid}/rule-package:bind",
                    json={"rule_package_id": rp_id})
    assert r.status_code == 200


def test_calculate_with_rule_package(client, db):
    """Calculation should use bound rule package's fee rates."""
    r = client.post("/api/projects", json={"name": "CalcRP", "region": "sh"})
    pid = r.json()["id"]
    boq1, q1 = _seed(db, pid)

    # Create a rule package with different rates
    r = client.post("/api/rule-packages", json={
        "name": "高费率", "region": "sh",
        "management_rate": 0.20, "profit_rate": 0.10,
        "regulatory_rate": 0.05, "tax_rate": 0.13,
    })
    rp_id = r.json()["id"]
    client.post(f"/api/projects/{pid}/rule-package:bind",
                json={"rule_package_id": rp_id})

    # Calculate with rule package
    r = client.post(f"/api/projects/{pid}/calculate")
    assert r.status_code == 200
    result_with_rp = r.json()["grand_total"]

    # Compare: create another project with default rates, reuse existing quota
    r2 = client.post("/api/projects", json={"name": "CalcDef", "region": "sh"})
    pid2 = r2.json()["id"]
    boq2 = BoqItem(project_id=pid2, code="010101", name="混凝土浇筑C30", unit="m3", quantity=100)
    db.add(boq2)
    db.commit()
    db.refresh(boq2)
    # Reuse q1 from first seed
    db.add(LineItemQuotaBinding(boq_item_id=boq2.id, quota_item_id=q1.id))
    db.commit()
    r2 = client.post(f"/api/projects/{pid2}/calculate")
    result_default = r2.json()["grand_total"]

    # Higher fee rates → higher total
    assert result_with_rp > result_default


# ---------------------------------------------------------------------------
# Material Prices
# ---------------------------------------------------------------------------

def test_create_material_price(client):
    r = client.post("/api/material-prices", json={
        "code": "RC-001", "name": "人工费", "unit": "工日", "unit_price": 350.0,
    })
    assert r.status_code == 200
    assert r.json()["unit_price"] == 350.0


def test_batch_create_material_prices(client):
    r = client.post("/api/material-prices:batch", json={
        "items": [
            {"code": "RC-001", "name": "人工费", "unit": "工日", "unit_price": 350.0},
            {"code": "CL-001", "name": "材料费", "unit": "t", "unit_price": 500.0},
            {"code": "JX-001", "name": "机械费", "unit": "台班", "unit_price": 800.0},
        ]
    })
    assert r.status_code == 200
    assert len(r.json()) == 3


def test_list_material_prices(client):
    client.post("/api/material-prices", json={
        "code": "X1", "name": "TestMP", "unit": "m", "unit_price": 10,
    })
    r = client.get("/api/material-prices")
    assert r.status_code == 200
    assert len(r.json()) >= 1


def test_calculate_with_material_prices(client, db):
    """Calculation should use material prices from DB instead of fallback 1.0."""
    r = client.post("/api/projects", json={"name": "CalcMP", "region": "sh"})
    pid = r.json()["id"]
    _seed(db, pid)

    # Calculate with default prices (1.0 fallback)
    r1 = client.post(f"/api/projects/{pid}/calculate")
    total_default = r1.json()["grand_total"]

    # Add higher material prices
    db.add_all([
        MaterialPrice(code="RC", name="人工费", unit="工日", unit_price=100.0),
        MaterialPrice(code="CL", name="材料费", unit="t", unit_price=200.0),
        MaterialPrice(code="JX", name="机械费", unit="台班", unit_price=150.0),
    ])
    db.commit()

    # Recalculate – should be much higher
    r2 = client.post(f"/api/projects/{pid}/calculate")
    total_with_prices = r2.json()["grand_total"]

    assert total_with_prices > total_default


# ---------------------------------------------------------------------------
# Diff Export
# ---------------------------------------------------------------------------

def test_export_diff_report(client, db):
    r = client.post("/api/projects", json={"name": "DiffExp", "region": "bj"})
    pid = r.json()["id"]
    _seed(db, pid)

    r1 = client.post(f"/api/projects/{pid}/snapshots", json={"label": "v1"})
    sid1 = r1.json()["id"]

    # Change data
    boq = db.query(BoqItem).filter(BoqItem.project_id == pid).first()
    boq.quantity = 200
    boq.is_dirty = 1
    db.commit()

    r2 = client.post(f"/api/projects/{pid}/snapshots", json={"label": "v2"})
    sid2 = r2.json()["id"]

    r = client.post(f"/api/exports/diff-report?snapshot_a_id={sid1}&snapshot_b_id={sid2}")
    assert r.status_code == 200
    assert "spreadsheetml" in r.headers["content-type"]
    assert len(r.content) > 100


def test_export_diff_report_404(client):
    r = client.post("/api/exports/diff-report?snapshot_a_id=999&snapshot_b_id=888")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Audit Logs
# ---------------------------------------------------------------------------

def test_audit_log_on_bind(client):
    """Binding a rule package should produce an audit log entry."""
    r = client.post("/api/projects", json={"name": "AuditP", "region": "bj"})
    pid = r.json()["id"]
    r = client.post("/api/rule-packages", json={"name": "AuditRP", "region": "bj"})
    rp_id = r.json()["id"]

    client.post(f"/api/projects/{pid}/rule-package:bind",
                json={"rule_package_id": rp_id})

    r = client.get(f"/api/projects/{pid}/audit-logs")
    assert r.status_code == 200
    logs = r.json()
    assert len(logs) >= 1
    assert logs[0]["action"] == "bind_rule_package"
    assert logs[0]["resource_type"] == "project"


def test_audit_log_empty(client):
    r = client.post("/api/projects", json={"name": "NoLog", "region": "sh"})
    pid = r.json()["id"]
    r = client.get(f"/api/projects/{pid}/audit-logs")
    assert r.status_code == 200
    assert r.json() == []
