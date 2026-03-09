"""Sprint 5 integration tests: BOQ CRUD, extended validation, diff explanation, division export.

DB fixtures provided by conftest.py.
"""

from app.models.boq_item import BoqItem
from app.models.line_item_quota_binding import LineItemQuotaBinding
from app.models.quota_item import QuotaItem


def _seed_with_division(db, project_id):
    """Seed BOQ + quota + bindings with division labels."""
    boq1 = BoqItem(project_id=project_id, code="010101", name="混凝土浇筑C30",
                   unit="m3", quantity=100, division="土建")
    boq2 = BoqItem(project_id=project_id, code="020101", name="给排水管安装",
                   unit="m", quantity=50, division="安装")
    q1 = QuotaItem(quota_code="D-C30", name="混凝土浇筑C30", unit="m3",
                   labor_qty=2.0, material_qty=5.0, machine_qty=1.0)
    q2 = QuotaItem(quota_code="D-PIPE", name="给排水管安装", unit="m",
                   labor_qty=1.0, material_qty=3.0, machine_qty=0.5)
    db.add_all([boq1, boq2, q1, q2])
    db.commit()
    db.refresh(boq1)
    db.refresh(boq2)
    db.refresh(q1)
    db.refresh(q2)
    db.add(LineItemQuotaBinding(boq_item_id=boq1.id, quota_item_id=q1.id))
    db.add(LineItemQuotaBinding(boq_item_id=boq2.id, quota_item_id=q2.id))
    db.commit()
    return boq1, boq2, q1, q2


# ---------------------------------------------------------------------------
# BOQ Item CRUD
# ---------------------------------------------------------------------------

def test_create_boq_item(client):
    r = client.post("/api/projects", json={"name": "CRUD", "region": "bj"})
    pid = r.json()["id"]

    r = client.post(f"/api/projects/{pid}/boq-items", json={
        "code": "NEW01", "name": "新建清单项", "unit": "m2", "quantity": 50,
        "division": "装饰",
    })
    assert r.status_code == 200
    item = r.json()
    assert item["code"] == "NEW01"
    assert item["division"] == "装饰"
    assert item["quantity"] == 50


def test_update_boq_item(client, db):
    r = client.post("/api/projects", json={"name": "Update", "region": "sh"})
    pid = r.json()["id"]

    boq = BoqItem(project_id=pid, code="U01", name="原名", unit="m", quantity=10, is_dirty=0)
    db.add(boq)
    db.commit()
    db.refresh(boq)

    r = client.put(f"/api/projects/{pid}/boq-items/{boq.id}", json={
        "name": "新名", "quantity": 20,
    })
    assert r.status_code == 200
    assert r.json()["name"] == "新名"
    assert r.json()["quantity"] == 20

    # dirty flag should be set
    db.refresh(boq)
    assert boq.is_dirty == 1


def test_update_boq_item_creates_audit_log(client, db):
    r = client.post("/api/projects", json={"name": "UpAudit", "region": "bj"})
    pid = r.json()["id"]

    boq = BoqItem(project_id=pid, code="A01", name="Test", unit="m", quantity=5)
    db.add(boq)
    db.commit()
    db.refresh(boq)

    client.put(f"/api/projects/{pid}/boq-items/{boq.id}", json={"quantity": 99})

    r = client.get(f"/api/projects/{pid}/audit-logs")
    logs = r.json()
    assert any(l["action"] == "update_boq_item" for l in logs)


def test_delete_boq_item(client, db):
    r = client.post("/api/projects", json={"name": "Del", "region": "bj"})
    pid = r.json()["id"]

    boq = BoqItem(project_id=pid, code="D01", name="ToDelete", unit="m", quantity=1)
    db.add(boq)
    db.commit()
    db.refresh(boq)

    r = client.delete(f"/api/projects/{pid}/boq-items/{boq.id}")
    assert r.status_code == 200

    r = client.get(f"/api/projects/{pid}/boq-items")
    assert len(r.json()) == 0

    # Audit log recorded
    r = client.get(f"/api/projects/{pid}/audit-logs")
    assert any(l["action"] == "delete_boq_item" for l in r.json())


def test_delete_boq_item_404(client):
    r = client.post("/api/projects", json={"name": "D404", "region": "bj"})
    pid = r.json()["id"]
    r = client.delete(f"/api/projects/{pid}/boq-items/9999")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Extended Validation Rules
# ---------------------------------------------------------------------------

def test_validation_duplicate_code(client, db):
    r = client.post("/api/projects", json={"name": "DupCode", "region": "bj"})
    pid = r.json()["id"]

    db.add(BoqItem(project_id=pid, code="DUP01", name="A", unit="m", quantity=1))
    db.add(BoqItem(project_id=pid, code="DUP01", name="B", unit="m", quantity=2))
    db.commit()

    r = client.get(f"/api/projects/{pid}/validation-issues")
    report = r.json()
    assert any(i["code"] == "DUPLICATE_CODE" for i in report["issues"])


def test_validation_missing_material_price(client, db):
    """When no material prices exist, warning should fire."""
    r = client.post("/api/projects", json={"name": "NoMP", "region": "sh"})
    pid = r.json()["id"]

    db.add(BoqItem(project_id=pid, code="X01", name="Item", unit="m", quantity=1))
    db.commit()

    r = client.get(f"/api/projects/{pid}/validation-issues")
    report = r.json()
    mp_issues = [i for i in report["issues"] if i["code"] == "MISSING_MATERIAL_PRICE"]
    assert len(mp_issues) == 3  # 人工费, 材料费, 机械费


def test_validation_no_rule_package(client, db):
    r = client.post("/api/projects", json={"name": "NoRP", "region": "bj"})
    pid = r.json()["id"]

    db.add(BoqItem(project_id=pid, code="R01", name="Item", unit="m", quantity=1))
    db.commit()

    r = client.get(f"/api/projects/{pid}/validation-issues")
    report = r.json()
    assert any(i["code"] == "NO_RULE_PACKAGE" for i in report["issues"])


# ---------------------------------------------------------------------------
# AI Diff Explanation
# ---------------------------------------------------------------------------

def test_diff_has_explanation(client, db):
    r = client.post("/api/projects", json={"name": "DiffExp", "region": "bj"})
    pid = r.json()["id"]
    boq1, boq2, q1, q2 = _seed_with_division(db, pid)

    r1 = client.post(f"/api/projects/{pid}/snapshots", json={"label": "v1"})
    sid1 = r1.json()["id"]

    # Change quantity
    boq1.quantity = 200
    boq1.is_dirty = 1
    db.commit()

    r2 = client.post(f"/api/projects/{pid}/snapshots", json={"label": "v2"})
    sid2 = r2.json()["id"]

    r = client.post(f"/api/projects/{pid}/diff", json={
        "snapshot_a_id": sid1, "snapshot_b_id": sid2,
    })
    diff = r.json()
    assert "explanation" in diff
    assert len(diff["explanation"]) > 0
    assert "变更" in diff["explanation"]
    assert "总价变动" in diff["explanation"]


def test_diff_unchanged_explanation(client, db):
    r = client.post("/api/projects", json={"name": "DiffUn", "region": "sh"})
    pid = r.json()["id"]
    _seed_with_division(db, pid)

    r1 = client.post(f"/api/projects/{pid}/snapshots", json={"label": "a"})
    r2 = client.post(f"/api/projects/{pid}/snapshots", json={"label": "b"})

    r = client.post(f"/api/projects/{pid}/diff", json={
        "snapshot_a_id": r1.json()["id"], "snapshot_b_id": r2.json()["id"],
    })
    diff = r.json()
    assert "未变" in diff["explanation"]


# ---------------------------------------------------------------------------
# Division Summary Export
# ---------------------------------------------------------------------------

def test_export_has_division_sheet(client, db):
    """Valuation report should contain a division summary sheet."""
    r = client.post("/api/projects", json={"name": "DivExp", "region": "bj"})
    pid = r.json()["id"]
    _seed_with_division(db, pid)

    r = client.post(f"/api/exports/valuation-report?project_id={pid}")
    assert r.status_code == 200
    assert "spreadsheetml" in r.headers["content-type"]

    # Verify it's a valid xlsx with 2 sheets
    import io, openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(r.content))
    assert len(wb.sheetnames) == 2
    assert "分部汇总" in wb.sheetnames
    ws = wb["分部汇总"]
    # Should have header + at least 2 division rows (土建, 安装)
    assert ws.cell(row=4, column=1).value in ("安装", "土建")
