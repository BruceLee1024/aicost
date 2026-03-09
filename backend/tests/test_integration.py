"""Integration tests: full MVP loop (create → import → bind → calculate).

DB fixtures provided by conftest.py.
"""

from app.models.boq_item import BoqItem
from app.models.quota_item import QuotaItem


def _seed_boq_and_quota(db, project_id):
    boq = BoqItem(project_id=project_id, code="010101", name="混凝土浇筑", unit="m3", quantity=100)
    quota = QuotaItem(quota_code="D-001", name="混凝土浇筑", unit="m3",
                      labor_qty=2.0, material_qty=5.0, machine_qty=1.0)
    db.add_all([boq, quota])
    db.commit()
    db.refresh(boq)
    db.refresh(quota)
    return boq.id, quota.id


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_create_and_list_projects(client):
    r = client.post("/api/projects", json={"name": "Test Project", "region": "jiangsu"})
    assert r.status_code == 200
    assert r.json()["name"] == "Test Project"
    r2 = client.get("/api/projects")
    assert len(r2.json()) >= 1


def test_get_project_404(client):
    assert client.get("/api/projects/9999").status_code == 404


def test_list_boq_items_empty(client):
    r = client.post("/api/projects", json={"name": "P", "region": "bj"})
    r2 = client.get(f"/api/projects/{r.json()['id']}/boq-items")
    assert r2.json() == []


def test_full_loop_create_bind_calculate(client, db):
    r = client.post("/api/projects", json={"name": "E2E", "region": "sh"})
    project_id = r.json()["id"]
    boq_id, quota_id = _seed_boq_and_quota(db, project_id)

    assert len(client.get(f"/api/projects/{project_id}/boq-items").json()) == 1

    r = client.post(f"/api/boq-items/{boq_id}/quota-binding:confirm",
                    json={"quota_item_id": quota_id})
    assert r.status_code == 200

    r = client.post(f"/api/projects/{project_id}/calculate")
    assert r.json()["grand_total"] > 0
    assert r.json()["line_results"][0]["direct_cost"] > 0


def test_batch_binding(client, db):
    r = client.post("/api/projects", json={"name": "Batch", "region": "gd"})
    pid = r.json()["id"]

    boq1 = BoqItem(project_id=pid, code="A1", name="Item A", unit="m2", quantity=10)
    boq2 = BoqItem(project_id=pid, code="A2", name="Item B", unit="m2", quantity=20)
    quota = QuotaItem(quota_code="Q-BATCH-001", name="Quota A", unit="m2",
                      labor_qty=1, material_qty=1, machine_qty=1)
    db.add_all([boq1, boq2, quota])
    db.commit()
    db.refresh(boq1)
    db.refresh(boq2)
    db.refresh(quota)

    r = client.post("/api/boq-items/quota-binding:batch-confirm",
                    json={"bindings": [
                        {"boq_item_id": boq1.id, "quota_item_id": quota.id},
                        {"boq_item_id": boq2.id, "quota_item_id": quota.id},
                    ]})
    assert len(r.json()) == 2


def test_legacy_calculate_run(client):
    r = client.post("/api/calculate/run", json={
        "labor_qty": 1, "labor_price": 100,
        "material_qty": 2, "material_price": 50,
        "machine_qty": 0.5, "machine_price": 80,
    })
    assert r.json()["total"] == 240.0
