"""Sprint 7 integration tests: binding lifecycle, dashboard summary, regional material prices."""

from app.models.boq_item import BoqItem
from app.models.line_item_quota_binding import LineItemQuotaBinding
from app.models.material_price import MaterialPrice
from app.models.quota_item import QuotaItem


def _seed_single(db, project_id: int):
    boq = BoqItem(project_id=project_id, code="B001", name="测试清单项", unit="m", quantity=10, is_dirty=0)
    q1 = QuotaItem(quota_code="Q-001", name="测试定额1", unit="m", labor_qty=1, material_qty=1, machine_qty=1)
    q2 = QuotaItem(quota_code="Q-002", name="测试定额2", unit="m", labor_qty=1, material_qty=1, machine_qty=1)
    db.add_all([boq, q1, q2])
    db.commit()
    db.refresh(boq)
    db.refresh(q1)
    db.refresh(q2)
    return boq, q1, q2


def _seed_calc_case(db, project_id: int, code_prefix: str):
    boq = BoqItem(project_id=project_id, code=f"{code_prefix}-B", name="计价项", unit="m", quantity=10)
    quota = QuotaItem(
        quota_code=f"{code_prefix}-Q",
        name="计价定额",
        unit="m",
        labor_qty=1,
        material_qty=1,
        machine_qty=1,
    )
    db.add_all([boq, quota])
    db.commit()
    db.refresh(boq)
    db.refresh(quota)
    return boq, quota


def test_confirm_binding_is_idempotent(client, db):
    r = client.post("/api/projects", json={"name": "BindIdem", "region": "bj"})
    pid = r.json()["id"]
    boq, q1, _ = _seed_single(db, pid)

    r1 = client.post(f"/api/boq-items/{boq.id}/quota-binding:confirm", json={"quota_item_id": q1.id})
    r2 = client.post(f"/api/boq-items/{boq.id}/quota-binding:confirm", json={"quota_item_id": q1.id})

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["id"] == r2.json()["id"]

    rows = client.get(f"/api/boq-items/{boq.id}/quota-bindings").json()
    assert len(rows) == 1


def test_replace_and_clear_binding_lifecycle(client, db):
    r = client.post("/api/projects", json={"name": "BindLife", "region": "sh"})
    pid = r.json()["id"]
    boq, q1, q2 = _seed_single(db, pid)

    client.post(f"/api/boq-items/{boq.id}/quota-binding:confirm", json={"quota_item_id": q1.id})
    rep = client.post(f"/api/boq-items/{boq.id}/quota-binding:replace", json={"quota_item_id": q2.id})
    assert rep.status_code == 200
    assert rep.json()["quota_item_id"] == q2.id

    rows = client.get(f"/api/boq-items/{boq.id}/quota-bindings").json()
    assert len(rows) == 1
    assert rows[0]["quota_item_id"] == q2.id

    clr = client.delete(f"/api/boq-items/{boq.id}/quota-bindings:clear")
    assert clr.status_code == 200
    assert clr.json()["removed"] == 1
    rows2 = client.get(f"/api/boq-items/{boq.id}/quota-bindings").json()
    assert rows2 == []


def test_batch_replace_bindings(client, db):
    r = client.post("/api/projects", json={"name": "BatchReplace", "region": "bj"})
    pid = r.json()["id"]
    boq1 = BoqItem(project_id=pid, code="BR-1", name="一", unit="m", quantity=1)
    boq2 = BoqItem(project_id=pid, code="BR-2", name="二", unit="m", quantity=1)
    q1 = QuotaItem(quota_code="BR-Q1", name="定额1", unit="m", labor_qty=1, material_qty=1, machine_qty=1)
    q2 = QuotaItem(quota_code="BR-Q2", name="定额2", unit="m", labor_qty=1, material_qty=1, machine_qty=1)
    db.add_all([boq1, boq2, q1, q2])
    db.commit()
    db.refresh(boq1)
    db.refresh(boq2)
    db.refresh(q1)
    db.refresh(q2)

    r = client.post(
        "/api/boq-items/quota-binding:batch-replace",
        json={"bindings": [
            {"boq_item_id": boq1.id, "quota_item_id": q1.id},
            {"boq_item_id": boq2.id, "quota_item_id": q2.id},
        ]},
    )
    assert r.status_code == 200
    assert len(r.json()) == 2

    assert len(client.get(f"/api/boq-items/{boq1.id}/quota-bindings").json()) == 1
    assert len(client.get(f"/api/boq-items/{boq2.id}/quota-bindings").json()) == 1


def test_dashboard_summary_endpoint(client, db):
    r = client.post("/api/projects", json={"name": "Dash", "region": "bj"})
    pid = r.json()["id"]

    boq1 = BoqItem(project_id=pid, code="D-A", name="已绑定", unit="m", quantity=1, is_dirty=0)
    boq2 = BoqItem(project_id=pid, code="D-B", name="未绑定", unit="m", quantity=1, is_dirty=1)
    q = QuotaItem(quota_code="D-Q", name="定额", unit="m", labor_qty=1, material_qty=1, machine_qty=1)
    db.add_all([boq1, boq2, q])
    db.commit()
    db.refresh(boq1)
    db.refresh(boq2)
    db.refresh(q)

    client.post(f"/api/boq-items/{boq1.id}/quota-binding:confirm", json={"quota_item_id": q.id})
    client.post(f"/api/projects/{pid}/comments", json={"author": "tester", "content": "ok"})

    s = client.get(f"/api/projects/{pid}/dashboard-summary")
    assert s.status_code == 200
    body = s.json()
    assert body["boq_count"] == 2
    assert body["unbound_count"] == 1
    assert body["dirty_count"] == 2
    assert body["validation_total"] >= 1
    assert body["recent_audit_count"] >= 1
    assert body["recent_comment_count"] == 1


def test_calculate_prefers_region_and_latest_effective_material_price(client, db):
    r_sh = client.post("/api/projects", json={"name": "RegionSH", "region": "sh"})
    pid_sh = r_sh.json()["id"]
    r_bj = client.post("/api/projects", json={"name": "RegionBJ", "region": "bj"})
    pid_bj = r_bj.json()["id"]

    boq_sh, q_sh = _seed_calc_case(db, pid_sh, "SH")
    boq_bj, q_bj = _seed_calc_case(db, pid_bj, "BJ")

    client.post(f"/api/boq-items/{boq_sh.id}/quota-binding:confirm", json={"quota_item_id": q_sh.id})
    client.post(f"/api/boq-items/{boq_bj.id}/quota-binding:confirm", json={"quota_item_id": q_bj.id})

    db.add_all([
        # Global fallback prices (high)
        MaterialPrice(code="G-L", name="人工费", unit="工日", unit_price=500, region="", effective_date="2025-01-01"),
        MaterialPrice(code="G-M", name="材料费", unit="t", unit_price=500, region="", effective_date="2025-01-01"),
        MaterialPrice(code="G-N", name="机械费", unit="台班", unit_price=500, region="", effective_date="2025-01-01"),
        # SH prices: old then new, should pick the newest effective one (100)
        MaterialPrice(code="SH-L-OLD", name="人工费", unit="工日", unit_price=50, region="sh", effective_date="2024-01-01"),
        MaterialPrice(code="SH-L-NEW", name="人工费", unit="工日", unit_price=100, region="sh", effective_date="2026-01-01"),
        MaterialPrice(code="SH-M-NEW", name="材料费", unit="t", unit_price=100, region="sh", effective_date="2026-01-01"),
        MaterialPrice(code="SH-N-NEW", name="机械费", unit="台班", unit_price=100, region="sh", effective_date="2026-01-01"),
    ])
    db.commit()

    sh_calc = client.post(f"/api/projects/{pid_sh}/calculate").json()
    bj_calc = client.post(f"/api/projects/{pid_bj}/calculate").json()

    assert sh_calc["line_results"][0]["direct_cost"] == 3000.0
    assert bj_calc["line_results"][0]["direct_cost"] == 15000.0
    assert sh_calc["grand_total"] < bj_calc["grand_total"]


def test_calculate_supports_multi_quota_composition_with_coefficient(client, db):
    r = client.post("/api/projects", json={"name": "MultiQuota", "region": "bj"})
    pid = r.json()["id"]

    boq = BoqItem(project_id=pid, code="MQ-1", name="组合定额项", unit="m", quantity=10)
    q1 = QuotaItem(quota_code="MQ-Q1", name="人工定额", unit="m", labor_qty=1, material_qty=0, machine_qty=0)
    q2 = QuotaItem(quota_code="MQ-Q2", name="材料定额", unit="m", labor_qty=0, material_qty=2, machine_qty=0)
    db.add_all([boq, q1, q2])
    db.commit()
    db.refresh(boq)
    db.refresh(q1)
    db.refresh(q2)

    client.post(
        "/api/boq-items/quota-binding:batch-confirm",
        json={"bindings": [
            {"boq_item_id": boq.id, "quota_item_id": q1.id, "coefficient": 1},
            {"boq_item_id": boq.id, "quota_item_id": q2.id, "coefficient": 0.5},
        ]},
    )

    calc = client.post(f"/api/projects/{pid}/calculate").json()
    line = calc["line_results"][0]
    assert line["direct_cost"] == 20.0
    assert line["total"] == 25.29


def test_provenance_contains_unit_price_and_breakdown(client, db):
    r = client.post("/api/projects", json={"name": "ProvBreakdown", "region": "bj"})
    pid = r.json()["id"]

    boq = BoqItem(project_id=pid, code="PB-1", name="溯源项", unit="m", quantity=10)
    quota = QuotaItem(quota_code="PB-Q1", name="溯源定额", unit="m", labor_qty=1, material_qty=0, machine_qty=0)
    db.add_all([boq, quota])
    db.commit()
    db.refresh(boq)
    db.refresh(quota)

    db.add(LineItemQuotaBinding(boq_item_id=boq.id, quota_item_id=quota.id, coefficient=1.5))
    db.commit()

    body = client.get(f"/api/calc-results/{boq.id}/provenance").json()
    assert body["unit_price"] is not None
    assert body["calc_breakdown"] is not None
    assert body["price_snapshot"]["labor_price"] > 0
    assert body["bindings"][0]["coefficient"] == 1.5
