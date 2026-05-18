"""GB50500 12-digit BOQ code parser, validator, and project-feature structuring.

12-digit structure per GB 50500 / GB/T 50500:
  ┌─────┬─────┬─────┬─────┬─────┐
  │ 01  │ 02  │ 03  │ 04  │ 005 │
  │专业  │分部  │分项  │清单  │特征  │
  └─────┴─────┴─────┴─────┴─────┘
  pos:  1-2   3-4   5-6   7-9  10-12

Profession codes (positions 1-2):
  01  房屋建筑与装饰工程
  02  仿古建筑工程
  03  通用安装工程
  04  市政工程
  05  园林绿化工程
  06  矿山工程
  07  构筑物工程
  08  城市轨道交通工程
  09  爆破工程

Feature JSON schema
-------------------
A feature_json field on BoqItem stores structured item characteristics as a
list of {"name": ..., "value": ...} dicts, e.g.::

    [
        {"name": "土壤类别", "value": "一类土"},
        {"name": "挖土深度", "value": "2m以内"},
        {"name": "弃土运距", "value": "5km以内"}
    ]
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from typing import Any


# ---------------------------------------------------------------------------
# Profession registry
# ---------------------------------------------------------------------------

PROFESSION_CODES: dict[str, str] = {
    "01": "房屋建筑与装饰工程",
    "02": "仿古建筑工程",
    "03": "通用安装工程",
    "04": "市政工程",
    "05": "园林绿化工程",
    "06": "矿山工程",
    "07": "构筑物工程",
    "08": "城市轨道交通工程",
    "09": "爆破工程",
}

PROFESSION_CODE_REVERSE: dict[str, str] = {v: k for k, v in PROFESSION_CODES.items()}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class CodeSegments:
    """Parsed segments of a 12-digit BOQ code."""
    raw: str               # original input (may be shorter)
    profession: str        # 2 digits — 专业工程代码
    chapter: str           # 2 digits — 分部工程顺序码
    section: str           # 2 digits — 分项工程项目名称顺序码
    item: str              # 3 digits — 清单项目名称顺序码
    variation: str         # 3 digits — 清单项目特征顺序码
    profession_name: str = ""

    def to_dict(self) -> dict[str, str]:
        d = asdict(self)
        d["full_code"] = self.full_code
        d["chapter_code"] = self.chapter_code
        d["section_code"] = self.section_code
        d["item_code"] = self.item_code
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @property
    def full_code(self) -> str:
        """Reconstruct the normalised 12-digit code."""
        return self.profession + self.chapter + self.section + self.item + self.variation

    @property
    def chapter_code(self) -> str:
        """First 4 digits — 专业+分部."""
        return self.profession + self.chapter

    @property
    def section_code(self) -> str:
        """First 6 digits — 专业+分部+分项."""
        return self.profession + self.chapter + self.section

    @property
    def item_code(self) -> str:
        """First 9 digits — 专业+分部+分项+清单名."""
        return self.profession + self.chapter + self.section + self.item


@dataclass
class ValidationResult:
    valid: bool
    code: str
    errors: list[str]
    warnings: list[str]
    segments: CodeSegments | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "valid": self.valid,
            "code": self.code,
            "errors": self.errors,
            "warnings": self.warnings,
        }
        if self.segments:
            d["segments"] = self.segments.to_dict()
        return d


@dataclass
class FeatureItem:
    name: str
    value: str
    sort_order: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "value": self.value, "sort_order": self.sort_order}


# ---------------------------------------------------------------------------
# Code parser
# ---------------------------------------------------------------------------

_CODE_CLEAN_RE = re.compile(r"[^0-9A-Za-z]")


def _clean_code(raw: str) -> str:
    """Strip hyphens, spaces, dots from raw input."""
    return _CODE_CLEAN_RE.sub("", raw.strip())


def parse_code(raw: str) -> CodeSegments | None:
    """Parse a raw BOQ code string into CodeSegments.

    Accepts codes with or without separators, and pads to 12 digits if short.
    Returns None only if the input is completely un-parseable (non-numeric).
    """
    clean = _clean_code(raw)
    if not clean:
        return None

    # Pad to 12 digits
    padded = clean.ljust(12, "0")[:12]

    profession = padded[0:2]
    chapter = padded[2:4]
    section = padded[4:6]
    item = padded[6:9]
    variation = padded[9:12]

    return CodeSegments(
        raw=raw,
        profession=profession,
        chapter=chapter,
        section=section,
        item=item,
        variation=variation,
        profession_name=PROFESSION_CODES.get(profession, "未知专业"),
    )


def validate_code(raw: str) -> ValidationResult:
    """Validate a BOQ code against GB50500 rules.

    Checks:
    - Must be exactly 12 digits
    - Profession code must be known
    - Chapter / section / item must be non-zero (at least first segment)
    """
    clean = _clean_code(raw)
    errors: list[str] = []
    warnings: list[str] = []

    if not clean:
        return ValidationResult(valid=False, code=raw, errors=["编码为空"], warnings=[])

    if not clean.isdigit():
        errors.append(f"编码包含非数字字符: '{clean}'")

    if len(clean) < 12:
        warnings.append(f"编码长度 {len(clean)} 位，不足12位（已末位补0）")
    elif len(clean) > 12:
        errors.append(f"编码长度 {len(clean)} 位，超过12位")

    if errors:
        return ValidationResult(valid=False, code=raw, errors=errors, warnings=warnings)

    segments = parse_code(raw)
    if segments is None:
        return ValidationResult(valid=False, code=raw, errors=["解析失败"], warnings=warnings)

    if segments.profession not in PROFESSION_CODES:
        errors.append(
            f"专业代码 '{segments.profession}' 不在标准范围 ({', '.join(PROFESSION_CODES)})，"
            "请确认是否为自定义专业"
        )

    if segments.chapter == "00":
        warnings.append("分部工程顺序码为 00，通常表示分部未定")

    if segments.section == "00":
        warnings.append("分项工程顺序码为 00，通常表示分项未定")

    if segments.item == "000":
        warnings.append("清单项目名称顺序码为 000，通常表示清单项未定")

    valid = len(errors) == 0
    return ValidationResult(
        valid=valid, code=raw, errors=errors, warnings=warnings, segments=segments
    )


def segments_to_json(raw: str) -> str:
    """Parse code and return JSON string (for storage in code_segments_json)."""
    segs = parse_code(raw)
    if segs is None:
        return "{}"
    return segs.to_json()


# ---------------------------------------------------------------------------
# Feature JSON utilities
# ---------------------------------------------------------------------------

def parse_feature_json(feature_json: str) -> list[FeatureItem]:
    """Deserialise feature_json into FeatureItem list."""
    if not feature_json or feature_json.strip() in ("{}", "[]", ""):
        return []
    try:
        data = json.loads(feature_json)
    except (json.JSONDecodeError, TypeError):
        return []

    items: list[FeatureItem] = []
    if isinstance(data, list):
        for i, entry in enumerate(data):
            if isinstance(entry, dict):
                name = str(entry.get("name", ""))
                value = str(entry.get("value", ""))
                sort_order = int(entry.get("sort_order", i))
                if name:
                    items.append(FeatureItem(name=name, value=value, sort_order=sort_order))
    return items


def build_feature_json(features: list[dict[str, Any]]) -> str:
    """Build feature_json from a list of {name, value} dicts."""
    result = []
    for i, f in enumerate(features):
        name = str(f.get("name", "")).strip()
        value = str(f.get("value", "")).strip()
        if name:
            result.append({"name": name, "value": value, "sort_order": i})
    return json.dumps(result, ensure_ascii=False)


def feature_text_to_json(text: str) -> str:
    """Convert plain-text feature description (one per line) to feature JSON.

    Each line format: "特征名称：特征值" or "特征名称:特征值"
    Lines without a separator are stored with empty value.

    Example input::
        土壤类别：一类土
        挖土深度：2m以内
        弃土运距：5km以内
    """
    items = []
    for i, line in enumerate(text.splitlines()):
        line = line.strip()
        if not line:
            continue
        if "：" in line:
            name, _, value = line.partition("：")
        elif ":" in line:
            name, _, value = line.partition(":")
        else:
            name, value = line, ""
        name = name.strip()
        value = value.strip()
        if name:
            items.append({"name": name, "value": value, "sort_order": i})
    return json.dumps(items, ensure_ascii=False)


def feature_json_to_text(feature_json: str) -> str:
    """Convert feature JSON back to human-readable plain text."""
    items = parse_feature_json(feature_json)
    lines = [f"{it.name}：{it.value}" if it.value else it.name for it in items]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Batch utilities
# ---------------------------------------------------------------------------

def validate_boq_codes(codes: list[str]) -> list[ValidationResult]:
    """Validate a list of BOQ codes, returning one ValidationResult per code."""
    return [validate_code(c) for c in codes]


def normalise_code(raw: str) -> str:
    """Return the normalised 12-digit code, or empty string if invalid."""
    result = validate_code(raw)
    if result.segments:
        return result.segments.full_code
    return ""


def suggest_variation_code(base_item_code: str, existing_variations: list[str]) -> str:
    """Suggest the next available variation suffix (positions 10-12).

    Args:
        base_item_code: 9-digit prefix (profession+chapter+section+item)
        existing_variations: list of full 12-digit codes already used

    Returns:
        Full 12-digit code with the next free 3-digit variation suffix.
    """
    prefix = _clean_code(base_item_code)[:9].ljust(9, "0")
    used: set[int] = set()
    for full in existing_variations:
        c = _clean_code(full)
        if c.startswith(prefix) and len(c) == 12:
            try:
                used.add(int(c[9:12]))
            except ValueError:
                pass

    for i in range(1, 1000):
        if i not in used:
            return prefix + str(i).zfill(3)
    return prefix + "999"
