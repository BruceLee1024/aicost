"""LMMAggregationAgent — 人材机汇总分析 Agent.

Read-only agent that drills into a project's labor / material / machine
resource consumption. Typical user requests:
- "看一下项目的人材机汇总"
- "钢筋用了多少"
- "哪几种材料金额最大"
- "哪些主材还没接信息价"
"""

from __future__ import annotations

from app.ai.framework.base_agent import BaseAgent
from app.ai.framework.context import AgentContext


class LMMAggregationAgent(BaseAgent):
    """Labor / Material / Machine aggregation & analysis agent."""

    @property
    def name(self) -> str:
        return "lmm_agent"

    @property
    def description(self) -> str:
        return (
            "人材机汇总 Agent：分析项目人工/材料/机械资源消耗，识别成本驱动项、"
            "未挂信息价的主材，给出合规与优化建议。"
        )

    @property
    def tool_names(self) -> list[str]:
        return [
            "aggregate_lmm_summary",
            "aggregate_lmm_by_resource",
            "find_main_materials",
            "get_material_prices",
            "get_project_stats",
        ]

    @property
    def read_only(self) -> bool:
        return True

    @property
    def max_turns(self) -> int:
        return 10

    @property
    def system_prompt(self) -> str:
        return """\
你是「人材机汇总」分析专家。基于项目所有清单的定额绑定，聚合实际消耗的资源（人工/材料/机械），\
并给出**金额排序的成本驱动项**和**主材风险提示**。

## 工作流程
1. **先 `aggregate_lmm_summary`** —— 一次拿到合计 + 三大类金额/占比
2. 必要时 `aggregate_lmm_by_resource(category=...)` —— 钻取某一类的明细 Top-N
3. `find_main_materials` —— 列出主材，挑出**未挂信息价**的部分
4. 对未挂信息价的高金额主材，调用 `get_material_prices(name=...)` 看市场价是否存在

## 报告格式（强制）

### 1. 成本结构概览
| 类别 | 金额(元) | 占比 |
|---|---|---|
| 人工 | xxx | xx% |
| 材料 | xxx | xx% |
| 机械 | xxx | xx% |
| **合计** | **xxx** | 100% |

### 2. 成本 Top 10 资源（按金额）
列出名称/规格/单位/总耗量/单价/金额。

### 3. 主材风险
- 主材总数 / 已挂信息价数 / 待挂信息价数
- 待挂信息价金额最大的前 5 项 → 推荐立即接入市场价

### 4. 异常与建议
- 占比异常（如材料占比 > 75% 提醒检查、人工占比 < 8% 提醒漏项）
- 量级异常（钢筋/混凝土与建筑面积单方指标对比）
- 给出**3 条具体可操作建议**

## 严禁
- ❌ 反问"请提供项目数据"——所有数据都在工具里
- ❌ 编造未在工具结果中出现的资源名称
- ❌ 给出占比却不给金额（必须双指标）
"""

    def build_user_message(self, ctx: AgentContext, instruction: str) -> str:
        parts = [f"项目ID: {ctx.project_id}"]
        project = ctx.get_project()
        if project:
            bits = [f"名称: {project.name}", f"地区: {project.region}"]
            if project.project_type:
                bits.append(f"类型: {project.project_type}")
            parts.append(" | ".join(bits))
        if instruction:
            parts.append(instruction)
        else:
            parts.append("请生成完整的人材机汇总报告。")
        return "\n\n".join(parts)
