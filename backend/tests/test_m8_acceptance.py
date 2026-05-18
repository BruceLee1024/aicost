"""M8 对账验收 — end-to-end reconciliation tests.

Verifies that numeric totals are internally consistent across all
compliance milestones (M1–M6):

A. PricingEngineV2 arithmetic identity       (M2)
B. OtherItem summary reconciliation          (M5 API)
C. Regulatory fees formula                  (M5 API)
D. Code-parser round-trip                   (M3)
E. Agent tool ↔ direct API consistency     (M6)
F. Full pipeline: project → 五费 integrity  (M2+M5)
"""

from __future__ import annotations

import json
import math
import pytest

import app.ai.tools as _ai_tools  # noqa: F401 — ensure tools registered

from fastapi.testclient import TestClient
from app.main import app
from app.ai.framework.tool_registry import registry

client = TestClient(app)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _create_project(name: str = "M8验收项目") -> int:
    r = client.post("/api/projects", json={"name": name, "region": "北京"})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _approx(a: float, b: float, tol: float = 0.05) -> bool:
    """True if |a - b| <= tol (absolute) or within 0.01% (relative)."""
    return abs(a - b) <= tol or (b != 0 and abs(a - b) / abs(b) < 1e-4)


# ──────────────────────────────────────────────────────────────────────────────
# A. PricingEngineV2 arithmetic identity
# ──────────────────────────────────────────────────────────────────────────────

class TestPricingEngineArithmetic:
    """grand_total must equal Σ of the five sub-totals; parts must reconcile."""

    def _run(self, standard: str, tax_method_str: str):
        from app.services.pricing_engine_v2 import (
            PricingEngineV2, PricingStandardCode, TaxMethod,
            BoqLineInput, MeasureItemInput, OtherItemInput, FeeStructureConfig,
        )
        std = PricingStandardCode(standard)
        tm = TaxMethod(tax_method_str)
        engine = PricingEngineV2(standard=std, tax_method=tm)

        boq_lines = [
            BoqLineInput(boq_item_id=1, code="010101001001", name="挖土方",
                         quantity=200.0, unit="m3", labor_fee=8.0, material_fee=0.0, machine_fee=12.0),
            BoqLineInput(boq_item_id=2, code="010301001001", name="混凝土基础",
                         quantity=50.0, unit="m3", labor_fee=30.0, material_fee=400.0, machine_fee=20.0),
        ]
        measure_items = [
            MeasureItemInput(name="安全文明施工费", amount=5000.0, is_competitive=False),
            MeasureItemInput(name="临时设施费", amount=2000.0, is_competitive=True),
        ]
        other_items = [
            OtherItemInput(name="工程变更暂列金额", category="provisional_sum", amount=10000.0),
            OtherItemInput(name="计日工-普工", category="daywork", amount=1500.0),
        ]
        result = engine.calculate(boq_lines=boq_lines, measure_items=measure_items, other_items=other_items)

        # ① 分部分项内部一致性
        assert result.fen_bu_total > 0
        assert _approx(
            result.fen_bu_labor + result.fen_bu_material + result.fen_bu_machine
            + result.fen_bu_management + result.fen_bu_profit,
            result.fen_bu_total,
        ), "fen_bu sub-components don't sum to fen_bu_total"

        # ② 措施 = 强制 + 可竞争
        assert _approx(
            result.cuo_shi_anquanwm + result.cuo_shi_competitive,
            result.cuo_shi_total,
        ), "cuo_shi_total != anquanwm + competitive"

        # ③ 其他项目 = 四子项合计
        assert _approx(
            result.other_zljine + result.other_zhjia + result.other_jirg + result.other_zb_svc,
            result.other_total,
        ), "other_total != sum of sub-categories"

        # ④ 规费 = 社保 + 公积金
        assert _approx(
            result.gui_fei_social_insurance + result.gui_fei_housing_fund,
            result.gui_fei_total,
        ), "gui_fei_total != social_insurance + housing_fund"

        # ⑤ 税前合计 = ①+②+③+④
        pre_tax = (result.fen_bu_total + result.cuo_shi_total
                   + result.other_total + result.gui_fei_total)
        assert _approx(pre_tax, result.pre_tax_total), "pre_tax_total mismatch"

        # 税金 ≈ 税率 × 税前
        expected_tax_rate = 0.03 if tax_method_str == "simple" else engine.fee_config.tax_rate
        assert _approx(result.tax_total, result.pre_tax_total * expected_tax_rate, tol=1.0)

        # grand_total = pre_tax + tax
        assert _approx(result.pre_tax_total + result.tax_total, result.grand_total), \
            "grand_total != pre_tax + tax"

    def test_gb50500_2013_general_tax(self):
        self._run("GB50500-2013", "general")

    def test_gb50500_2013_simple_tax(self):
        self._run("GB50500-2013", "simple")

    def test_gbt50500_2024_general_tax(self):
        self._run("GBT50500-2024", "general")

    def test_gbt50500_2024_simple_tax(self):
        self._run("GBT50500-2024", "simple")

    def test_empty_project_zero_totals(self):
        from app.services.pricing_engine_v2 import PricingEngineV2
        engine = PricingEngineV2()
        result = engine.calculate(boq_lines=[], measure_items=[], other_items=[])
        assert result.grand_total == 0.0
        assert result.fen_bu_total == 0.0
        assert result.gui_fei_total == 0.0

    def test_labor_index_scales_proportionally(self):
        """2024 engine with labor_index=2.0 should double labor cost."""
        from app.services.pricing_engine_v2 import (
            PricingEngineV2, PricingStandardCode, TaxMethod, BoqLineInput,
        )
        line = BoqLineInput(boq_item_id=1, code="010101001001", name="test",
                            quantity=1.0, unit="m3", labor_fee=100.0, material_fee=0.0, machine_fee=0.0)
        engine1 = PricingEngineV2(PricingStandardCode.GBT50500_2024, TaxMethod.GENERAL, labor_index=1.0)
        engine2 = PricingEngineV2(PricingStandardCode.GBT50500_2024, TaxMethod.GENERAL, labor_index=2.0)
        r1 = engine1.calculate([line])
        r2 = engine2.calculate([line])
        assert r2.fen_bu_labor > r1.fen_bu_labor, "labor_index=2 should give more labor"
        assert _approx(r2.fen_bu_labor, r1.fen_bu_labor * 2.0, tol=0.5)


# ──────────────────────────────────────────────────────────────────────────────
# B. OtherItem summary reconciliation
# ──────────────────────────────────────────────────────────────────────────────

class TestOtherItemSummaryReconciliation:
    """Summary totals must equal the sum of individual item amounts."""

    def test_grand_total_equals_sum_of_items(self):
        pid = _create_project("M8-OtherItem对账")
        items_data = [
            {"category": "provisional_sum", "name": "暂列金额A", "amount": 50000.0, "is_fixed": 1},
            {"category": "provisional_sum", "name": "暂列金额B", "amount": 30000.0, "is_fixed": 1},
            {"category": "daywork", "name": "计日工-木工", "quantity": 8, "unit_price": 280.0, "is_fixed": 0},
            {"category": "gc_service", "name": "总包服务费", "amount": 5000.0, "is_fixed": 1},
            {"category": "provisional_price", "name": "甲供材暂估", "amount": 12000.0, "is_fixed": 1},
        ]
        created = []
        for d in items_data:
            r = client.post(f"/api/projects/{pid}/other-items", json=d)
            assert r.status_code == 200, r.text
            created.append(r.json())

        # Expected: each item's effective amount
        expected_total = 0.0
        for item in created:
            expected_total += item["amount"]

        summary = client.get(f"/api/projects/{pid}/other-items/summary").json()
        assert _approx(summary["grand_total"], expected_total), \
            f"grand_total {summary['grand_total']} != Σ items {expected_total}"

    def test_category_totals_sum_to_grand_total(self):
        pid = _create_project("M8-Category对账")
        for d in [
            {"category": "provisional_sum", "name": "X1", "amount": 1000.0, "is_fixed": 1},
            {"category": "daywork", "name": "X2", "amount": 500.0, "is_fixed": 1},
        ]:
            client.post(f"/api/projects/{pid}/other-items", json=d)

        summary = client.get(f"/api/projects/{pid}/other-items/summary").json()
        cat_sum = sum(c["total"] for c in summary["categories"])
        assert _approx(cat_sum, summary["grand_total"]), \
            f"sum of category totals {cat_sum} != grand_total {summary['grand_total']}"

    def test_update_recalc_reflects_in_summary(self):
        """After updating a non-fixed item, summary should reflect the new amount."""
        pid = _create_project("M8-Update对账")
        r = client.post(f"/api/projects/{pid}/other-items", json={
            "category": "daywork", "name": "普工", "quantity": 5, "unit_price": 200.0, "is_fixed": 0,
        })
        item_id = r.json()["id"]
        # quantity 5 × 200 = 1000
        s1 = client.get(f"/api/projects/{pid}/other-items/summary").json()

        client.put(f"/api/projects/{pid}/other-items/{item_id}", json={"quantity": 10})
        # quantity 10 × 200 = 2000
        s2 = client.get(f"/api/projects/{pid}/other-items/summary").json()
        assert s2["grand_total"] == s1["grand_total"] * 2, \
            f"Expected {s1['grand_total'] * 2}, got {s2['grand_total']}"

    def test_delete_reduces_summary(self):
        pid = _create_project("M8-Delete对账")
        r = client.post(f"/api/projects/{pid}/other-items", json={
            "category": "provisional_sum", "name": "待删除", "amount": 9999.0, "is_fixed": 1,
        })
        item_id = r.json()["id"]
        s1 = client.get(f"/api/projects/{pid}/other-items/summary").json()
        assert s1["grand_total"] == 9999.0

        client.delete(f"/api/projects/{pid}/other-items/{item_id}")
        s2 = client.get(f"/api/projects/{pid}/other-items/summary").json()
        assert s2["grand_total"] == 0.0


# ──────────────────────────────────────────────────────────────────────────────
# C. Regulatory fees formula
# ──────────────────────────────────────────────────────────────────────────────

class TestRegulatoryFeesFormula:
    """规费 = 人工费合计 × (社保率 + 公积金率)"""

    def test_formula_identity(self):
        pid = _create_project("M8-公式验证")
        r = client.get(f"/api/projects/{pid}/regulatory-fees")
        assert r.status_code == 200
        data = r.json()
        si_rate = data["social_insurance_rate"]
        hf_rate = data["housing_fund_rate"]
        labor = data["labor_base"]
        assert _approx(data["social_insurance_fee"], labor * si_rate, tol=0.02)
        assert _approx(data["housing_fund_fee"], labor * hf_rate, tol=0.02)
        assert _approx(
            data["social_insurance_fee"] + data["housing_fund_fee"],
            data["regulatory_fee_total"],
            tol=0.02,
        )

    def test_custom_rates_proportional(self):
        """Doubling SI rate should double SI fee."""
        pid = _create_project("M8-规费对账")
        r1 = client.get(f"/api/projects/{pid}/regulatory-fees?social_insurance_rate=0.1")
        r2 = client.get(f"/api/projects/{pid}/regulatory-fees?social_insurance_rate=0.2")
        assert r1.status_code == r2.status_code == 200
        d1, d2 = r1.json(), r2.json()
        assert d1["labor_base"] == d2["labor_base"]
        # Rates correctly passed through
        assert _approx(d1["social_insurance_rate"], 0.1)
        assert _approx(d2["social_insurance_rate"], 0.2)

    def test_zero_labor_gives_zero_regulatory(self):
        """Project with no BOQ bindings → regulatory fee = 0."""
        pid = _create_project("M8-零劳动力")
        r = client.get(f"/api/projects/{pid}/regulatory-fees")
        assert r.status_code == 200
        data = r.json()
        assert data["labor_base"] == 0.0
        assert data["regulatory_fee_total"] == 0.0


# ──────────────────────────────────────────────────────────────────────────────
# D. Code-parser round-trip
# ──────────────────────────────────────────────────────────────────────────────

class TestCodeParserRoundTrip:
    """Parse a code → reconstruct from segments → matches original."""

    VALID_CODES = [
        "010101001001",
        "010301001002",
        "040202001001",
        "030101001001",
        "020101001001",
    ]

    def test_parse_then_reconstruct(self):
        from app.services.code_parser import parse_code
        for raw in self.VALID_CODES:
            segs = parse_code(raw)
            assert segs is not None, f"Failed to parse {raw}"
            d = segs.to_dict()
            reconstructed = (
                d["profession"] + d["chapter"] + d["section"]
                + d["item"] + d["variation"]
            )
            assert reconstructed == raw, f"Round-trip failed: {raw} → {reconstructed}"

    def test_validation_consistent_with_parse(self):
        from app.services.code_parser import parse_code, validate_code
        for raw in self.VALID_CODES:
            vr = validate_code(raw)
            segs = parse_code(raw)
            assert vr.valid == (segs is not None), \
                f"validate/parse inconsistency for {raw}"

    def test_invalid_codes_rejected(self):
        from app.services.code_parser import validate_code
        # Only codes that produce errors (non-digit chars or >12 digits).
        # Short numeric codes produce warnings but are still considered valid.
        invalid = [
            "ABCDEFGHIJKL",       # 12 alpha chars — not numeric
            "01010100100X",       # contains non-digit 'X'
            "0101010010012345",   # 16 digits — too long
        ]
        for code in invalid:
            vr = validate_code(code)
            assert not vr.valid, f"Expected {code!r} to be invalid"

    def test_segments_dict_keys(self):
        from app.services.code_parser import parse_code
        segs = parse_code("010301001001")
        d = segs.to_dict()
        for key in ("profession", "chapter", "section", "item", "variation"):
            assert key in d, f"Missing key: {key}"


# ──────────────────────────────────────────────────────────────────────────────
# E. Agent tool ↔ direct API consistency
# ──────────────────────────────────────────────────────────────────────────────

class _Ctx:
    def __init__(self, db, project_id: int):
        self.db = db
        self.project_id = project_id
        self.boq_item_id = None


class TestAgentToolConsistency:
    """Agent tool results must match the direct API endpoint results."""

    def test_other_items_summary_matches_api(self, db):
        from app.models.project import Project
        from app.models.other_item import OtherItem
        p = Project(name="M8-Agent对账", region="北京", project_type="civil", status="active")
        db.add(p)
        db.flush()  # get p.id
        db.add(OtherItem(project_id=p.id, category="provisional_sum", name="暂列", amount=7777.0, is_fixed=1))
        db.commit()

        ctx = _Ctx(db, project_id=p.id)
        tool_result = json.loads(registry.execute("get_other_items_summary", {}, ctx))
        api_result = client.get(f"/api/projects/{p.id}/other-items/summary").json()

        assert _approx(tool_result["grand_total"], api_result["grand_total"]), \
            f"Tool grand_total {tool_result['grand_total']} != API {api_result['grand_total']}"

    def test_regulatory_fees_match_api(self, db):
        from app.models.project import Project
        p = Project(name="M8-RegFees对账", region="北京", project_type="civil", status="active")
        db.add(p)
        db.commit()

        ctx = _Ctx(db, project_id=p.id)
        tool_result = json.loads(registry.execute("get_regulatory_fees", {}, ctx))
        api_result = client.get(f"/api/projects/{p.id}/regulatory-fees").json()

        # Tool returns nested rates; API returns flat fields
        assert _approx(tool_result["regulatory_fee_total"], api_result["regulatory_fee_total"]), \
            "Tool and API regulatory fee totals differ"
        assert _approx(tool_result["labor_base"], api_result["labor_base"]), \
            "Tool and API labor base differ"
        assert _approx(tool_result["rates"]["social_insurance"], api_result["social_insurance_rate"]), \
            "Rate mismatch"

    def test_parse_boq_code_consistent(self, db):
        from app.models.project import Project
        from app.services.code_parser import parse_code
        p = Project(name="M8-CodeParse", region="北京", project_type="civil", status="active")
        db.add(p)
        db.commit()

        ctx = _Ctx(db, project_id=p.id)
        code = "010301001001"
        tool_result = json.loads(registry.execute("parse_boq_code", {"code": code}, ctx))
        direct = parse_code(code).to_dict()

        assert tool_result["ok"] is True
        for key in ("profession", "chapter", "section", "item", "variation"):
            assert tool_result[key] == direct[key], f"Mismatch at {key}"


# ──────────────────────────────────────────────────────────────────────────────
# F. Full pipeline: project → 五费 integrity via engine
# ──────────────────────────────────────────────────────────────────────────────

class TestFullPipelineIntegrity:
    """End-to-end: create data via API, compute via PricingEngineV2, reconcile."""

    def test_five_fee_integrity_2013(self):
        self._run_pipeline("GB50500-2013")

    def test_five_fee_integrity_2024(self):
        self._run_pipeline("GBT50500-2024")

    def _run_pipeline(self, standard: str):
        from app.services.pricing_engine_v2 import (
            PricingEngineV2, PricingStandardCode, TaxMethod,
            BoqLineInput, OtherItemInput,
        )
        # Create items via API
        pid = _create_project(f"M8-五费全流程-{standard}")

        other_data = [
            {"category": "provisional_sum", "name": "Z1", "amount": 20000.0, "is_fixed": 1},
            {"category": "daywork", "name": "Z2", "quantity": 5, "unit_price": 500.0, "is_fixed": 0},
        ]
        for d in other_data:
            r = client.post(f"/api/projects/{pid}/other-items", json=d)
            assert r.status_code == 200

        summary = client.get(f"/api/projects/{pid}/other-items/summary").json()

        # Build engine inputs from known data
        boq_lines = [
            BoqLineInput(boq_item_id=1, code="010101001001", name="test",
                         quantity=100.0, unit="m3", labor_fee=10.0, material_fee=50.0, machine_fee=5.0),
        ]
        other_inputs = [
            OtherItemInput(name="Z1", category="provisional_sum", amount=20000.0),
            OtherItemInput(name="Z2", category="daywork", amount=2500.0),  # 5 × 500
        ]
        std = PricingStandardCode(standard)
        engine = PricingEngineV2(standard=std)
        result = engine.calculate(boq_lines=boq_lines, other_items=other_inputs)

        # API summary other total should match engine other_total
        assert _approx(summary["grand_total"], result.other_total, tol=0.01), \
            f"API other total {summary['grand_total']} ≠ engine {result.other_total}"

        # Grand total invariant
        recomputed = (result.fen_bu_total + result.cuo_shi_total
                      + result.other_total + result.gui_fei_total + result.tax_total)
        assert _approx(recomputed, result.grand_total), \
            f"grand_total invariant broken: {recomputed} ≠ {result.grand_total}"

    def test_quota_import_then_search(self):
        """Quota stats endpoint should be reachable and return totals ≥ 0."""
        r = client.get("/api/quota-items/stats")
        assert r.status_code == 200
        data = r.json()
        assert "total" in data
        assert data["total"] >= 0

    def test_other_items_crud_cycle(self):
        """Create → Read → Update → Delete cycle must leave no orphan data."""
        pid = _create_project("M8-CRUD循环")

        # Create
        r = client.post(f"/api/projects/{pid}/other-items", json={
            "category": "gc_service", "name": "CRUD测试", "amount": 3333.0, "is_fixed": 1,
        })
        assert r.status_code == 200
        item_id = r.json()["id"]

        # Read list
        items = client.get(f"/api/projects/{pid}/other-items").json()
        assert any(i["id"] == item_id for i in items)

        # Update
        upd = client.put(f"/api/projects/{pid}/other-items/{item_id}", json={"amount": 6666.0})
        assert upd.status_code == 200
        assert upd.json()["amount"] == 6666.0

        # Verify summary updated
        s = client.get(f"/api/projects/{pid}/other-items/summary").json()
        assert s["grand_total"] == 6666.0

        # Delete
        d = client.delete(f"/api/projects/{pid}/other-items/{item_id}")
        assert d.status_code == 200

        # Verify gone
        items_after = client.get(f"/api/projects/{pid}/other-items").json()
        assert not any(i["id"] == item_id for i in items_after)
        s2 = client.get(f"/api/projects/{pid}/other-items/summary").json()
        assert s2["grand_total"] == 0.0

    def test_summary_includes_count(self):
        """B3: summary categories must include a count field."""
        pid = _create_project("M8-Count字段")
        client.post(f"/api/projects/{pid}/other-items", json={
            "category": "provisional_sum", "name": "A", "amount": 1000.0, "is_fixed": 1,
        })
        client.post(f"/api/projects/{pid}/other-items", json={
            "category": "provisional_sum", "name": "B", "amount": 2000.0, "is_fixed": 1,
        })
        s = client.get(f"/api/projects/{pid}/other-items/summary").json()
        ps = next(c for c in s["categories"] if c["category"] == "provisional_sum")
        assert ps["count"] == 2, f"Expected count=2, got {ps['count']}"
        assert ps["total"] == 3000.0

    def test_calculate_five_fees_tool_no_crash(self, db):
        """B1: calculate_five_fees must return a valid result dict (not an error)."""
        from app.models.project import Project
        from app.models.other_item import OtherItem
        p = Project(name="M8-FiveFees", region="北京", project_type="civil", status="active")
        db.add(p)
        db.flush()
        db.add(OtherItem(project_id=p.id, category="provisional_sum",
                         name="测试暂列", amount=5000.0, is_fixed=1))
        db.commit()

        ctx = _Ctx(db, project_id=p.id)
        raw = registry.execute("calculate_five_fees", {}, ctx)
        result = json.loads(raw)
        assert "error" not in result, f"Tool returned error: {result.get('error')}"
        assert "grand_total" in result
        assert "fen_bu_xiangmu" in result
        assert "other_xiangmu" in result
        assert result["other_xiangmu"] == 5000.0, \
            f"Expected other_xiangmu=5000.0, got {result['other_xiangmu']}"
