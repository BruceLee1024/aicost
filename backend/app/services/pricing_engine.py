"""Deterministic pricing engine.

All calculations are pure functions: same inputs → same outputs.
Every result carries a provenance dict explaining its derivation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from decimal import ROUND_HALF_UP, Decimal


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _r2(value: float) -> float:
    """Round to 2 decimal places using ROUND_HALF_UP (banker‑safe)."""
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


# ---------------------------------------------------------------------------
# Fee config (rule‑package params – will be loaded from DB / JSON later)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FeeConfig:
    """Configurable fee rates – mirrors a "rule package" row."""
    management_rate: float = 0.0   # 管理费率 (on direct cost)
    profit_rate: float = 0.0       # 利润率 (on direct cost)
    regulatory_rate: float = 0.0   # 规费费率 (on direct cost)
    tax_rate: float = 0.09         # 增值税率 (on pre‑tax total)


DEFAULT_FEE_CONFIG = FeeConfig(
    management_rate=0.08,
    profit_rate=0.05,
    regulatory_rate=0.03,
    tax_rate=0.09,
)


# ---------------------------------------------------------------------------
# Result data classes
# ---------------------------------------------------------------------------

@dataclass
class LineItemResult:
    labor_cost: float
    material_cost: float
    machine_cost: float
    direct_cost: float       # 人 + 材 + 机
    management_fee: float
    profit: float
    regulatory_fee: float
    pre_tax_total: float
    tax: float
    total: float
    provenance: dict = field(default_factory=dict)


@dataclass
class ProjectSummary:
    line_results: list[LineItemResult]
    total_direct: float
    total_management: float
    total_profit: float
    total_regulatory: float
    total_pre_tax: float
    total_tax: float
    total_measures: float = 0.0
    grand_total: float = 0.0


# ---------------------------------------------------------------------------
# Core calculation
# ---------------------------------------------------------------------------

def calculate_line_item_total(
    *,
    labor_qty: float,
    labor_price: float,
    material_qty: float,
    material_price: float,
    machine_qty: float,
    machine_price: float,
) -> float:
    """Legacy simple helper – returns direct cost only."""
    labor_cost = labor_qty * labor_price
    material_cost = material_qty * material_price
    machine_cost = machine_qty * machine_price
    return _r2(labor_cost + material_cost + machine_cost)


def calculate_line_item(
    *,
    labor_qty: float,
    labor_price: float,
    material_qty: float,
    material_price: float,
    machine_qty: float,
    machine_price: float,
    quantity: float = 1.0,
    fee_config: FeeConfig = DEFAULT_FEE_CONFIG,
) -> LineItemResult:
    """Full line‑item calculation with fees and tax."""
    labor_cost = _r2(labor_qty * labor_price * quantity)
    material_cost = _r2(material_qty * material_price * quantity)
    machine_cost = _r2(machine_qty * machine_price * quantity)
    direct_cost = _r2(labor_cost + material_cost + machine_cost)

    management_fee = _r2(direct_cost * fee_config.management_rate)
    profit = _r2(direct_cost * fee_config.profit_rate)
    regulatory_fee = _r2(direct_cost * fee_config.regulatory_rate)

    pre_tax_total = _r2(direct_cost + management_fee + profit + regulatory_fee)
    tax = _r2(pre_tax_total * fee_config.tax_rate)
    total = _r2(pre_tax_total + tax)

    provenance = {
        "formula": "(labor+material+machine)*qty → direct; +mgmt+profit+reg → pretax; +tax → total",
        "fee_config": asdict(fee_config),
        "inputs": {
            "labor_qty": labor_qty, "labor_price": labor_price,
            "material_qty": material_qty, "material_price": material_price,
            "machine_qty": machine_qty, "machine_price": machine_price,
            "quantity": quantity,
        },
    }

    return LineItemResult(
        labor_cost=labor_cost,
        material_cost=material_cost,
        machine_cost=machine_cost,
        direct_cost=direct_cost,
        management_fee=management_fee,
        profit=profit,
        regulatory_fee=regulatory_fee,
        pre_tax_total=pre_tax_total,
        tax=tax,
        total=total,
        provenance=provenance,
    )


# ---------------------------------------------------------------------------
# Resource-detail (精细) calculation mode
# ---------------------------------------------------------------------------

@dataclass
class ResourceLine:
    """One resource consumed within a quota binding."""
    category: str          # "人工" | "材料" | "机械"
    resource_name: str
    spec: str
    unit: str
    quantity: float        # consumption per unit of quota
    unit_price: float      # resolved market price (or quota base price fallback)
    cost: float = 0.0      # quantity * unit_price (filled by engine)
    price_source: str = ""  # "信息价" | "定额基价" | "合同价"


@dataclass
class DetailedLineItemResult:
    """Calculation result with full resource-level breakdown."""
    resource_lines: list[ResourceLine]
    labor_cost: float
    material_cost: float
    machine_cost: float
    direct_cost: float
    management_fee: float
    profit: float
    regulatory_fee: float
    pre_tax_total: float
    tax: float
    total: float
    provenance: dict = field(default_factory=dict)


def calculate_line_item_detailed(
    *,
    resource_lines: list[ResourceLine],
    quantity: float = 1.0,
    coefficient: float = 1.0,
    fee_config: FeeConfig = DEFAULT_FEE_CONFIG,
) -> DetailedLineItemResult:
    """Resource-detail pricing: sum individual resource costs instead of
    aggregate labor/material/machine totals.

    Each resource line's cost = resource.quantity * coefficient * unit_price * boq_quantity.
    """
    labor_cost = 0.0
    material_cost = 0.0
    machine_cost = 0.0

    for rl in resource_lines:
        rl.cost = _r2(rl.quantity * coefficient * rl.unit_price * quantity)
        if rl.category == "人工":
            labor_cost += rl.cost
        elif rl.category == "材料":
            material_cost += rl.cost
        else:
            machine_cost += rl.cost

    labor_cost = _r2(labor_cost)
    material_cost = _r2(material_cost)
    machine_cost = _r2(machine_cost)
    direct_cost = _r2(labor_cost + material_cost + machine_cost)

    management_fee = _r2(direct_cost * fee_config.management_rate)
    profit = _r2(direct_cost * fee_config.profit_rate)
    regulatory_fee = _r2(direct_cost * fee_config.regulatory_rate)

    pre_tax_total = _r2(direct_cost + management_fee + profit + regulatory_fee)
    tax = _r2(pre_tax_total * fee_config.tax_rate)
    total = _r2(pre_tax_total + tax)

    provenance = {
        "mode": "resource_detail",
        "formula": "Σ(resource.qty × coeff × price × boq_qty) per category → direct; +fees → total",
        "fee_config": asdict(fee_config),
        "resource_count": len(resource_lines),
        "coefficient": coefficient,
        "quantity": quantity,
    }

    return DetailedLineItemResult(
        resource_lines=resource_lines,
        labor_cost=labor_cost,
        material_cost=material_cost,
        machine_cost=machine_cost,
        direct_cost=direct_cost,
        management_fee=management_fee,
        profit=profit,
        regulatory_fee=regulatory_fee,
        pre_tax_total=pre_tax_total,
        tax=tax,
        total=total,
        provenance=provenance,
    )


# ---------------------------------------------------------------------------
# Project-level aggregation
# ---------------------------------------------------------------------------

def calculate_project(line_inputs: list[dict], fee_config: FeeConfig = DEFAULT_FEE_CONFIG) -> ProjectSummary:
    """Run full calculation for a list of line items and produce a summary."""
    results: list[LineItemResult] = []
    for inp in line_inputs:
        r = calculate_line_item(**inp, fee_config=fee_config)
        results.append(r)

    return ProjectSummary(
        line_results=results,
        total_direct=_r2(sum(r.direct_cost for r in results)),
        total_management=_r2(sum(r.management_fee for r in results)),
        total_profit=_r2(sum(r.profit for r in results)),
        total_regulatory=_r2(sum(r.regulatory_fee for r in results)),
        total_pre_tax=_r2(sum(r.pre_tax_total for r in results)),
        total_tax=_r2(sum(r.tax for r in results)),
        grand_total=_r2(sum(r.total for r in results)),
    )
