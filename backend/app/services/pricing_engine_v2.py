"""Dual-track pricing engine (GB50500-2013 / GB/T 50500-2024).

Design principles
-----------------
* Pure functions — no DB access; callers pre-load data and pass it in.
* Same inputs → same outputs (deterministic).
* Provenance dict attached to every result so LLMs / audit logs can explain
  how a number was derived.
* 2024 standard adds dynamic labor-cost index: the *base* labor amount from
  the quota is multiplied by ``labor_index`` before fees are applied.

Five-fee structure (按 GB/T 50500 汇总口径)
-------------------------------------------
  ① 分部分项工程费  (fen_bu)      = Σ BOQ line综合单价 × 工程量
  ② 措施项目费      (cuo_shi)     = 通用措施 + 专业措施
  ③ 其他项目费      (other)       = 暂列金额 + 暂估价 + 计日工 + 总承包服务费
  ④ 规费            (gui_fei)     = rate × 分部分项人工费
  ⑤ 税金            (tax)         = rate × 税前合计 (①+②+③+④)
  Grand total                     = ①+②+③+④+⑤
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _r2(value: float) -> float:
    """Round to 2 decimal places (ROUND_HALF_UP)."""
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class PricingStandardCode(str, Enum):
    GB50500_2013 = "GB50500-2013"
    GBT50500_2024 = "GBT50500-2024"


class TaxMethod(str, Enum):
    GENERAL = "general"    # 一般计税法 9%
    SIMPLE = "simple"      # 简易计税法 3%


# ---------------------------------------------------------------------------
# Input data classes (caller populates, engine reads)
# ---------------------------------------------------------------------------

@dataclass
class BoqLineInput:
    """One BOQ item input to the engine."""
    boq_item_id: int
    code: str
    name: str
    quantity: float
    unit: str
    # Direct cost components (per unit, from quota/综合单价)
    labor_fee: float       # 人工费（基期）per unit
    material_fee: float    # 材料费 per unit
    machine_fee: float     # 机械费 per unit
    # Fees already embedded in综合单价 (per unit)
    management_fee: float = 0.0
    profit_fee: float = 0.0
    # Rate overrides (0 → use FeeStructureConfig defaults)
    management_rate: float = 0.0
    profit_rate: float = 0.0


@dataclass
class MeasureItemInput:
    """One measure item (措施项目)."""
    name: str
    amount: float          # 固定金额 (lump-sum)
    is_rate_based: bool = False
    rate: float = 0.0      # if is_rate_based, rate × 分部分项工程费
    is_competitive: bool = True


@dataclass
class OtherItemInput:
    """One other-fee item (其他项目)."""
    name: str
    category: str          # 暂列金额 | 暂估价 | 计日工 | 总承包服务费
    amount: float


@dataclass
class FeeStructureConfig:
    """Rates loaded from FeeStructure rows for a given PricingStandard."""
    management_rate: float = 0.055   # 企业管理费率 (on direct cost)
    profit_rate: float = 0.05        # 利润率 (on direct cost)
    # 安全文明施工费 (不可竞争)
    anquanwm_rate: float = 0.02
    # 其他措施费率（可竞争）
    other_measure_rate: float = 0.025
    # 规费费率 (on 人工费)
    social_insurance_rate: float = 0.285
    housing_fund_rate: float = 0.08
    # 税率
    tax_rate: float = 0.09           # 一般计税 9%; 简易 3%


DEFAULT_FEE_CONFIG_2013 = FeeStructureConfig()
DEFAULT_FEE_CONFIG_2024 = FeeStructureConfig(
    management_rate=0.055,
    profit_rate=0.05,
    anquanwm_rate=0.02,
    other_measure_rate=0.025,
    social_insurance_rate=0.285,
    housing_fund_rate=0.08,
    tax_rate=0.09,
)


# ---------------------------------------------------------------------------
# Result data classes
# ---------------------------------------------------------------------------

@dataclass
class BoqLineResult:
    boq_item_id: int
    code: str
    name: str
    quantity: float
    unit_labor: float       # 人工费/unit (after dynamic index for 2024)
    unit_material: float
    unit_machine: float
    unit_management: float
    unit_profit: float
    unit_price: float       # 综合单价
    amount: float           # unit_price × quantity
    labor_amount: float     # 人工费合计 (used for 规费 base)
    provenance: dict = field(default_factory=dict)


@dataclass
class MeasureResult:
    name: str
    amount: float
    is_competitive: bool


@dataclass
class FiveFeeResult:
    """Full five-fee breakdown for a project."""
    # ① 分部分项工程费
    fen_bu_total: float
    fen_bu_labor: float        # 人工费合计 (规费基数)
    fen_bu_material: float
    fen_bu_machine: float
    fen_bu_management: float
    fen_bu_profit: float

    # ② 措施项目费
    cuo_shi_total: float
    cuo_shi_anquanwm: float    # 安全文明施工费 (强制)
    cuo_shi_competitive: float # 可竞争措施费

    # ③ 其他项目费
    other_total: float
    other_zljine: float        # 暂列金额
    other_zhjia: float         # 暂估价
    other_jirg: float          # 计日工
    other_zb_svc: float        # 总承包服务费

    # ④ 规费
    gui_fei_total: float
    gui_fei_social_insurance: float
    gui_fei_housing_fund: float

    # ⑤ 税金
    tax_total: float

    # Grand total
    pre_tax_total: float       # ①+②+③+④
    grand_total: float         # ①+②+③+④+⑤

    # Metadata
    standard_code: str = ""
    tax_method: str = TaxMethod.GENERAL.value
    labor_index: float = 1.0
    line_results: list[BoqLineResult] = field(default_factory=list)
    measure_results: list[MeasureResult] = field(default_factory=list)
    provenance: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class PricingEngineV2:
    """Dual-track pricing engine.

    Usage::

        engine = PricingEngineV2(
            standard=PricingStandardCode.GBT50500_2024,
            tax_method=TaxMethod.GENERAL,
            labor_index=1.08,          # 2024 动态指数
            fee_config=DEFAULT_FEE_CONFIG_2024,
        )
        result = engine.calculate(
            boq_lines=[...],
            measure_items=[...],
            other_items=[...],
        )
    """

    def __init__(
        self,
        standard: PricingStandardCode = PricingStandardCode.GB50500_2013,
        tax_method: TaxMethod = TaxMethod.GENERAL,
        labor_index: float = 1.0,
        fee_config: FeeStructureConfig | None = None,
    ) -> None:
        self.standard = standard
        self.tax_method = tax_method
        self.labor_index = labor_index
        self._is_2024 = (standard == PricingStandardCode.GBT50500_2024)
        if fee_config is not None:
            self.fee_config = fee_config
        else:
            self.fee_config = (
                DEFAULT_FEE_CONFIG_2024 if self._is_2024 else DEFAULT_FEE_CONFIG_2013
            )
        # Tax rate resolved from tax_method
        self._tax_rate = 0.03 if tax_method == TaxMethod.SIMPLE else self.fee_config.tax_rate

    # ── Public API ──────────────────────────────────────────────────────────

    def calculate(
        self,
        boq_lines: list[BoqLineInput],
        measure_items: list[MeasureItemInput] | None = None,
        other_items: list[OtherItemInput] | None = None,
    ) -> FiveFeeResult:
        measure_items = measure_items or []
        other_items = other_items or []

        # ① 分部分项工程费
        line_results, fen_bu = self._calc_fen_bu(boq_lines)

        # ② 措施项目费（rate-based ones use fen_bu_total as base）
        measure_results, cuo_shi = self._calc_cuo_shi(measure_items, fen_bu["total"])

        # ③ 其他项目费
        other_breakdown = self._calc_other(other_items)
        other_total = other_breakdown["total"]

        # ④ 规费（base = 人工费合计）
        labor_base = fen_bu["labor"]
        si = _r2(labor_base * self.fee_config.social_insurance_rate)
        hf = _r2(labor_base * self.fee_config.housing_fund_rate)
        gui_fei_total = _r2(si + hf)

        # ⑤ 税金
        pre_tax = _r2(fen_bu["total"] + cuo_shi["total"] + other_total + gui_fei_total)
        tax_total = _r2(pre_tax * self._tax_rate)
        grand_total = _r2(pre_tax + tax_total)

        provenance: dict[str, Any] = {
            "standard": self.standard.value,
            "tax_method": self.tax_method.value,
            "tax_rate": self._tax_rate,
            "labor_index": self.labor_index,
            "is_dynamic_labor": self._is_2024 and self.labor_index != 1.0,
            "formula": "grand_total = fen_bu + cuo_shi + other + gui_fei + tax",
        }

        return FiveFeeResult(
            fen_bu_total=fen_bu["total"],
            fen_bu_labor=fen_bu["labor"],
            fen_bu_material=fen_bu["material"],
            fen_bu_machine=fen_bu["machine"],
            fen_bu_management=fen_bu["management"],
            fen_bu_profit=fen_bu["profit"],
            cuo_shi_total=cuo_shi["total"],
            cuo_shi_anquanwm=cuo_shi["anquanwm"],
            cuo_shi_competitive=cuo_shi["competitive"],
            other_total=other_total,
            other_zljine=other_breakdown["zljine"],
            other_zhjia=other_breakdown["zhjia"],
            other_jirg=other_breakdown["jirg"],
            other_zb_svc=other_breakdown["zb_svc"],
            gui_fei_total=gui_fei_total,
            gui_fei_social_insurance=si,
            gui_fei_housing_fund=hf,
            tax_total=tax_total,
            pre_tax_total=pre_tax,
            grand_total=grand_total,
            standard_code=self.standard.value,
            tax_method=self.tax_method.value,
            labor_index=self.labor_index,
            line_results=line_results,
            measure_results=measure_results,
            provenance=provenance,
        )

    # ── Private helpers ──────────────────────────────────────────────────────

    def _effective_labor(self, base_labor: float) -> float:
        """Apply dynamic labor index for 2024 standard."""
        if self._is_2024 and self.labor_index != 1.0:
            return _r2(base_labor * self.labor_index)
        return base_labor

    def _calc_fen_bu(self, lines: list[BoqLineInput]) -> tuple[list[BoqLineResult], dict]:
        results: list[BoqLineResult] = []
        total = labor = material = machine = management = profit = 0.0

        cfg = self.fee_config
        for ln in lines:
            qty = ln.quantity
            # Per-unit labor (with 2024 dynamic adjustment)
            u_labor = _r2(self._effective_labor(ln.labor_fee))
            u_mat = _r2(ln.material_fee)
            u_mach = _r2(ln.machine_fee)
            direct_u = _r2(u_labor + u_mat + u_mach)

            # Management / profit: use line-level override if non-zero, else config rate
            mgmt_rate = ln.management_rate if ln.management_rate else cfg.management_rate
            prof_rate = ln.profit_rate if ln.profit_rate else cfg.profit_rate

            if ln.management_fee:
                u_mgmt = _r2(ln.management_fee)
            else:
                u_mgmt = _r2(direct_u * mgmt_rate)

            if ln.profit_fee:
                u_prof = _r2(ln.profit_fee)
            else:
                u_prof = _r2(direct_u * prof_rate)

            unit_price = _r2(direct_u + u_mgmt + u_prof)
            amount = _r2(unit_price * qty)
            labor_amount = _r2(u_labor * qty)

            provenance: dict[str, Any] = {
                "labor_index": self.labor_index if self._is_2024 else 1.0,
                "unit_price_formula": "direct(labor+mat+mach) + management + profit",
                "management_rate": mgmt_rate,
                "profit_rate": prof_rate,
            }
            if self._is_2024 and ln.labor_fee > 0 and self.labor_index != 1.0:
                provenance["labor_base"] = ln.labor_fee
                provenance["labor_dynamic"] = u_labor
                provenance["labor_delta"] = _r2(u_labor - ln.labor_fee)

            results.append(BoqLineResult(
                boq_item_id=ln.boq_item_id,
                code=ln.code,
                name=ln.name,
                quantity=qty,
                unit_labor=u_labor,
                unit_material=u_mat,
                unit_machine=u_mach,
                unit_management=u_mgmt,
                unit_profit=u_prof,
                unit_price=unit_price,
                amount=amount,
                labor_amount=labor_amount,
                provenance=provenance,
            ))

            total += amount
            labor += labor_amount
            material += _r2(u_mat * qty)
            machine += _r2(u_mach * qty)
            management += _r2(u_mgmt * qty)
            profit += _r2(u_prof * qty)

        agg = {
            "total": _r2(total),
            "labor": _r2(labor),
            "material": _r2(material),
            "machine": _r2(machine),
            "management": _r2(management),
            "profit": _r2(profit),
        }
        return results, agg

    def _calc_cuo_shi(
        self, items: list[MeasureItemInput], fen_bu_total: float
    ) -> tuple[list[MeasureResult], dict]:
        results: list[MeasureResult] = []
        anquanwm = _r2(fen_bu_total * self.fee_config.anquanwm_rate)
        results.append(MeasureResult(
            name="安全文明施工费（计算）",
            amount=anquanwm,
            is_competitive=False,
        ))

        competitive_sum = 0.0
        for it in items:
            if it.is_rate_based:
                amt = _r2(fen_bu_total * it.rate)
            else:
                amt = _r2(it.amount)
            results.append(MeasureResult(name=it.name, amount=amt,
                                          is_competitive=it.is_competitive))
            if it.is_competitive:
                competitive_sum += amt
            else:
                anquanwm += amt  # other mandatory measures lumped in

        # If no measure items given, apply default other-measure rate
        if not items:
            default_other = _r2(fen_bu_total * self.fee_config.other_measure_rate)
            results.append(MeasureResult(
                name="其他措施费（默认费率）",
                amount=default_other,
                is_competitive=True,
            ))
            competitive_sum = default_other

        total = _r2(anquanwm + competitive_sum)
        return results, {
            "total": total,
            "anquanwm": anquanwm,
            "competitive": _r2(competitive_sum),
        }

    @staticmethod
    def _calc_other(items: list[OtherItemInput]) -> dict:
        zljine = zhjia = jirg = zb_svc = 0.0
        for it in items:
            cat = it.category
            if cat in ("暂列金额", "provisional_sum"):
                zljine += it.amount
            elif cat in ("暂估价", "专业工程暂估价", "provisional_price"):
                zhjia += it.amount
            elif cat in ("计日工", "daywork"):
                jirg += it.amount
            elif cat in ("总承包服务费", "总承包", "gc_service"):
                zb_svc += it.amount
        return {
            "total": _r2(zljine + zhjia + jirg + zb_svc),
            "zljine": _r2(zljine),
            "zhjia": _r2(zhjia),
            "jirg": _r2(jirg),
            "zb_svc": _r2(zb_svc),
        }


# ---------------------------------------------------------------------------
# Convenience factory
# ---------------------------------------------------------------------------

def make_engine_from_project(project_row: Any, fee_config: FeeStructureConfig | None = None) -> PricingEngineV2:
    """Create engine from a Project ORM row (or dict-like object).

    Looks for:
        project_row.pricing_standard_id  → resolves standard code externally
        project_row.standard_code        → str like 'GB50500-2013'
        project_row.tax_method           → 'general' | 'simple'
        project_row.labor_index_period   → str (caller resolves to float)
    """
    std_code_str = getattr(project_row, "standard_code", None) or "GB50500-2013"
    try:
        std = PricingStandardCode(std_code_str)
    except ValueError:
        std = PricingStandardCode.GB50500_2013

    tax_str = getattr(project_row, "tax_method", "general") or "general"
    try:
        tax = TaxMethod(tax_str)
    except ValueError:
        tax = TaxMethod.GENERAL

    labor_index = float(getattr(project_row, "labor_index", 1.0) or 1.0)

    return PricingEngineV2(
        standard=std,
        tax_method=tax,
        labor_index=labor_index,
        fee_config=fee_config,
    )
