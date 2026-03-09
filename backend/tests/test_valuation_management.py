from app.models.boq_item import BoqItem


def test_get_and_lock_valuation_standard(client):
    r = client.post("/api/projects", json={"name": "VM-STD", "region": "bj"})
    pid = r.json()["id"]

    cfg = client.get(f"/api/projects/{pid}/valuation-management/config").json()
    assert cfg["standard_code"] == "GB/T50500-2024"
    assert cfg["locked"] is False

    locked = client.put(
        f"/api/projects/{pid}/valuation-management/config",
        json={
            "standard_code": "GB/T50500-2024",
            "standard_name": "建设工程工程量清单计价标准",
            "effective_date": "2025-09-01",
            "lock_standard": True,
        },
    )
    assert locked.status_code == 200
    assert locked.json()["locked"] is True

    switched = client.put(
        f"/api/projects/{pid}/valuation-management/config",
        json={
            "standard_code": "GB/T50500-2013",
            "standard_name": "旧版",
            "effective_date": "2013-01-01",
            "lock_standard": True,
        },
    )
    assert switched.status_code == 400


def test_contract_measurement_create_and_approve(client, db):
    r = client.post("/api/projects", json={"name": "VM-MEASURE", "region": "sh"})
    pid = r.json()["id"]
    boq = BoqItem(project_id=pid, code="M-001", name="土方开挖", unit="m3", quantity=100)
    db.add(boq)
    db.commit()
    db.refresh(boq)

    m1 = client.post(
        f"/api/projects/{pid}/valuation-management/measurements",
        json={
            "boq_item_id": boq.id,
            "period_label": "2026-03",
            "measured_qty": 30,
            "note": "首期计量",
        },
    )
    assert m1.status_code == 200
    assert m1.json()["cumulative_qty"] == 30
    assert m1.json()["status"] == "draft"

    approved = client.post(
        f"/api/projects/{pid}/valuation-management/measurements/{m1.json()['id']}:approve",
        json={"approved_by": "监理A"},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["approved_by"] == "监理A"


def test_adjustment_payment_and_overview(client):
    r = client.post("/api/projects", json={"name": "VM-OV", "region": "gd"})
    pid = r.json()["id"]

    adj = client.post(
        f"/api/projects/{pid}/valuation-management/adjustments",
        json={
            "adjustment_type": "material_price_change",
            "amount": 20000,
            "reason": "钢材上涨",
            "status": "approved",
        },
    )
    assert adj.status_code == 200
    assert adj.json()["amount"] == 20000

    pay = client.post(
        f"/api/projects/{pid}/valuation-management/payments",
        json={
            "period_label": "2026-Q1",
            "gross_amount": 300000,
            "prepayment_deduction": 50000,
            "retention": 10000,
            "paid_amount": 100000,
            "status": "issued",
        },
    )
    assert pay.status_code == 200
    assert pay.json()["net_payable"] == 240000

    overview = client.get(f"/api/projects/{pid}/valuation-management/overview")
    assert overview.status_code == 200
    body = overview.json()
    assert body["adjustment_count"] == 1
    assert body["payment_count"] == 1
    assert body["adjustment_total"] == 20000
    assert body["payment_net_total"] == 240000

