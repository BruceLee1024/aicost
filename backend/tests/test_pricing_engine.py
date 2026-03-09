from app.services.pricing_engine import (
    FeeConfig,
    calculate_line_item,
    calculate_line_item_total,
    calculate_project,
)


# ---------------------------------------------------------------------------
# Legacy helper (direct cost only)
# ---------------------------------------------------------------------------

def test_calculate_line_item_total() -> None:
    total = calculate_line_item_total(
        labor_qty=2,
        labor_price=100,
        material_qty=3,
        material_price=50,
        machine_qty=1.5,
        machine_price=80,
    )
    assert total == 470.0


def test_zero_inputs() -> None:
    total = calculate_line_item_total(
        labor_qty=0, labor_price=0,
        material_qty=0, material_price=0,
        machine_qty=0, machine_price=0,
    )
    assert total == 0.0


# ---------------------------------------------------------------------------
# Full line‑item calculation with fees + tax
# ---------------------------------------------------------------------------

def test_calculate_line_item_with_fees() -> None:
    cfg = FeeConfig(
        management_rate=0.08,
        profit_rate=0.05,
        regulatory_rate=0.03,
        tax_rate=0.09,
    )
    r = calculate_line_item(
        labor_qty=2, labor_price=100,
        material_qty=3, material_price=50,
        machine_qty=1.5, machine_price=80,
        quantity=1.0,
        fee_config=cfg,
    )
    # direct = 200 + 150 + 120 = 470
    assert r.direct_cost == 470.0
    # management = 470 * 0.08 = 37.60
    assert r.management_fee == 37.60
    # profit = 470 * 0.05 = 23.50
    assert r.profit == 23.50
    # regulatory = 470 * 0.03 = 14.10
    assert r.regulatory_fee == 14.10
    # pre_tax = 470 + 37.60 + 23.50 + 14.10 = 545.20
    assert r.pre_tax_total == 545.20
    # tax = 545.20 * 0.09 = 49.068 → 49.07
    assert r.tax == 49.07
    # total = 545.20 + 49.07 = 594.27
    assert r.total == 594.27
    # provenance must exist
    assert "formula" in r.provenance
    assert "fee_config" in r.provenance


def test_calculate_line_item_quantity_multiplier() -> None:
    cfg = FeeConfig(management_rate=0, profit_rate=0, regulatory_rate=0, tax_rate=0)
    r = calculate_line_item(
        labor_qty=1, labor_price=100,
        material_qty=0, material_price=0,
        machine_qty=0, machine_price=0,
        quantity=5.0,
        fee_config=cfg,
    )
    assert r.direct_cost == 500.0
    assert r.total == 500.0


# ---------------------------------------------------------------------------
# Project‑level summary
# ---------------------------------------------------------------------------

def test_calculate_project_summary() -> None:
    cfg = FeeConfig(management_rate=0.10, profit_rate=0.0, regulatory_rate=0.0, tax_rate=0.0)
    inputs = [
        dict(labor_qty=1, labor_price=100, material_qty=0, material_price=0, machine_qty=0, machine_price=0, quantity=1),
        dict(labor_qty=1, labor_price=200, material_qty=0, material_price=0, machine_qty=0, machine_price=0, quantity=1),
    ]
    summary = calculate_project(inputs, fee_config=cfg)
    assert len(summary.line_results) == 2
    assert summary.total_direct == 300.0
    assert summary.total_management == 30.0
    assert summary.grand_total == 330.0
