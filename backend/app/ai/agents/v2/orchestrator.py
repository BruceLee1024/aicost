"""Orchestrator — Supervisor Agent that routes tasks to sub-agents.

The Orchestrator is itself a BaseAgent whose tools are other agents
(via agent_as_tool). It decides which sub-agent(s) to invoke based on
the user's request, coordinates their execution, and synthesizes results.

This implements the Claude Code "Agent-as-Tool" pattern at the top level.

## Phase H6: Memory + Skills integration

The Orchestrator now automatically:
- Injects relevant cross-session memories into every run (via ``use_memory_context``).
- Pre-fetches the top-K semantically matching Skills for the user's instruction
  and prepends them to the user message.
- Exposes memory + skill management tools so it can save/retrieve on the fly.
"""

from __future__ import annotations

import logging

from app.ai.framework.agent_as_tool import agent_to_tool
from app.ai.framework.base_agent import BaseAgent
from app.ai.framework.context import AgentContext
from app.ai.framework.tool_registry import ToolRegistry
from app.ai.framework.types import AgentResult

logger = logging.getLogger(__name__)


class OrchestratorAgent(BaseAgent):
    """Top-level supervisor that delegates to specialized sub-agents.

    Unlike other agents that use the global tool registry, the Orchestrator
    builds its own registry containing agent-tools + a few utility tools.
    """

    def __init__(self) -> None:
        super().__init__()
        self._agent_registry = ToolRegistry()
        self._setup_agent_tools()

    def _setup_agent_tools(self) -> None:
        """Register all sub-agents as tools + utility tools."""
        from app.ai.agents.v2.valuation_agent_v2 import ValuationAgentV2
        from app.ai.agents.v2.validation_agent_v2 import ValidationAgentV2
        from app.ai.agents.v2.chat_agent_v2 import ChatAgentV2
        from app.ai.agents.v2.boq_agent_v2 import BoqAgentV2
        from app.ai.agents.v2.query_agent_v2 import QueryAgentV2
        from app.ai.agents.v2.insight_agent_v2 import InsightAgentV2
        from app.ai.agents.v2.quota_match_agent_v2 import QuotaMatchAgentV2
        from app.ai.agents.v2.batch_review_agent_v2 import BatchReviewAgentV2
        from app.ai.agents.v2.rate_suggestion_agent_v2 import RateSuggestionAgentV2
        # Phase G: Specialized cost agents
        from app.ai.agents.v2.cost_explore_agent import CostExploreAgent
        from app.ai.agents.v2.cost_plan_agent import CostPlanAgent
        from app.ai.agents.v2.cost_validation_agent import CostValidationAgent
        from app.ai.agents.v2.cost_execute_agent import CostExecuteAgent
        # Phase I: Project setup & pipeline
        from app.ai.agents.v2.project_setup_agent import ProjectSetupAgent
        from app.ai.agents.v2.full_pipeline_agent import FullPipelineAgent
        # Phase J: Business-specific agents
        from app.ai.agents.v2.measures_agent import MeasuresAgent
        from app.ai.agents.v2.lmm_agent import LMMAggregationAgent

        # Wrap each agent as a tool
        agent_tools = [
            agent_to_tool(ValuationAgentV2(), name_override="delegate_valuation",
                          description_override="委派给「智能组价Agent」：为清单项搜索定额、绑定定额、计算综合单价。需要提供具体的清单项信息。"),
            agent_to_tool(ValidationAgentV2(), name_override="delegate_validation",
                          description_override="委派给「数据审核Agent」：检查编码合规、消耗量异常、历史对比。可审核单个清单项或整个项目。"),
            agent_to_tool(QueryAgentV2(), name_override="delegate_query",
                          description_override="委派给「查询Agent」：搜索清单项、查看绑定、获取统计数据等数据查询类任务。"),
            agent_to_tool(InsightAgentV2(), name_override="delegate_insight",
                          description_override="委派给「分析洞察Agent」：费用结构分析、异常检测、改进建议等分析类任务。"),
            agent_to_tool(QuotaMatchAgentV2(), name_override="delegate_quota_match",
                          description_override="委派给「定额匹配Agent」：为清单项搜索和推荐最佳候选定额。"),
            agent_to_tool(BatchReviewAgentV2(), name_override="delegate_batch_review",
                          description_override="委派给「批量审查Agent」：扫描整个项目的绑定问题，生成审查报告。"),
            agent_to_tool(BoqAgentV2(), name_override="delegate_boq_generate",
                          description_override="委派给「清单生成Agent」：根据工程描述生成工程量清单项建议。"),
            agent_to_tool(RateSuggestionAgentV2(), name_override="delegate_rate_suggestion",
                          description_override="委派给「费率建议Agent」：为HKSMM4清单项建议合理的单价范围。"),
            agent_to_tool(ChatAgentV2(), name_override="delegate_chat",
                          description_override="委派给「问答Agent」：回答关于项目数据的一般性问题。"),
            # Phase G: Specialized cost agents
            agent_to_tool(CostExploreAgent(), name_override="delegate_explore",
                          description_override="委派给「造价探索Agent」：只读快速搜索定额库、清单、材料价格。适合纯查询类任务，速度最快。"),
            agent_to_tool(CostPlanAgent(), name_override="delegate_plan",
                          description_override="委派给「组价方案Agent」：分析清单项并设计组价策略方案，不执行绑定。适合需要规划的复杂组价场景。"),
            agent_to_tool(CostValidationAgent(), name_override="delegate_adversarial_review",
                          description_override="委派给「对抗性审核Agent」：以找出问题为目标审核绑定合理性、单价异常。比普通审核更严格。"),
            agent_to_tool(CostExecuteAgent(), name_override="delegate_execute",
                          description_override="委派给「组价执行Agent」：执行定额绑定、单价计算等写操作，并自动验证结果。"),
            # Phase I: Project setup
            agent_to_tool(ProjectSetupAgent(), name_override="delegate_project_setup",
                          description_override="委派给「智能开项Agent」：根据工程描述或图纸自动创建项目并生成完整工程量清单。适合新建项目、智能开项场景。"),
            agent_to_tool(FullPipelineAgent(), name_override="delegate_full_pipeline",
                          description_override="委派给「全流程Agent」：一键完成从新建项目到生成计价报告的全自动流水线（开项→BOQ→组价→计算→报告）。适合“一键全流程”场景。"),
            # Phase J: Business-specific agents
            agent_to_tool(MeasuresAgent(), name_override="delegate_measures",
                          description_override="委派给「措施项目Agent」：配置/调整/查询措施项目（安全文明施工、脚手架、垂直运输、夜间施工、二次搬运等）。能一键返回 GB50500 标准套餐并批量写入。"),
            agent_to_tool(LMMAggregationAgent(), name_override="delegate_lmm",
                          description_override="委派给「人材机汇总Agent」：聚合项目人工/材料/机械资源消耗，按金额排序资源 Top-N、识别未挂信息价主材，生成人材机报告。"),
        ]

        for t in agent_tools:
            self._agent_registry.register(t)

        # Also include a few direct utility tools from the global registry
        # Ensure all tool modules are imported (memory_tools / skill_tools auto-register on import).
        import app.ai.tools  # noqa: F401
        from app.ai.framework.tool_registry import registry as global_registry

        utility_tools = [
            # Project overview
            "get_project_stats", "get_divisions_summary", "list_unbound_items",
            # Project lifecycle
            "batch_calculate_project", "recalculate_dirty",
            "update_boq_item", "delete_boq_items",
            # Batch binding
            "batch_bind_quotas", "auto_match_and_bind", "batch_auto_match_all",
            # Reports
            "get_project_summary_report", "generate_valuation_report",
            # Phase H6: Memory management
            "save_memory", "search_memory", "search_memory_semantic",
            "list_memories", "forget_memory",
            # Phase H6: Skill discovery & loading
            "list_skills", "match_skills", "match_skills_semantic", "load_skill",
        ]
        for tool_name in utility_tools:
            tool = global_registry.get(tool_name)
            if tool:
                self._agent_registry.register(tool)
            else:  # pragma: no cover — defensive
                logger.warning("Orchestrator: utility tool not found: %s", tool_name)

    @property
    def name(self) -> str:
        return "orchestrator"

    @property
    def description(self) -> str:
        return "总调度 Agent：理解用户意图，将复杂任务分解并委派给专业子Agent执行"

    @property
    def tool_names(self) -> list[str]:
        return self._agent_registry.all_names

    @property
    def max_turns(self) -> int:
        return 30  # Orchestrator may need multiple delegation rounds

    # ── Phase H6: Memory + Skills integration ──

    @property
    def use_memory_context(self) -> bool:
        """Orchestrator auto-injects cross-session memories every run. (H6)"""
        return True

    @property
    def memory_context_limit(self) -> int:
        """Memories per scope (global / user / project) surfaced in context."""
        return 5

    #: Top-K skills to pre-fetch via semantic match and surface as hints.
    skill_prefetch_limit: int = 3
    #: Minimum cosine similarity for a skill to be hinted (hash embedder is noisy).
    skill_prefetch_min_similarity: float = 0.25

    # ── Phase H7: Auto-sediment memories after successful runs ──

    #: Opt-in flag. When True, on_result asks the memory_extractor for
    #: candidate memories and persists them into ctx.memory. Default off.
    auto_save_memory: bool = False

    #: Extractor used when auto_save_memory is True. Pluggable — tests
    #: inject a stub; production wires in LLMMemoryExtractor().
    memory_extractor: "MemoryExtractor | None" = None

    def __post_init_memory_extractor(self) -> None:  # called lazily
        """Lazily install a default NoopMemoryExtractor so attribute is never None."""
        if self.memory_extractor is None:
            from app.ai.framework.memory_extractor import NoopMemoryExtractor
            self.memory_extractor = NoopMemoryExtractor()

    def build_user_message(self, ctx: AgentContext, instruction: str) -> str:
        """Build user message with memory + skill hints injected. (H6)

        Layout (top to bottom):
        1. Cross-session memory block (from BaseAgent.build_memory_context)
        2. Skill hints — top-K skill titles matching the instruction
        3. The original instruction

        Skill *bodies* are NOT injected here to keep the orchestrator's
        context lean; if it wants the full body it should call ``load_skill``.
        """
        parts: list[str] = []

        memory_block = self.build_memory_context(ctx)
        if memory_block:
            parts.append(memory_block)

        skill_hints = self._build_skill_hints(instruction)
        if skill_hints:
            parts.append(skill_hints)

        parts.append(f"## 任务\n{instruction}")

        execution_directive = self._execution_directive(instruction)
        if execution_directive:
            parts.append(execution_directive)

        return "\n\n".join(parts)

    # ── Phase H10: Hard routing for execution-class intents ──

    _EXECUTION_KEYWORDS: tuple[str, ...] = (
        "智能组价", "自动组价", "帮我组价", "执行组价", "开始组价",
        "组价", "绑定定额", "处理未绑定", "把未绑定",
        "auto-valuate", "auto valuate",
    )

    _PROJECT_SETUP_KEYWORDS: tuple[str, ...] = (
        "新建项目", "智能开项", "创建项目", "创建工程", "生成清单",
        "生成BOQ", "帮我开项", "建一个项目",
    )

    _FULL_PIPELINE_KEYWORDS: tuple[str, ...] = (
        "一键全流程", "全流程", "从开项到组价", "从头到尾",
        "自动完成全部", "一键完成", "full pipeline",
    )

    def _execution_directive(self, instruction: str) -> str:
        """If the instruction matches execution keywords, append a hard directive
        that forces the first tool call to be ``delegate_execute``.

        This is the server-side guardrail that stops the model from spiraling
        through read-only tools (match_skills_semantic / load_skill / save_memory)
        when the user clearly wants execution.
        """
        text = instruction.strip()
        if not text:
            return ""

        # Full pipeline routing (check before project setup — it's a superset)
        if any(kw in text for kw in self._FULL_PIPELINE_KEYWORDS):
            return (
                "## 🚨 系统识别：全流程请求\n"
                "本任务已被系统识别为「全流程自动化请求」。请严格按以下顺序行动：\n"
                "1. **你的下一个工具调用必须是 `delegate_full_pipeline`**。`task` 参数传入用户的完整描述。\n"
                "2. `delegate_full_pipeline` 会依次完成：开项→BOQ生成→定额绑定→计算→审查→报告。\n"
                "3. 等待它返回后，综合结果回复用户。\n"
            )

        # Project setup routing
        if any(kw in text for kw in self._PROJECT_SETUP_KEYWORDS):
            return (
                "## 🚨 系统识别：智能开项请求\n"
                "本任务已被系统识别为「智能开项请求」。请严格按以下顺序行动：\n"
                "1. **你的下一个工具调用必须是 `delegate_project_setup`**。`task` 参数传入用户的工程描述。\n"
                "2. `delegate_project_setup` 会自动创建项目并生成完整 BOQ 清单。\n"
                "3. 如果用户还要求自动组价，在 `delegate_project_setup` 完成后，"
                "再调用 `delegate_execute` 进行批量组价，最后调用 `batch_calculate_project` 计算汇总。\n"
                "4. 综合结果回复用户。\n"
            )

        # Execution routing
        if not any(kw in text for kw in self._EXECUTION_KEYWORDS):
            return ""
        return (
            "## 🚨 系统识别：执行类请求\n"
            "本任务已被系统识别为「执行类请求」。请严格按以下顺序行动：\n"
            "1. **你的下一个工具调用必须是 `delegate_execute`**。`task` 参数传入用户原话"
            "（加上需要的上下文，例如 \"为项目内所有未绑定清单项搜索并绑定最合适的定额、计算综合单价\"）。\n"
            "2. `delegate_execute` 已在工具列表中可用。如果你以为它不存在，是你看错了——请直接调用它。\n"
            "3. 在 `delegate_execute` 返回之前，禁止调用 `match_skills_semantic` / `load_skill` / `save_memory` "
            "/ 再次调用 `list_unbound_items` 或 `get_project_stats`。\n"
            "4. `delegate_execute` 返回后，再综合结果回复用户。\n"
        )

    def _build_skill_hints(self, instruction: str) -> str:
        """Semantic-match skills against the instruction, return a hint block.

        Returns empty string if no skills match or the registry is empty.
        """
        if not instruction:
            return ""

        try:
            from app.ai.framework.skill_registry import skill_registry
        except Exception:  # pragma: no cover — defensive
            return ""

        try:
            scored = skill_registry.match_semantic(
                query=instruction,
                limit=self.skill_prefetch_limit,
                min_similarity=self.skill_prefetch_min_similarity,
            )
        except Exception as e:  # pragma: no cover — defensive
            logger.warning("skill prefetch failed: %s", e)
            return ""

        if not scored:
            return ""

        lines = ["## 可能相关的领域知识（Skills）",
                 "_以下 Skill 可能与本任务相关，需要详细内容时调用 `load_skill(name=...)`。_"]
        for score, s in scored:
            lines.append(f"- **{s.name}** ({score:.2f}) — {s.title}: {s.description}")
        return "\n".join(lines)

    @property
    def system_prompt(self) -> str:
        return """\
你是工程计价系统的总调度 AI。理解用户意图 → 委派给子 Agent → 综合结果回复。

## 🚨 执行类请求：直接委派，不要自己计划

当用户说"组价 / 绑定定额 / 开项 / 生成清单 / 全流程"等**动作动词**时，立刻调对应 delegate_*，**禁止**自己写计划文档。

| 用户意图 | 必须调用 |
|---|---|
| 智能组价 / 自动组价 / 处理未绑定 / 绑定定额 | `delegate_execute`（批量）或 `delegate_valuation`（单项） |
| 新建项目 / 智能开项 / 生成清单 | `delegate_project_setup` |
| 一键全流程 / 从开项到报告 | `delegate_full_pipeline` |
| 严格审核 / 挑错 | `delegate_adversarial_review` |
| 扫描 / 批量审查 | `delegate_batch_review` |
| 纯查询 / 查一下 | `delegate_explore` |

**严禁反模式**：
- ❌ 用 Markdown 输出"第一阶段处理 X，第二阶段处理 Y..."而没真的调 delegate_execute
- ❌ 反问"您希望从哪开始"——用户已说"全部"
- ❌ 执行前反复 `save_memory` / `load_skill` / `match_skills_semantic`（三者合计最多 1 次）；`save_memory` 必须带 `scope+key+content`，禁止空参
- ❌ 同一次对话重复调同一个只读工具（系统会返回缓存并提示）

## 子 Agent 一览

专用（优先）：`delegate_explore`(只读搜索) / `delegate_plan`(规划方案) / `delegate_adversarial_review`(严格审核) / `delegate_execute`(写操作+自动验证)

通用：`delegate_valuation`(单项组价) / `delegate_validation`(合规检查) / `delegate_query`(数据查询) / `delegate_insight`(洞察分析) / `delegate_quota_match`(定额匹配) / `delegate_batch_review`(全项目扫描) / `delegate_boq_generate`(BOQ建议) / `delegate_rate_suggestion`(费率建议) / `delegate_chat`(问答) / `delegate_project_setup`(智能开项) / `delegate_full_pipeline`(全流程)

## 直接可用工具
- **概况**：`get_project_stats` / `get_divisions_summary` / `list_unbound_items` / `batch_calculate_project`
- **记忆**：`save_memory` / `search_memory_semantic` / `list_memories` / `forget_memory`（scope=global|user|project）
- **Skills**：`match_skills_semantic` / `load_skill`（仅在系统注入的"领域知识"hints 指出时或任务明确需要详细规则时）

## delegate_* 返回：直接用 `final_state`，不要再查

```
{"success": true, "tool_calls_made": N,
 "steps_summary": {"by_tool": {...}},
 "final_state": {"boq_items_count": 87, "by_division": {...}}}
```
- `final_state.boq_items_count / by_division` → 代替 `get_project_stats` / `get_divisions_summary`
- `steps_summary.by_tool` 含 `batch_create_boq_items`/`batch_bind_quotas` → 已真正写入
- `tool_calls_made == 0` 或 `success == false` → **不要用同一个 task 重试同一个 Agent**（会死循环），换策略或回复用户

## 部分完成续接
delegate 返回 `error="budget_exceeded"` 但 `tool_calls_made > 0`：读 `final_state` 看还剩多少，**再次调同一个 delegate** 处理剩余项，直到完成。**不要切换到只读 Agent**——那不会完成写操作。

## 其他
- 子 Agent 连接失败（APIConnectionError）→ 换同类 Agent 重试（execute ↔ valuation）
- 最终回答是所有子 Agent 结果的综合总结，结构化、清晰
"""

    def run(
        self,
        ctx: AgentContext,
        instruction: str,
        *,
        on_step=None,
        budget=None,
        registry=None,
        conversation_history=None,
    ) -> AgentResult:
        """Override run to use the orchestrator's own agent registry.

        Phase H7: stashes ``instruction`` and ``ctx`` on the instance so
        ``on_result`` can reach them without a signature change on BaseAgent.
        """
        self._last_instruction = instruction
        self._last_ctx = ctx
        return super().run(
            ctx,
            instruction,
            on_step=on_step,
            budget=budget,
            registry=self._agent_registry,
            conversation_history=conversation_history,
        )

    def stream_run(
        self,
        ctx: AgentContext,
        instruction: str,
        *,
        on_step=None,
        budget=None,
        registry=None,
        conversation_history=None,
    ) -> AgentResult:
        """Override stream_run so the streaming path also uses the
        orchestrator's own agent registry (containing ``delegate_*`` tools).

        Without this override, the LLM sees ``delegate_execute`` in the tool
        schemas (built from ``self.tool_names`` → ``_agent_registry``) but the
        actual execution path falls back to ``global_registry``, which does
        not contain any ``delegate_*`` tool. The model then receives an
        "未知工具: delegate_execute" error at runtime, despite having been
        offered the tool in the schema.
        """
        self._last_instruction = instruction
        self._last_ctx = ctx
        return super().stream_run(
            ctx,
            instruction,
            on_step=on_step,
            budget=budget,
            registry=self._agent_registry,
            conversation_history=conversation_history,
        )

    # ── Phase H7: post-run memory sediment ──

    def on_result(self, ctx: AgentContext, result: AgentResult) -> AgentResult:
        """After the Orchestrator finishes, auto-persist key facts to memory.

        No-op unless ``auto_save_memory`` is True and all preconditions pass:
        - ctx.memory must be attached
        - result must be successful (no error)
        - result.answer must be non-empty
        - extractor must return at least one valid candidate
        """
        if not self.auto_save_memory:
            return result
        if not getattr(result, "success", True):
            return result
        if not result.answer or not result.answer.strip():
            return result

        store = getattr(ctx, "memory", None)
        if store is None:
            return result

        instruction = getattr(self, "_last_instruction", "")
        if not instruction:
            return result

        # Lazily install the default extractor if nothing was set.
        self.__post_init_memory_extractor()
        extractor = self.memory_extractor
        if extractor is None:  # defensive — should never happen after the lazy init
            return result

        try:
            candidates = extractor.extract(instruction, result.answer, ctx)
        except Exception as e:  # pragma: no cover — extractors promise to swallow, but defend anyway
            logger.warning("memory_extractor raised (swallowed): %s", e)
            return result

        if not candidates:
            return result

        saved_keys: list[str] = []
        for mem in candidates:
            try:
                scope_id = self._resolve_scope_id(ctx, mem.scope)
            except ValueError as e:
                logger.debug("skipping extracted memory (%s): %s", mem.key, e)
                continue

            try:
                store.save(
                    scope=mem.scope,  # type: ignore[arg-type]
                    scope_id=scope_id,
                    key=mem.key,
                    content=mem.content,
                    tags=list(mem.tags),
                    importance=mem.importance,
                    created_by_agent=self.name,
                )
                saved_keys.append(mem.key)
            except Exception as e:  # pragma: no cover — store failures shouldn't break response
                logger.warning("auto-save memory failed for %r: %s", mem.key, e)

        if saved_keys:
            # Expose what we saved for observability without mutating the user-visible answer.
            extras = dict(getattr(result, "extra", {}) or {})
            extras["auto_saved_memories"] = saved_keys
            try:
                result.extra = extras  # type: ignore[attr-defined]
            except Exception:  # pragma: no cover
                pass

        return result

    @staticmethod
    def _resolve_scope_id(ctx: AgentContext, scope: str) -> int | None:
        """Turn a scope type into the concrete scope_id using ctx.

        Raises ValueError when the required id is not available on ctx.
        """
        if scope == "global":
            return None
        if scope == "user":
            if ctx.user_id is None:
                raise ValueError("user scope requires ctx.user_id")
            return ctx.user_id
        if scope == "project":
            if ctx.project_id is None:
                raise ValueError("project scope requires ctx.project_id")
            return ctx.project_id
        raise ValueError(f"unknown scope: {scope!r}")
