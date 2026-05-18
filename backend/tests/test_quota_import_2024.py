"""Tests for quota_import_2024 service and updated quota-items API — M4."""

from __future__ import annotations

import io
import json
import pytest
import openpyxl

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.quota_item import QuotaItem
from app.models.pricing_standard import PricingStandard
from app.services.quota_import_2024 import import_quota_excel, seed_quota_items


# ---------------------------------------------------------------------------
# In-memory DB fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def engine():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture()
def db_session(engine):
    Session = sessionmaker(bind=engine)
    session = Session()
    # Seed a GBT50500-2024 standard row
    if not session.query(PricingStandard).filter_by(code="GBT50500-2024").first():
        session.add(PricingStandard(
            code="GBT50500-2024", name_zh="2024标准", name_en="2024 Standard",
            year=2024, region="全国", profession="general",
            coding_rule_json="{}", fee_structure_json="{}",
            rounding_rule="round2", is_active=1,
        ))
        session.commit()
    yield session
    session.rollback()
    session.close()


@pytest.fixture()
def client(db_session, engine):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as c:
            yield c
    finally:
        if previous is not None:
            app.dependency_overrides[get_db] = previous
        else:
            app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# Helper: build a minimal Excel file in memory
# ---------------------------------------------------------------------------

def _make_excel(rows: list[dict]) -> bytes:
    """Create a minimal xlsx with headers matching the importer expectations."""
    wb = openpyxl.Workbook()
    ws = wb.active
    headers = ["定额编号", "定额名称", "单位", "人工费", "材料费", "机械费", "合计", "章节", "工作内容"]
    ws.append(headers)
    for row in rows:
        ws.append([
            row.get("定额编号", ""),
            row.get("定额名称", ""),
            row.get("单位", "m3"),
            row.get("人工费", 0),
            row.get("材料费", 0),
            row.get("机械费", 0),
            row.get("合计", 0),
            row.get("章节", ""),
            row.get("工作内容", ""),
        ])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# seed_quota_items (programmatic helper)
# ---------------------------------------------------------------------------

class TestSeedQuotaItems:
    def test_insert_new_items(self, db_session):
        items = [
            {"quota_code": "T2024-001", "name": "挖一般土方", "unit": "m3",
             "labor_fee": 15.0, "material_fee": 0.0, "machine_fee": 10.0},
            {"quota_code": "T2024-002", "name": "现浇混凝土", "unit": "m3",
             "labor_fee": 60.0, "material_fee": 400.0, "machine_fee": 25.0},
        ]
        result = seed_quota_items(items, db_session, standard_code="GBT50500-2024")
        assert result.imported == 2
        assert result.updated == 0
        assert result.errors == []

    def test_upsert_updates_existing(self, db_session):
        items = [{"quota_code": "T2024-001", "name": "挖一般土方（更新）",
                  "labor_fee": 18.0, "material_fee": 0.0, "machine_fee": 12.0}]
        result = seed_quota_items(items, db_session, standard_code="GBT50500-2024", upsert=True)
        assert result.updated == 1
        updated = db_session.query(QuotaItem).filter_by(quota_code="T2024-001").first()
        assert updated.name == "挖一般土方（更新）"
        assert updated.labor_fee == 18.0

    def test_skip_when_upsert_false(self, db_session):
        items = [{"quota_code": "T2024-001", "name": "应被跳过",
                  "labor_fee": 99.0, "material_fee": 0.0, "machine_fee": 0.0}]
        result = seed_quota_items(items, db_session, standard_code="GBT50500-2024", upsert=False)
        assert result.skipped == 1
        unchanged = db_session.query(QuotaItem).filter_by(quota_code="T2024-001").first()
        assert unchanged.name != "应被跳过"

    def test_skip_empty_code(self, db_session):
        items = [{"quota_code": "", "name": "无编号项"}]
        result = seed_quota_items(items, db_session)
        assert result.skipped == 1

    def test_base_price_auto_derived(self, db_session):
        items = [{"quota_code": "T2024-003", "name": "砌砖墙", "unit": "m3",
                  "labor_fee": 40.0, "material_fee": 200.0, "machine_fee": 5.0}]
        seed_quota_items(items, db_session, standard_code="GBT50500-2024")
        row = db_session.query(QuotaItem).filter_by(quota_code="T2024-003").first()
        assert row.base_price == 245.0

    def test_standard_id_linked(self, db_session):
        std = db_session.query(PricingStandard).filter_by(code="GBT50500-2024").first()
        row = db_session.query(QuotaItem).filter_by(quota_code="T2024-003").first()
        assert row.pricing_standard_id == std.id


# ---------------------------------------------------------------------------
# import_quota_excel (Excel importer)
# ---------------------------------------------------------------------------

class TestImportQuotaExcel:
    def test_import_from_xlsx(self, db_session):
        xlsx = _make_excel([
            {"定额编号": "XL-001", "定额名称": "挖土方", "单位": "m3",
             "人工费": 12.0, "材料费": 0.0, "机械费": 8.0, "章节": "土石方工程"},
            {"定额编号": "XL-002", "定额名称": "砌砖", "单位": "m3",
             "人工费": 45.0, "材料费": 150.0, "机械费": 5.0, "章节": "砌筑工程"},
        ])
        result = import_quota_excel(xlsx, db_session, standard_code="GBT50500-2024")
        assert result.imported == 2
        assert result.errors == []

    def test_chapter_attached(self, db_session):
        row = db_session.query(QuotaItem).filter_by(quota_code="XL-001").first()
        assert row is not None
        assert row.chapter == "土石方工程"

    def test_invalid_file_returns_error(self, db_session):
        result = import_quota_excel(b"NOT AN EXCEL FILE", db_session)
        assert len(result.errors) > 0

    def test_no_header_returns_error(self, db_session):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["Col1", "Col2"])  # unrecognised headers
        ws.append(["A", "B"])
        buf = io.BytesIO()
        wb.save(buf)
        result = import_quota_excel(buf.getvalue(), db_session)
        assert any("表头" in e for e in result.errors)

    def test_upsert_on_reimport(self, db_session):
        xlsx = _make_excel([
            {"定额编号": "XL-001", "定额名称": "挖土方（更新版）", "单位": "m3",
             "人工费": 14.0, "材料费": 0.0, "机械费": 9.0},
        ])
        result = import_quota_excel(xlsx, db_session, upsert=True, standard_code="GBT50500-2024")
        assert result.updated == 1
        row = db_session.query(QuotaItem).filter_by(quota_code="XL-001").first()
        assert row.labor_fee == 14.0


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------

class TestQuotaItemsAPI:
    def test_list_quota_items_basic(self, client):
        r = client.get("/api/quota-items?limit=5")
        assert r.status_code == 200
        data = r.json()
        assert "total" in data
        assert "items" in data

    def test_list_includes_fee_fields(self, client):
        r = client.get("/api/quota-items?limit=1&detailed=true")
        assert r.status_code == 200
        items = r.json()["items"]
        if items:
            assert "labor_fee" in items[0]
            assert "work_content" in items[0]

    def test_filter_by_profession(self, client):
        r = client.get("/api/quota-items?profession=房建&limit=5")
        assert r.status_code == 200

    def test_filter_by_standard_code(self, client):
        r = client.get("/api/quota-items?standard_code=GBT50500-2024&limit=5")
        assert r.status_code == 200

    def test_get_quota_item_detail(self, client, db_session):
        row = db_session.query(QuotaItem).first()
        if row:
            r = client.get(f"/api/quota-items/{row.id}")
            assert r.status_code == 200
            data = r.json()
            assert data["quota_code"] == row.quota_code
            assert "work_content" in data

    def test_get_quota_item_404(self, client):
        r = client.get("/api/quota-items/999999")
        assert r.status_code == 404

    def test_import_endpoint_rejects_non_xlsx(self, client):
        r = client.post(
            "/api/quota-items/import-2024",
            files={"file": ("bad.csv", b"a,b,c", "text/csv")},
        )
        assert r.status_code == 400

    def test_import_endpoint_xlsx(self, client):
        xlsx = _make_excel([
            {"定额编号": "API-001", "定额名称": "测试定额", "单位": "m2",
             "人工费": 20.0, "材料费": 80.0, "机械费": 5.0},
        ])
        r = client.post(
            "/api/quota-items/import-2024",
            files={"file": ("test.xlsx", xlsx,
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        assert r.status_code == 200
        data = r.json()
        assert "imported" in data
        assert "errors" in data

    def test_stats_endpoint(self, client):
        r = client.get("/api/quota-items/stats")
        assert r.status_code == 200
        data = r.json()
        assert "total" in data
        assert "chapters" in data
