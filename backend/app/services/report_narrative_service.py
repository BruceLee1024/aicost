"""Sprint 9 Phase 4 — AI-generated executive narrative for reports.

Reads aggregate project metrics and asks an LLM to produce a 3-paragraph
markdown narrative covering:

  1. **执行摘要** — total cost, key indicators, anomalies
  2. **分部分析** — per-division share, deviations vs typical benchmarks,
     comparison with similar projects (RAG)
  3. **风险与建议** — material price volatility, items deviating from
     industry averages

If no LLM is configured, falls back to a deterministic template-based
summary so the report still gets a useful (if shorter) blurb.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

from sqlalchemy.orm import Session

from app.ai.framework.context import AgentContext
from app.ai.framework.tool_registry import registry
from app.ai.providers.factory import get_ai_provider
from app.ai.providers.base import (
    AIProviderError,
    StructuredMessage,
)
from app.models.project import Project
from app.services.project_calc_service import run_project_calculation

logger = logging.getLogger(__name__)


def _gather_metrics(project_id: int, db: Session) -> dict[str, Any]:
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None:
        return {}
    summary, line_results = run_project_calculation(project_id=project_id, db=db)

    div_totals: dict[str, float] = defaultdict(float)
    div_counts: dict[str, int] = defaultdict(int)
    for boq, result in line_results:
        d = boq.division or "未分类"
        div_totals[d] += result.total
        div_counts[d] += 1

    grand = summary.grand_total or 1
    divisions = [
        {
            "division": d,
            "items": div_counts[d],
            "amount": round(t, 2),
            "pct": round(t / grand * 100, 1),
        }
        for d, t in sorted(div_totals.items(), key=lambda x: -x[1])
    ]

    return {
        "project_name": project.name,
        "project_type": project.project_type,
        "region": project.region,
        "standard": project.standard_type,
        "currency": project.currency,
        "total_items": len(line_results),
        "grand_total": round(summary.grand_total or 0, 2),
        "direct": round(summary.total_direct or 0, 2),
        "tax": round(summary.total_tax or 0, 2),
        "measures": round(summary.total_measures or 0, 2),
        "divisions": divisions,
    }


def _similar_projects_block(project_id: int, db: Session) -> str:
    """Return a short text block listing similar projects via the RAG tool.

    Returns empty string if RAG indexing yields no matches or fails.
    """
    try:
        ctx = AgentContext(db=db, project_id=project_id)
        result_str = registry.execute(
            "search_similar_projects",
            {"top_n": 3, "min_score": 0.3},
            ctx,
        )
        import json as _json

        result = _json.loads(result_str)
        results = result.get("results", [])
        if not results:
            return ""
        lines = []
        for r in results[:3]:
            lines.append(
                f"- {r.get('name')}（{r.get('region')}, {r.get('project_type')}）— 相似度 {r.get('score')}"
            )
        return "\n".join(lines)
    except Exception:
        logger.debug("similar_projects lookup failed", exc_info=True)
        return ""


def _fallback_narrative(metrics: dict[str, Any]) -> str:
    """Deterministic template when LLM is disabled."""
    if not metrics:
        return "无可用项目数据。"
    divs = metrics.get("divisions", [])
    top_div = divs[0] if divs else None
    parts = [
        f"## 执行摘要\n\n本项目「{metrics['project_name']}」位于{metrics['region']}，"
        f"项目类型为{metrics['project_type']}。本次计价共统计 {metrics['total_items']} 条清单项，"
        f"工程总价 {metrics['grand_total']:,.2f} {metrics['currency']}，"
        f"其中直接费 {metrics['direct']:,.2f}、税金 {metrics['tax']:,.2f}、措施费 {metrics['measures']:,.2f}。",
    ]
    if top_div:
        parts.append(
            f"## 分部分析\n\n占比最大的分部为「{top_div['division']}」"
            f"（{top_div['amount']:,.2f}，占 {top_div['pct']}%），共 {top_div['items']} 项。"
            f"全部分部数量为 {len(divs)} 个。"
        )
    parts.append(
        "## 风险与建议\n\n建议对占比超过 30% 的分部做进一步核对；"
        "材料价格存在波动的项目应在投标前刷新最近 3 个月行情。"
    )
    return "\n\n".join(parts)


def generate_narrative(project_id: int, db: Session) -> str:
    """Generate a markdown narrative for a project's report."""
    metrics = _gather_metrics(project_id, db)
    if not metrics:
        return ""

    similar_block = _similar_projects_block(project_id, db)

    provider = get_ai_provider()
    if not provider.is_enabled() or not provider.is_configured():
        logger.info("LLM disabled — falling back to template narrative")
        text = _fallback_narrative(metrics)
        if similar_block:
            text += f"\n\n## 相似历史项目\n\n{similar_block}"
        return text

    # ── Compose prompt ──
    system = (
        "你是一名专业的工程造价分析师。请基于给定的造价数据，"
        "用结构化中文 markdown 输出 3 段："
        "## 执行摘要、## 分部分析、## 风险与建议。"
        "每段 100~200 字，避免空话和套话，引用具体数字，"
        "并在适当处给出可操作的建议。"
    )
    user_lines = [
        f"项目名称：{metrics['project_name']}",
        f"项目类型：{metrics['project_type']}（{metrics['standard']}）",
        f"地区：{metrics['region']}",
        f"清单项数：{metrics['total_items']}",
        f"工程总价：{metrics['grand_total']:,.2f} {metrics['currency']}",
        f"直接费：{metrics['direct']:,.2f}，税金：{metrics['tax']:,.2f}，措施费：{metrics['measures']:,.2f}",
        "",
        "分部明细（按占比降序，前 8 项）：",
    ]
    for d in metrics["divisions"][:8]:
        user_lines.append(
            f"- {d['division']}: {d['amount']:,.2f} ({d['pct']}%, {d['items']} 项)"
        )
    if similar_block:
        user_lines.extend(["", "可参考的相似历史项目：", similar_block])

    messages: list[StructuredMessage] = [
        StructuredMessage(role="system", content=system),
        StructuredMessage(role="user", content="\n".join(user_lines)),
    ]

    try:
        text = provider.generate_text(task="report_narrative", messages=messages)
        if similar_block and "相似" not in text:
            text += f"\n\n## 相似历史项目\n\n{similar_block}"
        return text.strip()
    except AIProviderError as e:
        logger.warning("narrative LLM failed (%s); using fallback", e)
        return _fallback_narrative(metrics)
