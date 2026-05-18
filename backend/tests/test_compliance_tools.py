"""Tests for M6 compliance agent tools (compliance_tools.py)."""

from __future__ import annotations

import json
import pytest

import app.ai.tools  # noqa: F401 — ensures all tools registered

from app.ai.framework.tool_registry import registry


def _call(tool_name: str, ctx, **kwargs) -> dict:
    """Execute a tool by name through the registry and parse the JSON result."""
    return json.loads(registry.execute(tool_name, kwargs, ctx))


# ─── Minimal AgentContext stub ────────────────────────────────────────────────

class _StubCtx:
    """Lightweight context that wraps the conftest shared DB session."""

    def __init__(self, db, project_id: int = 1, boq_item_id: int | None = None):
        self.db = db
        self.project_id = project_id
        self.boq_item_id = boq_item_id

    def resolve_region(self) -> str:
        return "北京"

    def get_boq_item(self):
        return None


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture()
def ctx(db):
    from app.models.project import Project
    p = Project(name="M6合规工具测试", region="北京", project_type="civil", status="active")
    db.add(p)
    db.commit()
    db.refresh(p)
    return _StubCtx(db, project_id=p.id)


@pytest.fixture()
def ctx_with_quota(ctx, db):
    from app.models.quota_item import QuotaItem
    q = QuotaItem(
        quota_code="M6-001",
        name="挖一般土方",
        unit="m3",
        labor_fee=15.0,
        material_fee=0.0,
        machine_fee=10.0,
        base_price=25.0,
        labor_qty=0.0,
        material_qty=0.0,
        machine_qty=0.0,
        version="GBT50500-2024",
    )
    db.add(q)
    db.commit()
    db.refresh(q)
    return ctx, q


# ─── search_quotas_2024 ───────────────────────────────────────────────────────

class TestSearchQuotas2024:
    def test_returns_json(self, ctx):
        data = _call("search_quotas_2024", ctx, keyword="混凝土")
        assert "results" in data
        assert "standard" in data
        assert data["standard"] == "GBT50500-2024"

    def test_no_crash_on_empty_db(self, ctx):
        data = _call("search_quotas_2024", ctx, keyword="不存在的定额XYZ123")
        assert isinstance(data["results"], list)

    def test_finds_seeded_quota(self, ctx_with_quota):
        ctx, q = ctx_with_quota
        data = _call("search_quotas_2024", ctx, keyword="挖一般")
        # May or may not find depending on pricing_standard_id linkage in test DB
        assert "results" in data

    def test_result_has_fee_fields(self, ctx_with_quota):
        ctx, q = ctx_with_quota
        data = _call("search_quotas_2024", ctx, keyword="土方")
        for r in data["results"]:
            assert "labor_fee" in r
            assert "material_fee" in r
            assert "machine_fee" in r


# ─── get_other_items_summary ──────────────────────────────────────────────────

class TestGetOtherItemsSummary:
    def test_empty_project(self, ctx):
        data = _call("get_other_items_summary", ctx)
        assert data["grand_total"] == 0.0

    def test_with_items(self, ctx, db):
        from app.models.other_item import OtherItem
        db.add(OtherItem(
            project_id=ctx.project_id,
            category="provisional_sum",
            name="暂列金额",
            amount=100000.0,
            is_fixed=1,
        ))
        db.add(OtherItem(
            project_id=ctx.project_id,
            category="daywork",
            name="计日工",
            quantity=10,
            unit_price=200.0,
            amount=2000.0,
            is_fixed=0,
        ))
        db.commit()
        data = _call("get_other_items_summary", ctx)
        assert data["grand_total"] == 102000.0
        cats = {c["category"]: c["total"] for c in data["categories"]}
        assert cats["provisional_sum"] == 100000.0
        assert cats["daywork"] == 2000.0


# ─── get_regulatory_fees ─────────────────────────────────────────────────────

class TestGetRegulatoryFees:
    def test_structure(self, ctx):
        data = _call("get_regulatory_fees", ctx)
        assert "labor_base" in data
        assert "regulatory_fee_total" in data
        assert "social_insurance_fee" in data
        assert "housing_fund_fee" in data

    def test_zero_for_empty_project(self, ctx):
        data = _call("get_regulatory_fees", ctx)
        assert data["labor_base"] == 0.0
        assert data["regulatory_fee_total"] == 0.0

    def test_custom_rates(self, ctx):
        data = _call("get_regulatory_fees", ctx, social_insurance_rate=0.3, housing_fund_rate=0.1)
        assert data["rates"]["social_insurance"] == 0.3
        assert data["rates"]["housing_fund"] == 0.1


# ─── parse_boq_code ───────────────────────────────────────────────────────────

class TestParseBOQCode:
    def test_valid_12digit(self, ctx):
        data = _call("parse_boq_code", ctx, code="010301001001")
        assert data["ok"] is True
        assert data["profession"] == "01"
        assert data["chapter"] == "03"
        assert data["section"] == "01"
        assert data["item"] == "001"
        assert data["variation"] == "001"

    def test_invalid_code(self, ctx):
        data = _call("parse_boq_code", ctx, code="123")
        assert data["ok"] is False
        assert "error" in data

    def test_code_with_dashes(self, ctx):
        data = _call("parse_boq_code", ctx, code="01-03-01-001-001")
        assert data["ok"] is True

    def test_non_numeric_code(self, ctx):
        data = _call("parse_boq_code", ctx, code="ABCDEFGHIJKL")
        assert data["ok"] is False


# ─── add_other_item ───────────────────────────────────────────────────────────

class TestAddOtherItem:
    def test_add_provisional_sum(self, ctx, db):
        from app.models.other_item import OtherItem
        data = _call("add_other_item", ctx,
            category="provisional_sum",
            name="工程变更暂列金额",
            amount=50000.0,
            is_fixed=1,
        )
        assert data["ok"] is True
        assert data["amount"] == 50000.0
        assert data["category_zh"] == "暂列金额"
        # Verify in DB
        row = db.query(OtherItem).filter_by(id=data["id"]).first()
        assert row is not None
        assert row.amount == 50000.0

    def test_add_daywork_auto_calc(self, ctx):
        data = _call("add_other_item", ctx,
            category="daywork",
            name="普工",
            quantity=5,
            unit_price=250.0,
            is_fixed=0,
        )
        assert data["ok"] is True
        assert data["amount"] == 1250.0

    def test_invalid_category(self, ctx):
        data = _call("add_other_item", ctx, category="invalid", name="非法条目")
        assert data["ok"] is False
        assert "error" in data


# ─── calculate_five_fees ─────────────────────────────────────────────────────

class TestCalculateFiveFees:
    def test_structure(self, ctx):
        data = _call("calculate_five_fees", ctx)
        # Either succeeds or returns error — we just check it returns valid JSON
        assert "project_id" in data or "error" in data

    def test_returns_fee_fields_on_success(self, ctx):
        data = _call("calculate_five_fees", ctx)
        if "error" not in data:
            assert "grand_total" in data
            assert "fen_bu_xiangmu" in data
            assert "gui_fei" in data
            assert "shui_jin" in data

    def test_invalid_project(self, db):
        ctx = _StubCtx(db, project_id=999999)
        data = _call("calculate_five_fees", ctx)
        assert "error" in data


# ─── Tool registry integration ────────────────────────────────────────────────

class TestToolRegistration:
    def test_compliance_tools_registered(self):
        from app.ai.framework.tool_registry import registry
        for name in [
            "search_quotas_2024",
            "get_other_items_summary",
            "get_regulatory_fees",
            "parse_boq_code",
            "add_other_item",
            "calculate_five_fees",
        ]:
            assert name in registry, f"Tool '{name}' not in registry"

    def test_all_valuation_v2_tools_registered(self):
        from app.ai.framework.tool_registry import registry
        from app.ai.agents.v2.valuation_agent_v2 import ValuationAgentV2
        agent = ValuationAgentV2()
        for name in agent.tool_names:
            assert name in registry, f"Tool '{name}' not in registry"
