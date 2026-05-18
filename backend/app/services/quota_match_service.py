"""AI quota matching service.

Enhanced strategy:
  1. Recall: keyword phrase extraction + synonym expansion + unit filter
  2. Re-rank: weighted score (phrase match + char similarity + unit + keyword overlap)
  3. AI rerank: optional LLM reranking for top candidates
  4. Output: TopN candidates with confidence + reason codes
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from sqlalchemy.orm import Session
from app.ai.agents.quota_match_agent import rerank_quota_candidates_with_agent

from app.models.boq_item import BoqItem
from app.models.enterprise_quota_item import STATUS_APPROVED, EnterpriseQuotaItem
from app.models.quota_item import QuotaItem


@dataclass
class MatchCandidate:
    quota_item_id: int
    quota_code: str
    quota_name: str
    unit: str
    confidence: float  # 0.0 ~ 1.0
    reasons: list[str] = field(default_factory=list)
    is_enterprise: bool = False
    source_type: str = "public"  # "public" | "enterprise"


# ── Synonym / keyword expansion tables ──────────────────────────────
_SYNONYMS: dict[str, set[str]] = {
    "混凝土": {"砼", "混凝土", "现浇"},
    "砼": {"混凝土", "砼", "现浇"},
    "钢筋": {"钢筋", "配筋", "HRB"},
    "抹灰": {"抹灰", "粉刷", "抹面"},
    "粉刷": {"抹灰", "粉刷"},
    "涂料": {"涂料", "乳胶漆", "刷漆", "涂刷"},
    "乳胶漆": {"涂料", "乳胶漆", "涂刷"},
    "防水": {"防水", "防潮", "止水"},
    "防潮": {"防水", "防潮"},
    "管道": {"管道", "管线", "配管"},
    "配管": {"管道", "配管", "管线"},
    "给水": {"给水", "上水", "供水"},
    "排水": {"排水", "下水", "污水"},
    "模板": {"模板", "支模"},
    "脚手架": {"脚手架", "架子"},
    "回填": {"回填", "填方", "填土"},
    "开挖": {"开挖", "挖方", "挖土", "土方开挖"},
    "土方": {"土方", "土石方", "挖土", "填土"},
    "砌体": {"砌体", "砌筑", "砌墙", "砖墙"},
    "砌筑": {"砌体", "砌筑"},
    "吊顶": {"吊顶", "天棚", "天花"},
    "天棚": {"天棚", "吊顶", "天花"},
    "门窗": {"门窗", "门", "窗"},
    "塑钢窗": {"塑钢窗", "窗", "门窗"},
    "铝合金窗": {"铝合金窗", "窗", "门窗"},
    "消防": {"消防", "灭火", "喷淋"},
    "照明": {"照明", "灯具", "灯"},
    "灯具": {"照明", "灯具", "灯"},
    "配电箱": {"配电箱", "配电柜", "电箱"},
    "地砖": {"地砖", "地面砖", "瓷砖"},
    "找平": {"找平", "找平层", "地面找平"},
    "基础": {"基础", "地基", "底板"},
    "柱": {"柱", "框架柱", "立柱"},
    "梁": {"梁", "框架梁", "过梁"},
    "楼板": {"楼板", "板", "现浇板"},
    "楼梯": {"楼梯", "梯段"},
    "墙": {"墙", "墙体", "砌体", "填充墙"},
}

# Unit aliases
_UNIT_ALIASES: dict[str, set[str]] = {
    "m³": {"m³", "m3", "立方米", "立方"},
    "m3": {"m³", "m3", "立方米"},
    "m²": {"m²", "m2", "平方米", "平米", "平方"},
    "m2": {"m²", "m2", "平方米"},
    "m": {"m", "米", "延米"},
    "t": {"t", "吨", "T"},
    "台": {"台", "臺"},
    "套": {"套", "组"},
    "个": {"个", "只"},
    "樘": {"樘"},
}


def _tokenize(text: str) -> set[str]:
    """Split on non-word chars, keep Chinese chars individually."""
    tokens: set[str] = set()
    for w in re.findall(r"[a-zA-Z0-9]+", text):
        tokens.add(w.lower())
    for ch in text:
        if "\u4e00" <= ch <= "\u9fff":
            tokens.add(ch)
    return tokens


def _extract_phrases(text: str) -> list[str]:
    """Extract Chinese word phrases (2-4 chars) for better matching."""
    phrases: list[str] = []
    # Extract known keyword phrases
    for kw in _SYNONYMS:
        if kw in text:
            phrases.append(kw)
    # Also extract all 2-char, 3-char, 4-char substrings of Chinese text
    cn = re.sub(r"[^\u4e00-\u9fff]", "", text)
    for length in (4, 3, 2):
        for i in range(len(cn) - length + 1):
            phrases.append(cn[i:i + length])
    return phrases


def _expand_keywords(text: str) -> set[str]:
    """Expand text keywords with synonyms."""
    expanded: set[str] = set()
    for kw, syns in _SYNONYMS.items():
        if kw in text:
            expanded.update(syns)
    expanded.update(_tokenize(text))
    return expanded


def _units_compatible(u1: str, u2: str) -> bool:
    """Check if two units are compatible (exact or alias match)."""
    if u1.strip() == u2.strip():
        return True
    aliases1 = _UNIT_ALIASES.get(u1.strip(), {u1.strip()})
    aliases2 = _UNIT_ALIASES.get(u2.strip(), {u2.strip()})
    return bool(aliases1 & aliases2)


def _name_similarity(a: str, b: str) -> float:
    """Enhanced similarity: phrase match + sequence match + keyword overlap."""
    # Sequence similarity
    seq_score = SequenceMatcher(None, a, b).ratio()

    # Character-level Jaccard
    tokens_a = _tokenize(a)
    tokens_b = _tokenize(b)
    if tokens_a and tokens_b:
        jaccard = len(tokens_a & tokens_b) / len(tokens_a | tokens_b)
    else:
        jaccard = 0.0

    # Phrase overlap bonus
    phrases_a = set(_extract_phrases(a))
    phrases_b = set(_extract_phrases(b))
    if phrases_a and phrases_b:
        phrase_overlap = len(phrases_a & phrases_b) / max(len(phrases_a), len(phrases_b))
    else:
        phrase_overlap = 0.0

    # Synonym-expanded keyword overlap
    kw_a = _expand_keywords(a)
    kw_b = _expand_keywords(b)
    if kw_a and kw_b:
        kw_overlap = len(kw_a & kw_b) / len(kw_a | kw_b)
    else:
        kw_overlap = 0.0

    return 0.35 * seq_score + 0.25 * jaccard + 0.25 * phrase_overlap + 0.15 * kw_overlap


def find_candidates(
    boq_item_id: int,
    db: Session,
    top_n: int = 5,
) -> list[MatchCandidate]:
    """Return top-N quota candidates for a given BOQ item."""

    boq = db.query(BoqItem).filter(BoqItem.id == boq_item_id).first()
    if not boq:
        return []

    quotas = db.query(QuotaItem).all()
    enterprise_quotas = (
        db.query(EnterpriseQuotaItem)
        .filter(EnterpriseQuotaItem.status == STATUS_APPROVED)
        .all()
    )
    if not quotas and not enterprise_quotas:
        return []

    # tuples: (score, id, code, name, unit, reasons, is_enterprise)
    scored: list[tuple[float, int, str, str, str, list[str], bool]] = []

    def _score_quota(
        quota_id: int, quota_code: str, name: str, unit: str, *, is_ent: bool,
    ) -> tuple[float, list[str]]:
        reasons: list[str] = []
        score = 0.0
        # --- Name similarity (weight 0.55) ---
        name_sim = _name_similarity(boq.name, name)
        score += name_sim * 0.55
        if name_sim > 0.5:
            reasons.append(f"名称相似度 {name_sim:.0%}")
        elif name_sim > 0.3:
            reasons.append(f"名称部分匹配 {name_sim:.0%}")
        # --- Unit match (weight 0.30) ---
        if _units_compatible(boq.unit, unit):
            score += 0.30
            reasons.append("单位一致")
        else:
            reasons.append("⚠ 单位不一致")
        # --- Code prefix overlap (weight 0.15) ---
        code_sim = SequenceMatcher(None, boq.code, quota_code).ratio()
        score += code_sim * 0.15
        if code_sim > 0.3:
            reasons.append(f"编码相似 {code_sim:.0%}")
        # --- Enterprise priority boost (capped) ---
        if is_ent:
            score = min(score + 0.15, 1.2)
            reasons.insert(0, "⭐ 企业定额（优先）")
        return score, reasons

    for q in enterprise_quotas:
        s, r = _score_quota(q.id, q.quota_code, q.name, q.unit, is_ent=True)
        scored.append((s, q.id, q.quota_code, q.name, q.unit, r, True))
    for q in quotas:
        s, r = _score_quota(q.id, q.quota_code, q.name, q.unit, is_ent=False)
        scored.append((s, q.id, q.quota_code, q.name, q.unit, r, False))

    # Sort descending by score
    scored.sort(key=lambda x: x[0], reverse=True)
    # Recall more candidates, then optionally rerank via AI agent.
    recall_n = min(len(scored), max(top_n * 3, 15))
    recalled: list[dict] = []
    for score, qid, qcode, qname, qunit, reasons, is_ent in scored[:recall_n]:
        recalled.append(
            {
                "quota_item_id": qid,
                "quota_code": qcode,
                "quota_name": qname,
                "unit": qunit,
                "confidence": round(min(score, 1.0), 3),
                "reasons": reasons,
                "is_enterprise": is_ent,
                "source_type": "enterprise" if is_ent else "public",
            }
        )

    reranked = rerank_quota_candidates_with_agent(
        boq_code=boq.code,
        boq_name=boq.name,
        boq_unit=boq.unit,
        candidates=recalled,
        top_n=top_n,
    )

    # Build a lookup for enterprise flags from the recalled list (the rerank
    # agent is not guaranteed to preserve the new keys, so we re-attach).
    flag_lookup: dict[tuple[int, str], dict[str, object]] = {
        (int(c["quota_item_id"]), str(c["quota_code"])): c for c in recalled
    }
    enriched: list[MatchCandidate] = []
    for c in reranked:
        key = (int(c["quota_item_id"]), str(c["quota_code"]))
        original = flag_lookup.get(key, {})
        is_ent = bool(c.get("is_enterprise", original.get("is_enterprise", False)))
        source_type = str(c.get("source_type", original.get("source_type", "public")))
        enriched.append(
            MatchCandidate(
                quota_item_id=int(c["quota_item_id"]),
                quota_code=str(c["quota_code"]),
                quota_name=str(c["quota_name"]),
                unit=str(c["unit"]),
                confidence=float(c["confidence"]),
                reasons=[str(r) for r in c.get("reasons", [])],
                is_enterprise=is_ent,
                source_type=source_type,
            ),
        )
    return enriched
