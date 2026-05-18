"""Tests for OtherItem CRUD API and 规费明细 endpoint — M5."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)

# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture()
def project_id():
    r = client.post("/api/projects", json={"name": "M5测试项目", "region": "北京"})
    assert r.status_code == 200
    return r.json()["id"]


@pytest.fixture()
def other_item(project_id):
    r = client.post(f"/api/projects/{project_id}/other-items", json={
        "category": "provisional_sum",
        "name": "工程变更暂列金额",
        "unit": "元",
        "quantity": 1,
        "unit_price": 0,
        "amount": 50000.0,
        "is_fixed": 1,
        "tax_mode": "tax",
        "sort_order": 1,
    })
    assert r.status_code == 200
    return type("Item", (), r.json())()


# ─── List / Create ───────────────────────────────────────────────────────────

class TestOtherItemCRUD:
    def test_list_empty(self, project_id):
        r = client.get(f"/api/projects/{project_id}/other-items")
        assert r.status_code == 200
        assert r.json() == []

    def test_create_provisional_sum(self, project_id):
        payload = {
            "category": "provisional_sum",
            "name": "暂列金额-工程变更",
            "unit": "元",
            "quantity": 1,
            "unit_price": 0,
            "amount": 100000.0,
            "is_fixed": 1,
        }
        r = client.post(f"/api/projects/{project_id}/other-items", json=payload)
        assert r.status_code == 200
        data = r.json()
        assert data["category"] == "provisional_sum"
        assert data["category_zh"] == "暂列金额"
        assert data["amount"] == 100000.0

    def test_create_daywork(self, project_id):
        payload = {
            "category": "daywork",
            "name": "普工",
            "unit": "工日",
            "quantity": 10,
            "unit_price": 200.0,
            "is_fixed": 0,
        }
        r = client.post(f"/api/projects/{project_id}/other-items", json=payload)
        assert r.status_code == 200
        data = r.json()
        assert data["amount"] == 2000.0  # 10 × 200

    def test_create_invalid_category(self, project_id):
        r = client.post(f"/api/projects/{project_id}/other-items", json={
            "category": "invalid_cat",
            "name": "非法类别",
        })
        assert r.status_code == 422

    def test_list_returns_items(self, project_id, other_item):
        r = client.get(f"/api/projects/{project_id}/other-items")
        assert r.status_code == 200
        items = r.json()
        assert len(items) >= 1
        assert any(it["id"] == other_item.id for it in items)

    def test_filter_by_category(self, project_id, other_item):
        r = client.get(f"/api/projects/{project_id}/other-items?category=provisional_sum")
        assert r.status_code == 200
        items = r.json()
        assert all(it["category"] == "provisional_sum" for it in items)

    def test_update_item(self, project_id, other_item):
        r = client.put(
            f"/api/projects/{project_id}/other-items/{other_item.id}",
            json={"amount": 80000.0, "note": "调整后金额"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["amount"] == 80000.0
        assert data["note"] == "调整后金额"

    def test_update_recalculates_non_fixed(self, project_id):
        r0 = client.post(f"/api/projects/{project_id}/other-items", json={
            "category": "daywork", "name": "电工", "unit": "工日",
            "quantity": 5, "unit_price": 300.0, "is_fixed": 0,
        })
        assert r0.status_code == 200
        item_id = r0.json()["id"]
        r = client.put(
            f"/api/projects/{project_id}/other-items/{item_id}",
            json={"quantity": 8},
        )
        assert r.status_code == 200
        assert r.json()["amount"] == 2400.0  # 8 × 300

    def test_delete_item(self, project_id):
        r0 = client.post(f"/api/projects/{project_id}/other-items", json={
            "category": "gc_service", "name": "总包服务费",
            "amount": 5000.0, "is_fixed": 1,
        })
        assert r0.status_code == 200
        item_id = r0.json()["id"]
        r = client.delete(f"/api/projects/{project_id}/other-items/{item_id}")
        assert r.status_code == 200
        assert r.json()["deleted"] is True
        # Confirm gone
        r2 = client.delete(f"/api/projects/{project_id}/other-items/{item_id}")
        assert r2.status_code == 404

    def test_delete_not_found(self, project_id):
        r = client.delete(f"/api/projects/{project_id}/other-items/999999")
        assert r.status_code == 404

    def test_update_invalid_category(self, project_id, other_item):
        r = client.put(
            f"/api/projects/{project_id}/other-items/{other_item.id}",
            json={"category": "bad_cat"},
        )
        assert r.status_code == 422


# ─── Summary endpoint ─────────────────────────────────────────────────────────

class TestOtherItemsSummary:
    def test_summary_structure(self, project_id, other_item):
        r = client.get(f"/api/projects/{project_id}/other-items/summary")
        assert r.status_code == 200
        data = r.json()
        assert "grand_total" in data
        assert "categories" in data
        assert len(data["categories"]) == 4

    def test_summary_totals(self, project_id):
        payloads = [
            {"category": "provisional_sum", "name": "暂列金额1", "amount": 100000.0, "is_fixed": 1},
            {"category": "provisional_price", "name": "暂估价1", "amount": 50000.0, "is_fixed": 1},
            {"category": "daywork", "name": "计日工1", "quantity": 10, "unit_price": 200.0, "is_fixed": 0},
        ]
        for p in payloads:
            client.post(f"/api/projects/{project_id}/other-items", json=p)

        r = client.get(f"/api/projects/{project_id}/other-items/summary")
        data = r.json()
        cats = {c["category"]: c["total"] for c in data["categories"]}
        assert cats["provisional_sum"] >= 100000.0
        assert cats["provisional_price"] == 50000.0
        assert cats["daywork"] == 2000.0


# ─── 规费明细 endpoint ────────────────────────────────────────────────────────

class TestRegulatoryFees:
    def test_regulatory_fees_structure(self, project_id):
        r = client.get(f"/api/projects/{project_id}/regulatory-fees")
        assert r.status_code == 200
        data = r.json()
        assert "labor_base" in data
        assert "regulatory_fee_total" in data
        assert "breakdown" in data
        assert len(data["breakdown"]) == 2
        assert "provenance" in data

    def test_regulatory_fees_zero_with_no_bindings(self, project_id):
        r = client.get(f"/api/projects/{project_id}/regulatory-fees")
        data = r.json()
        assert data["labor_base"] == 0.0
        assert data["regulatory_fee_total"] == 0.0

    def test_regulatory_fees_custom_rates(self, project_id):
        r = client.get(
            f"/api/projects/{project_id}/regulatory-fees"
            "?social_insurance_rate=0.3&housing_fund_rate=0.1"
        )
        assert r.status_code == 200
        data = r.json()
        assert data["social_insurance_rate"] == 0.3
        assert data["housing_fund_rate"] == 0.1
