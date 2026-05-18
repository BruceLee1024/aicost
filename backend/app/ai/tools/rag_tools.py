"""Sprint 9 Phase 3 — RAG tools backed by the persistent VectorStore.

Three tools, all read-only and cacheable:

  * ``search_similar_projects`` — find historical projects that resemble
    the current one by structure / region / total cost.
  * ``search_skill_chunks`` — semantic search over uploaded regulation /
    skill documents (e.g. GB50500, HKSMM4).
  * ``get_price_trend`` — analyze ``MaterialPrice`` history to surface
    rolling averages and momentum signals.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func

from app.ai.framework.context import AgentContext
from app.ai.framework.tool_def import tool
from app.ai.framework.tool_registry import registry
from app.ai.framework.vector_store import VectorStore
from app.models.material_price import MaterialPrice
from app.models.project import Project

logger = logging.getLogger(__name__)


NAMESPACE_PROJECT = "project"
NAMESPACE_SKILL = "skill_chunk"


# ─────────────────────────────────────────────────────────────────
# search_similar_projects
# ─────────────────────────────────────────────────────────────────


@tool(
    name="search_similar_projects",
    description=(
        "查找与当前项目最相似的历史项目（按结构/地区/总价的语义相似度）。"
        "可选参数 query 用于自定义检索文本（默认用项目自身描述）；"
        "top_n 默认 5；min_score 过滤阈值，默认 0。"
        "返回 [{project_id, name, region, score, summary}]。"
    ),
    read_only=True,
)
def search_similar_projects(
    ctx: AgentContext,
    *,
    query: str = "",
    top_n: int = 5,
    min_score: float = 0.0,
) -> str:
    if not ctx.db:
        return json.dumps({"error": "数据库不可用"}, ensure_ascii=False)

    # Build the query text — either user-supplied, or compose from current project.
    text = (query or "").strip()
    if not text and ctx.project_id:
        proj = ctx.db.query(Project).filter(Project.id == ctx.project_id).first()
        if proj is not None:
            text = _project_summary_text(proj)

    if not text:
        return json.dumps(
            {"error": "缺少查询文本，且当前 ctx 无 project_id"},
            ensure_ascii=False,
        )

    store = VectorStore(ctx.db)
    excluded = {str(ctx.project_id)} if ctx.project_id else None
    hits = store.search(
        NAMESPACE_PROJECT,
        text,
        top_n=max(1, min(int(top_n or 5), 20)),
        min_score=float(min_score) if min_score else None,
        exclude_ref_ids=excluded,
    )

    results = []
    for h in hits:
        # Try to enrich with current project info (best-effort).
        meta = h.meta or {}
        try:
            pid = int(h.ref_id)
        except ValueError:
            pid = None
        results.append(
            {
                "project_id": pid,
                "name": meta.get("name", ""),
                "region": meta.get("region", ""),
                "project_type": meta.get("project_type", ""),
                "score": round(h.score, 4),
                "summary": h.snippet[:300] if h.snippet else "",
            }
        )

    return json.dumps(
        {
            "query": text[:200],
            "matched_count": len(results),
            "results": results,
            "namespace": NAMESPACE_PROJECT,
        },
        ensure_ascii=False,
    )


def _project_summary_text(p: Project) -> str:
    parts = [p.name or "", p.region or "", p.project_type or ""]
    if getattr(p, "description", None):
        parts.append(p.description)
    if getattr(p, "standard_type", None):
        parts.append(p.standard_type)
    return " ".join(part for part in parts if part).strip()


# ─────────────────────────────────────────────────────────────────
# search_skill_chunks
# ─────────────────────────────────────────────────────────────────


@tool(
    name="search_skill_chunks",
    description=(
        "在已上传的规范/技能文档（GB50500、HKSMM4 等）中做语义检索。"
        "返回最相关的若干段落，含 skill_name、片段、相似度。"
        "用于回答规范条文 / 标准定义类问题。"
    ),
    read_only=True,
)
def search_skill_chunks(
    ctx: AgentContext,
    *,
    query: str,
    top_n: int = 5,
    min_score: float = 0.0,
    skill_name: str = "",
) -> str:
    if not ctx.db:
        return json.dumps({"error": "数据库不可用"}, ensure_ascii=False)

    q = (query or "").strip()
    if not q:
        return json.dumps({"error": "query 必填"}, ensure_ascii=False)

    store = VectorStore(ctx.db)
    hits = store.search(
        NAMESPACE_SKILL,
        q,
        top_n=max(1, min(int(top_n or 5), 20)),
        min_score=float(min_score) if min_score else None,
    )

    out = []
    for h in hits:
        meta = h.meta or {}
        if skill_name and meta.get("skill_name") and meta["skill_name"] != skill_name:
            continue
        out.append(
            {
                "skill_name": meta.get("skill_name", ""),
                "section": meta.get("section", ""),
                "chunk_index": h.sub_key,
                "score": round(h.score, 4),
                "snippet": h.snippet or "",
            }
        )

    return json.dumps(
        {"query": q[:200], "matched_count": len(out), "results": out},
        ensure_ascii=False,
    )


# ─────────────────────────────────────────────────────────────────
# get_price_trend
# ─────────────────────────────────────────────────────────────────


@tool(
    name="get_price_trend",
    description=(
        "返回某材料/资源最近 N 个月的价格趋势（按 effective_date 聚合）。"
        "输出含 monthly_avg、min、max、最新价、与基准均价的偏离百分比。"
        "用于报告里的'材料价格波动'章节，或回答'XX 最近涨没涨'类问题。"
    ),
    read_only=True,
)
def get_price_trend(
    ctx: AgentContext,
    *,
    name: str = "",
    code: str = "",
    months: int = 12,
) -> str:
    if not ctx.db:
        return json.dumps({"error": "数据库不可用"}, ensure_ascii=False)

    if not name and not code:
        return json.dumps(
            {"error": "name 或 code 至少提供一个"}, ensure_ascii=False
        )

    months = max(1, min(int(months or 12), 60))
    cutoff = datetime.utcnow() - timedelta(days=months * 31)

    q = ctx.db.query(MaterialPrice)
    if code:
        q = q.filter(MaterialPrice.code == code.strip())
    if name:
        q = q.filter(MaterialPrice.name.ilike(f"%{name.strip()}%"))

    rows = q.order_by(MaterialPrice.effective_date.asc().nullsfirst()).all()
    if not rows:
        return json.dumps(
            {"name": name, "code": code, "samples": 0, "message": "无价格记录"},
            ensure_ascii=False,
        )

    # Bucket by year-month
    monthly: dict[str, list[float]] = {}
    for r in rows:
        if not getattr(r, "unit_price", None):
            continue
        ed = r.effective_date
        if ed is None:
            ym = "unknown"
        else:
            try:
                ym = ed.strftime("%Y-%m") if hasattr(ed, "strftime") else str(ed)[:7]
            except Exception:
                ym = str(ed)[:7]
        # Drop very old samples
        if hasattr(ed, "year"):
            try:
                if ed < cutoff:
                    continue
            except TypeError:
                pass
        monthly.setdefault(ym, []).append(float(r.unit_price))

    series = []
    all_prices: list[float] = []
    for ym in sorted(monthly):
        vals = monthly[ym]
        avg = sum(vals) / len(vals)
        series.append(
            {
                "month": ym,
                "samples": len(vals),
                "avg": round(avg, 4),
                "min": round(min(vals), 4),
                "max": round(max(vals), 4),
            }
        )
        all_prices.extend(vals)

    if not all_prices:
        return json.dumps(
            {"name": name, "code": code, "samples": 0, "message": "近期无有效价格"},
            ensure_ascii=False,
        )

    overall_avg = sum(all_prices) / len(all_prices)
    latest = series[-1]["avg"] if series else overall_avg
    deviation_pct = (
        round(((latest - overall_avg) / overall_avg) * 100, 2)
        if overall_avg
        else 0.0
    )

    # Simple momentum: last 3 months avg vs prior 3 months avg
    momentum_pct: float | None = None
    if len(series) >= 4:
        recent = series[-3:]
        prior = series[-6:-3] if len(series) >= 6 else series[:-3]
        if prior:
            r_avg = sum(s["avg"] for s in recent) / len(recent)
            p_avg = sum(s["avg"] for s in prior) / len(prior)
            if p_avg:
                momentum_pct = round(((r_avg - p_avg) / p_avg) * 100, 2)

    return json.dumps(
        {
            "name": name,
            "code": code,
            "months_window": months,
            "samples": len(all_prices),
            "overall_avg": round(overall_avg, 4),
            "latest": latest,
            "deviation_from_avg_pct": deviation_pct,
            "momentum_3m_vs_prior_pct": momentum_pct,
            "series": series,
        },
        ensure_ascii=False,
    )


# ─────────────────────────────────────────────────────────────────
# Register
# ─────────────────────────────────────────────────────────────────

registry.register_many(
    search_similar_projects,
    search_skill_chunks,
    get_price_trend,
)


# Suppress unused-import warning for func if linter complains.
_ = func
