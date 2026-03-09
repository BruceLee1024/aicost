"""BOQ generation agent with LLM-first and deterministic fallback."""

from __future__ import annotations

import json

from app.ai.prompts import load_prompt
from app.ai.providers import AIProviderError, get_ai_provider
from app.ai.schemas.boq import AIBoqGenerateOutput
from app.services.boq_generate_service import BoqSuggestion, generate_boq_items

_DEFAULT_SYSTEM_PROMPT = (
    "你是工程计价助手。输出 BOQ 建议 JSON，不输出金额，不输出额外文本。"
)


# HKSMM4 trade-based BOQ templates
_HKSMM4_TEMPLATES: list[dict] = [
    {"ref": "A/1", "trade": "Preliminaries", "name_en": "Insurance", "name_zh": "保险", "unit": "Item", "qty": 1},
    {"ref": "A/2", "trade": "Preliminaries", "name_en": "Temporary Works", "name_zh": "临时工程", "unit": "Item", "qty": 1},
    {"ref": "B/1", "trade": "Demolition", "name_en": "Demolition of existing structure", "name_zh": "拆除现有结构", "unit": "m2", "qty": 500},
    {"ref": "C/1", "trade": "Earthworks", "name_en": "Excavation to reduce levels", "name_zh": "减低场地挖方", "unit": "m3", "qty": 800},
    {"ref": "C/2", "trade": "Earthworks", "name_en": "Backfilling", "name_zh": "回填", "unit": "m3", "qty": 300},
    {"ref": "E/1", "trade": "Concrete Work", "name_en": "Reinforced concrete to foundations", "name_zh": "基础钢筋混凝土", "unit": "m3", "qty": 200},
    {"ref": "E/2", "trade": "Concrete Work", "name_en": "Reinforced concrete to columns", "name_zh": "柱钢筋混凝土", "unit": "m3", "qty": 120},
    {"ref": "E/3", "trade": "Concrete Work", "name_en": "Reinforced concrete to beams", "name_zh": "梁钢筋混凝土", "unit": "m3", "qty": 180},
    {"ref": "E/4", "trade": "Concrete Work", "name_en": "Reinforced concrete to slabs", "name_zh": "楼板钢筋混凝土", "unit": "m3", "qty": 300},
    {"ref": "E/5", "trade": "Concrete Work", "name_en": "Formwork", "name_zh": "模板", "unit": "m2", "qty": 2000},
    {"ref": "E/6", "trade": "Concrete Work", "name_en": "Reinforcement", "name_zh": "钢筋", "unit": "t", "qty": 50},
    {"ref": "F/1", "trade": "Masonry", "name_en": "Blockwork walls", "name_zh": "砖墙", "unit": "m2", "qty": 600},
    {"ref": "H/1", "trade": "Waterproofing", "name_en": "Waterproof membrane", "name_zh": "防水层", "unit": "m2", "qty": 400},
    {"ref": "L/1", "trade": "Plastering", "name_en": "Cement render to walls", "name_zh": "墙面水泥抓", "unit": "m2", "qty": 2000},
    {"ref": "M/1", "trade": "Tiling", "name_en": "Floor tiling", "name_zh": "地砖", "unit": "m2", "qty": 600},
    {"ref": "N/1", "trade": "Painting", "name_en": "Emulsion paint to walls", "name_zh": "墙面乳胶漆", "unit": "m2", "qty": 3000},
    {"ref": "P/1", "trade": "Plumbing", "name_en": "Water supply pipework", "name_zh": "给水管道", "unit": "m", "qty": 300},
    {"ref": "Q/1", "trade": "Drainage", "name_en": "Drainage pipework", "name_zh": "排水管道", "unit": "m", "qty": 200},
    {"ref": "R/1", "trade": "Electrical", "name_en": "Electrical installation", "name_zh": "电气安装", "unit": "m", "qty": 500},
]


def _generate_hksmm4_items(description: str) -> list[BoqSuggestion]:
    """Generate HKSMM4-style BOQ items from description."""
    from app.services.boq_generate_service import _detect_floors

    floors = _detect_floors(description)
    items: list[BoqSuggestion] = []
    for t in _HKSMM4_TEMPLATES:
        qty = t["qty"]
        if floors > 1 and t["trade"] not in ("Preliminaries",):
            qty = round(qty * (0.5 + 0.5 * floors), 1)
        items.append(BoqSuggestion(
            code=t["ref"],
            name=t["name_zh"],
            unit=t["unit"],
            quantity=qty,
            division=t["trade"],
            reason=f"HKSMM4 {t['trade']} standard item",
            characteristics=t["name_en"],
        ))
    return items


def generate_boq_items_with_agent(
    description: str, standard_type: str = "GB50500",
) -> list[BoqSuggestion]:
    """Generate BOQ suggestions using model when enabled, otherwise deterministic fallback."""
    if standard_type == "HKSMM4":
        fallback = _generate_hksmm4_items(description)
    else:
        fallback = generate_boq_items(description)

    provider = get_ai_provider()
    if not provider.is_enabled() or not provider.is_configured():
        return fallback

    try:
        system_prompt = load_prompt("boq_generate.txt")
    except OSError:
        system_prompt = _DEFAULT_SYSTEM_PROMPT

    # Adjust prompt for HKSMM4
    if standard_type == "HKSMM4":
        system_prompt = (
            "You are a Hong Kong quantity surveyor. Generate BOQ items following HKSMM4 standard. "
            "Each item must have: ref (e.g. A/1), trade section, English description, Chinese name, unit, quantity. "
            "Output JSON suggestions array. Do not output amounts."
        )

    fallback_context = [
        {
            "code": s.code,
            "name": s.name,
            "characteristics": s.characteristics,
            "unit": s.unit,
            "quantity": s.quantity,
            "division": s.division,
            "reason": s.reason,
        }
        for s in fallback
    ]

    user_payload = {
        "description": description,
        "standard_type": standard_type,
        "fallback_suggestions": fallback_context,
    }

    try:
        result = provider.generate_structured(
            task="boq_generate",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
            ],
            schema_model=AIBoqGenerateOutput,
        )
    except AIProviderError:
        return fallback

    if not result.suggestions:
        return fallback

    output: list[BoqSuggestion] = []
    seen_codes: set[str] = set()

    for row in result.suggestions:
        if row.code in seen_codes:
            continue
        seen_codes.add(row.code)
        output.append(
            BoqSuggestion(
                code=row.code,
                name=row.name,
                unit=row.unit,
                quantity=row.quantity,
                division=row.division,
                reason=f"AI 推荐 ({row.reason})",
                characteristics=row.characteristics,
            )
        )

    return output or fallback

