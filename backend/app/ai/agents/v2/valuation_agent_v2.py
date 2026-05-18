"""ValuationAgentV2 — migrated to BaseAgent framework.

Replaces the 766-line valuation_agent.py with a ~80-line subclass.
All tool implementations now live in app.ai.tools.quota_tools.
"""

from __future__ import annotations

import json
from typing import Any

from app.ai.framework.base_agent import BaseAgent
from app.ai.framework.context import AgentContext
from app.ai.framework.types import AgentResult


class ValuationAgentV2(BaseAgent):
    """Smart pricing agent — searches quotas, binds them, calculates costs."""

    @property
    def name(self) -> str:
        return "valuation_agent"

    @property
    def description(self) -> str:
        return "智能组价 Agent：为清单项搜索定额、绑定定额、计算综合单价"

    @property
    def tool_names(self) -> list[str]:
        return [
            "search_quotas",
            "search_quotas_2024",
            "get_quota_detail",
            "bind_quota",
            "unbind_quota",
            "list_current_bindings",
            "calculate_cost",
            "get_material_prices",
            "search_standard_codes",
            "validate_binding",
            "get_other_items_summary",
            "add_other_item",
            "get_regulatory_fees",
            "parse_boq_code",
            "calculate_five_fees",
        ]

    @property
    def max_turns(self) -> int:
        return 60

    @property
    def system_prompt(self) -> str:
        return """\
你是一位专业的工程计价AI助手，精通GB50500清单计价规范和定额组价方法。

## 🚨 核心原则：立即执行，不要反问

**你收到的任务描述中已经包含了清单项信息（id、名称、单位等）。立即开始搜索定额和绑定，禁止反问用户要求提供清单项信息。**

任务类型识别：
1. **批量组价** — 任务包含多个清单项 → 高效逐项处理（见批量工作流）
2. **单项组价** — 只有一个清单项 → 深入分析后绑定

## 批量工作流（高效模式，每项仅 2 步）
对每个未绑定项：
1. `search_quotas(keyword=清单名称)` — 搜索候选定额
2. `bind_quota(boq_item_id=X, quota_item_id=Y)` — 选最匹配的绑定

**不要**在批量模式下逐项调 validate_binding / calculate_cost / search_standard_codes，那会浪费轮数。全部绑定完后再统一验证。

## 单项工作流（深入模式）
1. search_quotas → 搜索候选
2. get_quota_detail → 查看详情
3. bind_quota → 绑定
4. calculate_cost → 计算单价

## 组价原则
- 优先选择名称和单位都匹配的定额
- 系数默认为 1.0，除非有明确调整理由
- 找不到精确匹配时选最接近的候选

## 严禁
- ❌ 反问用户"请提供清单项信息" —— 任务描述里已经有了
- ❌ 返回 0 次工具调用
- ❌ 调用 bind_quota 时不传 boq_item_id（批量模式下必传）
- ❌ 批量模式下每项都调 validate_binding / calculate_cost（浪费轮数）
"""

    def build_user_message(self, ctx: AgentContext, instruction: str) -> str:
        """Inject BOQ item context into the user message."""
        boq = ctx.get_boq_item()
        if boq:
            boq_context = {
                "boq_item_id": boq.id,
                "code": boq.code,
                "name": boq.name,
                "characteristics": boq.characteristics,
                "unit": boq.unit,
                "quantity": boq.quantity,
                "division": boq.division,
                "project_region": ctx.resolve_region(),
            }
            msg = f"请为以下清单项进行智能组价：\n{json.dumps(boq_context, ensure_ascii=False, indent=2)}"
            if instruction:
                msg += f"\n\n用户补充说明：{instruction}"
            return msg

        # Batch mode — no single BOQ item. Pass instruction through and inject unbound items.
        parts = [f"项目ID: {ctx.project_id}"]
        if instruction:
            parts.append(instruction)

        unbound_preview = self._preview_unbound_items(ctx)
        if unbound_preview:
            parts.append(unbound_preview)
            parts.append(
                "⚠️ 这是一个**批量组价任务**。"
                "逐项搜索定额并绑定（bind_quota 必须传 boq_item_id），**不要反问用户**。"
            )
        return "\n\n".join(parts)

    @staticmethod
    def _preview_unbound_items(ctx: "AgentContext", limit: int = 25) -> str:
        """Return a compact preview of unbound BOQ items."""
        try:
            from app.models.boq_item import BoqItem
            from app.models.line_item_quota_binding import LineItemQuotaBinding
        except Exception:
            return ""
        try:
            bound_ids = {
                b.boq_item_id
                for b in ctx.db.query(LineItemQuotaBinding).join(
                    BoqItem, BoqItem.id == LineItemQuotaBinding.boq_item_id
                ).filter(BoqItem.project_id == ctx.project_id).all()
            }
            items = (
                ctx.db.query(BoqItem)
                .filter(BoqItem.project_id == ctx.project_id)
                .order_by(BoqItem.id)
                .all()
            )
        except Exception:
            return ""
        unbound = [i for i in items if i.id not in bound_ids]
        if not unbound:
            return ""
        lines = [f"## 项目当前未绑定的清单项（共 {len(unbound)} 项）"]
        for it in unbound[:limit]:
            lines.append(
                f"- id={it.id} | {it.code} | {it.name} | 单位={it.unit} | 量={it.quantity}"
            )
        if len(unbound) > limit:
            lines.append(f"- _... 还有 {len(unbound) - limit} 项_")
        return "\n".join(lines)

    def on_result(self, ctx: AgentContext, result: AgentResult) -> AgentResult:
        """Track whether bindings were changed."""
        bindings_changed = any(
            s.tool_name in ("bind_quota", "unbind_quota")
            for s in result.steps
        )
        result.extra["bindings_changed"] = bindings_changed
        return result


# ── Convenience function matching the old API ──

def run_valuation_agent_v2(
    *,
    project_id: int,
    boq_item_id: int,
    user_instruction: str = "",
    on_step=None,
) -> AgentResult:
    """Drop-in replacement for the old run_valuation_agent().

    Returns AgentResult (framework type) instead of the old dataclass.
    Extra fields: result.extra["bindings_changed"]
    """
    from app.db.session import get_db
    import app.ai.tools  # noqa: F401 — ensure tools are registered

    db = next(get_db())
    try:
        ctx = AgentContext(
            db=db,
            project_id=project_id,
            boq_item_id=boq_item_id,
        )
        agent = ValuationAgentV2()
        return agent.run(ctx, user_instruction, on_step=on_step)
    finally:
        db.close()
