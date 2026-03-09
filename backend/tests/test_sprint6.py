"""Sprint 6 integration tests: measures, collaboration, AI query navigation.

DB fixtures provided by conftest.py.
"""

from app.models.boq_item import BoqItem
from app.models.line_item_quota_binding import LineItemQuotaBinding
from app.models.quota_item import QuotaItem


def _seed(db, project_id):
    boq1 = BoqItem(project_id=project_id, code="010101", name="混凝土浇筑C30", unit="m3", quantity=100)
    boq2 = BoqItem(project_id=project_id, code="020101", name="钢筋制安", unit="t", quantity=5)
    q1 = QuotaItem(quota_code="D-C30", name="混凝土浇筑C30", unit="m3",
                   labor_qty=2.0, material_qty=5.0, machine_qty=1.0)
    q2 = QuotaItem(quota_code="D-RB01", name="钢筋制作安装", unit="t",
                   labor_qty=10.0, material_qty=1.0, machine_qty=0.5)
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
# Measures
# ---------------------------------------------------------------------------

def test_create_measure(client):
    r = client.post("/api/projects", json={"name": "Meas", "region": "bj"})
    pid = r.json()["id"]

    r = client.post(f"/api/projects/{pid}/measures", json={
        "name": "安全文明施工费", "calc_base": "direct", "rate": 0.05,
    })
    assert r.status_code == 200
    assert r.json()["name"] == "安全文明施工费"
    assert r.json()["is_fixed"] is False


def test_create_fixed_measure(client):
    r = client.post("/api/projects", json={"name": "Fix", "region": "sh"})
    pid = r.json()["id"]

    r = client.post(f"/api/projects/{pid}/measures", json={
        "name": "临时设施费", "is_fixed": True, "amount": 50000,
    })
    assert r.status_code == 200
    assert r.json()["is_fixed"] is True
    assert r.json()["amount"] == 50000


def test_list_measures(client):
    r = client.post("/api/projects", json={"name": "ListM", "region": "bj"})
    pid = r.json()["id"]
    client.post(f"/api/projects/{pid}/measures", json={"name": "A", "rate": 0.01})
    client.post(f"/api/projects/{pid}/measures", json={"name": "B", "rate": 0.02})

    r = client.get(f"/api/projects/{pid}/measures")
    assert len(r.json()) == 2


def test_delete_measure(client):
    r = client.post("/api/projects", json={"name": "DelM", "region": "bj"})
    pid = r.json()["id"]
    r = client.post(f"/api/projects/{pid}/measures", json={"name": "X", "rate": 0.01})
    mid = r.json()["id"]

    r = client.delete(f"/api/projects/{pid}/measures/{mid}")
    assert r.status_code == 200

    r = client.get(f"/api/projects/{pid}/measures")
    assert len(r.json()) == 0


def test_calculate_with_measures(client, db):
    """Measures should be included in grand total."""
    r = client.post("/api/projects", json={"name": "CalcM", "region": "bj"})
    pid = r.json()["id"]
    _seed(db, pid)

    # Calculate without measures
    r1 = client.post(f"/api/projects/{pid}/calculate")
    total_no_measures = r1.json()["grand_total"]
    assert r1.json()["total_measures"] == 0

    # Add measures
    client.post(f"/api/projects/{pid}/measures", json={
        "name": "安全文明", "calc_base": "direct", "rate": 0.05,
    })
    client.post(f"/api/projects/{pid}/measures", json={
        "name": "临设", "is_fixed": True, "amount": 1000,
    })

    # Calculate with measures
    r2 = client.post(f"/api/projects/{pid}/calculate")
    assert r2.json()["total_measures"] > 0
    assert r2.json()["grand_total"] > total_no_measures


# ---------------------------------------------------------------------------
# Collaboration
# ---------------------------------------------------------------------------

def test_add_and_list_members(client):
    r = client.post("/api/projects", json={"name": "Collab", "region": "bj"})
    pid = r.json()["id"]

    r = client.post(f"/api/projects/{pid}/members", json={
        "user_name": "张三", "role": "owner",
    })
    assert r.status_code == 200
    assert r.json()["role"] == "owner"

    client.post(f"/api/projects/{pid}/members", json={
        "user_name": "李四", "role": "editor",
    })

    r = client.get(f"/api/projects/{pid}/members")
    assert len(r.json()) == 2


def test_add_and_list_comments(client, db):
    r = client.post("/api/projects", json={"name": "Comm", "region": "sh"})
    pid = r.json()["id"]

    boq = BoqItem(project_id=pid, code="C01", name="Item", unit="m", quantity=1)
    db.add(boq)
    db.commit()
    db.refresh(boq)

    r = client.post(f"/api/projects/{pid}/comments", json={
        "boq_item_id": boq.id, "author": "张三", "content": "这个数量需要确认",
    })
    assert r.status_code == 200
    assert r.json()["content"] == "这个数量需要确认"
    assert r.json()["boq_item_id"] == boq.id

    # Project-level comment (no boq_item_id)
    client.post(f"/api/projects/{pid}/comments", json={
        "author": "李四", "content": "整体费率偏高",
    })

    r = client.get(f"/api/projects/{pid}/comments")
    assert len(r.json()) == 2


# ---------------------------------------------------------------------------
# AI Query Navigation
# ---------------------------------------------------------------------------

def test_query_unbound(client, db):
    r = client.post("/api/projects", json={"name": "Q1", "region": "bj"})
    pid = r.json()["id"]

    # One bound, one unbound
    boq1 = BoqItem(project_id=pid, code="B01", name="已绑定", unit="m", quantity=1)
    boq2 = BoqItem(project_id=pid, code="B02", name="未绑定项", unit="m2", quantity=2)
    q = QuotaItem(quota_code="QQ-01", name="Test", unit="m",
                  labor_qty=1, material_qty=1, machine_qty=1)
    db.add_all([boq1, boq2, q])
    db.commit()
    db.refresh(boq1)
    db.refresh(q)
    db.add(LineItemQuotaBinding(boq_item_id=boq1.id, quota_item_id=q.id))
    db.commit()

    r = client.post(f"/api/projects/{pid}/query", json={"q": "未绑定"})
    assert r.status_code == 200
    resp = r.json()
    assert resp["total_hits"] == 1
    assert resp["hits"][0]["name"] == "未绑定项"


def test_query_issues(client, db):
    r = client.post("/api/projects", json={"name": "Q2", "region": "bj"})
    pid = r.json()["id"]

    db.add(BoqItem(project_id=pid, code="Q01", name="无绑定", unit="m", quantity=1))
    db.commit()

    r = client.post(f"/api/projects/{pid}/query", json={"q": "异常"})
    resp = r.json()
    assert resp["total_hits"] >= 1


def test_query_keyword(client, db):
    r = client.post("/api/projects", json={"name": "Q3", "region": "sh"})
    pid = r.json()["id"]

    db.add(BoqItem(project_id=pid, code="K01", name="混凝土浇筑", unit="m3", quantity=10))
    db.add(BoqItem(project_id=pid, code="K02", name="钢筋安装", unit="t", quantity=5))
    db.commit()

    r = client.post(f"/api/projects/{pid}/query", json={"q": "混凝土"})
    resp = r.json()
    assert resp["total_hits"] == 1
    assert "混凝土" in resp["hits"][0]["name"]


def test_query_dirty(client, db):
    r = client.post("/api/projects", json={"name": "Q4", "region": "bj"})
    pid = r.json()["id"]

    db.add(BoqItem(project_id=pid, code="D01", name="Dirty", unit="m", quantity=1, is_dirty=1))
    db.add(BoqItem(project_id=pid, code="D02", name="Clean", unit="m", quantity=1, is_dirty=0))
    db.commit()

    r = client.post(f"/api/projects/{pid}/query", json={"q": "待重算"})
    resp = r.json()
    assert resp["total_hits"] == 1
    assert resp["hits"][0]["name"] == "Dirty"
