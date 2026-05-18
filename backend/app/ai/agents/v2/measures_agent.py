"""MeasuresAgent — 措施项目智能管理 Agent.

Responsibilities:
- List / create / update / delete preliminaries (措施项目)
- Propose a GB50500-standard preliminaries kit based on project context
- Recompute project totals after edits

Typical user requests routed here:
- "帮我配置一套标准的措施项目"
- "把安全文明施工费费率改成 3%"
- "删除二次搬运费"
- "看一下当前项目的措施费合计"
"""

from __future__ import annotations

from app.ai.framework.base_agent import BaseAgent
from app.ai.framework.context import AgentContext


class MeasuresAgent(BaseAgent):
    """Preliminaries (措施项目) management agent."""

    @property
    def name(self) -> str:
        return "measures_agent"

    @property
    def description(self) -> str:
        return (
            "措施项目 Agent：管理项目的措施项目（安全文明施工费、脚手架、"
            "模板、垂直运输等），可批量配置标准套餐、调整费率、删除条目、"
            "查询合计。"
        )

    @property
    def tool_names(self) -> list[str]:
        return [
            # Domain
            "list_measures",
            "get_measures_total",
            "create_measure",
            "update_measure",
            "delete_measure",
            "batch_create_measures",
            "propose_standard_measures",
            # Read-only project context
            "get_project_stats",
            # Recompute totals after edits
            "batch_calculate_project",
        ]

    @property
    def max_turns(self) -> int:
        return 12

    @property
    def system_prompt(self) -> str:
        return """\
你是 GB50500 计价规范下的「措施项目」配置专家。

## 你的职责
- 为项目配置/调整/查询措施项目（安全文明施工费、脚手架、模板、垂直运输、夜间施工、二次搬运、冬雨季、降排水等）
- 区分「不可竞争费用」（如安全文明施工费）和「竞争性费用」
- 区分计算基础：`direct`(按直接费乘费率) / `pre_tax`(按税前合计乘费率) / `is_fixed=true`(固定金额)

## 工作流程

### 场景 A：用户要"配置一套标准措施项目"
1. `propose_standard_measures` —— 拿到 GB50500 典型套餐建议
2. 根据项目类型（住宅/商办/高层/装修）筛选适用项，调整费率
3. **一次性** `batch_create_measures` 写入（items 传 JSON 数组）
4. `get_measures_total` 返回写入后的合计，让用户确认
5. **不要**逐条 create_measure — 浪费轮次

### 场景 B：用户要"调整某项费率"
1. `list_measures` 找到要改的条目 id
2. `update_measure(measure_id=X, rate=Y)` 修改

### 场景 C：用户要"查看合计"
1. `get_measures_total` —— 一次返回合计 + 按计算基础分组明细

## 措施项目知识要点
- **安全文明施工费**：不可竞争费用，地区有强制最低标准（一般 2.0%~3.5%），不能随意删除或调低
- **脚手架/模板**：若清单已分项计入则去掉，避免重复
- **垂直运输**：高层（>10 层）项目费率显著提高
- **夜间施工/冬雨季/二次搬运**：项目实际不发生时不要勉强加上，按实结算更合理
- **大型机械进出场费**：按实际次数固定金额（is_fixed=true）

## 严禁
- ❌ 反问"请问要配置哪些措施项目"——你应该用 `propose_standard_measures` 先给方案
- ❌ 一条一条 create_measure（应该 batch）
- ❌ 删除安全文明施工费这种不可竞争费
- ❌ 修改后不调用 `get_measures_total` 给用户看变化

## 输出格式
- 修改完成后给出对比表：`{条目 → 旧费率/金额 → 新费率/金额}`
- 给出措施费合计 + 占总造价的估算比例
- 如果项目尚未做计算，提醒用户运行 `batch_calculate_project`
"""

    def build_user_message(self, ctx: AgentContext, instruction: str) -> str:
        parts = [f"项目ID: {ctx.project_id}"]
        project = ctx.get_project()
        if project:
            meta_bits = [f"名称: {project.name}", f"地区: {project.region}"]
            if project.project_type:
                meta_bits.append(f"类型: {project.project_type}")
            parts.append(" | ".join(meta_bits))
        if instruction:
            parts.append(instruction)
        else:
            parts.append("请先列出当前措施项目，再给出配置建议。")
        return "\n\n".join(parts)
