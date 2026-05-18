"""Tests for app/services/code_parser.py — M3 12-digit code parser."""

import json
import pytest

from app.services.code_parser import (
    parse_code,
    validate_code,
    normalise_code,
    segments_to_json,
    feature_text_to_json,
    feature_json_to_text,
    build_feature_json,
    parse_feature_json,
    suggest_variation_code,
    validate_boq_codes,
    PROFESSION_CODES,
)


# ─── parse_code ──────────────────────────────────────────────────────────────

class TestParseCode:
    def test_standard_12_digits(self):
        segs = parse_code("010101001001")
        assert segs is not None
        assert segs.profession == "01"
        assert segs.chapter == "01"
        assert segs.section == "01"
        assert segs.item == "001"
        assert segs.variation == "001"
        assert segs.full_code == "010101001001"

    def test_hyphen_separated(self):
        segs = parse_code("01-01-01-001-001")
        assert segs is not None
        assert segs.full_code == "010101001001"

    def test_pads_short_code(self):
        segs = parse_code("0101")
        assert segs is not None
        assert segs.profession == "01"
        assert segs.chapter == "01"
        assert segs.full_code == "010100000000"

    def test_profession_name_resolved(self):
        segs = parse_code("010101001001")
        assert segs.profession_name == "房屋建筑与装饰工程"

    def test_unknown_profession_name(self):
        segs = parse_code("990101001001")
        assert segs.profession_name == "未知专业"

    def test_none_on_empty(self):
        assert parse_code("") is None
        assert parse_code("   ") is None

    def test_chapter_code_property(self):
        segs = parse_code("010301001001")
        assert segs.chapter_code == "0103"

    def test_section_code_property(self):
        segs = parse_code("010301001001")
        assert segs.section_code == "010301"

    def test_item_code_property(self):
        segs = parse_code("010301001001")
        assert segs.item_code == "010301001"


# ─── validate_code ───────────────────────────────────────────────────────────

class TestValidateCode:
    def test_valid_standard_code(self):
        r = validate_code("010101001001")
        assert r.valid is True
        assert r.errors == []
        assert r.segments is not None

    def test_too_long(self):
        r = validate_code("0101010010011")
        assert r.valid is False
        assert any("超过12位" in e for e in r.errors)

    def test_non_digit(self):
        r = validate_code("ABCDEFGHIJKL")
        assert r.valid is False
        assert any("非数字" in e for e in r.errors)

    def test_short_code_warns(self):
        r = validate_code("01010100")
        assert r.valid is True  # pads OK
        assert any("不足12位" in w for w in r.warnings)

    def test_unknown_profession_is_error(self):
        r = validate_code("990101001001")
        assert r.valid is False
        assert any("专业代码" in e for e in r.errors)

    def test_zero_chapter_warns(self):
        r = validate_code("010001001001")
        assert any("分部" in w for w in r.warnings)

    def test_to_dict_structure(self):
        r = validate_code("010101001001")
        d = r.to_dict()
        assert "valid" in d
        assert "segments" in d
        assert d["segments"]["profession"] == "01"


# ─── normalise_code ──────────────────────────────────────────────────────────

class TestNormaliseCode:
    def test_normalises_with_hyphens(self):
        assert normalise_code("01-01-01-001-001") == "010101001001"

    def test_returns_empty_for_invalid(self):
        assert normalise_code("ZZZZ") == ""

    def test_pads_short(self):
        result = normalise_code("0101")
        assert len(result) == 12
        assert result.startswith("0101")


# ─── segments_to_json ────────────────────────────────────────────────────────

class TestSegmentsToJson:
    def test_returns_json_string(self):
        j = segments_to_json("010101001001")
        data = json.loads(j)
        assert data["profession"] == "01"
        assert data["full_code"] == "010101001001"

    def test_empty_returns_empty_dict(self):
        j = segments_to_json("")
        assert j == "{}"


# ─── feature utilities ───────────────────────────────────────────────────────

class TestFeatureJson:
    def test_build_and_parse_roundtrip(self):
        features = [
            {"name": "土壤类别", "value": "一类土"},
            {"name": "挖土深度", "value": "2m以内"},
        ]
        j = build_feature_json(features)
        items = parse_feature_json(j)
        assert len(items) == 2
        assert items[0].name == "土壤类别"
        assert items[0].value == "一类土"
        assert items[1].name == "挖土深度"

    def test_build_skips_empty_name(self):
        features = [{"name": "", "value": "x"}, {"name": "材料", "value": "C30"}]
        j = build_feature_json(features)
        items = parse_feature_json(j)
        assert len(items) == 1
        assert items[0].name == "材料"

    def test_text_to_json_colon(self):
        text = "土壤类别：一类土\n挖土深度：2m以内"
        j = feature_text_to_json(text)
        items = parse_feature_json(j)
        assert items[0].name == "土壤类别"
        assert items[0].value == "一类土"
        assert items[1].name == "挖土深度"

    def test_text_to_json_ascii_colon(self):
        text = "混凝土强度等级:C30\n钢筋规格:HRB400"
        items = parse_feature_json(feature_text_to_json(text))
        assert items[0].value == "C30"
        assert items[1].value == "HRB400"

    def test_text_to_json_no_separator(self):
        text = "无特殊要求"
        items = parse_feature_json(feature_text_to_json(text))
        assert items[0].name == "无特殊要求"
        assert items[0].value == ""

    def test_json_to_text(self):
        j = build_feature_json([{"name": "土壤类别", "value": "一类土"}])
        text = feature_json_to_text(j)
        assert "土壤类别" in text
        assert "一类土" in text

    def test_parse_empty(self):
        assert parse_feature_json("{}") == []
        assert parse_feature_json("[]") == []
        assert parse_feature_json("") == []

    def test_parse_bad_json(self):
        assert parse_feature_json("NOT JSON") == []


# ─── suggest_variation_code ──────────────────────────────────────────────────

class TestSuggestVariationCode:
    def test_first_variation(self):
        code = suggest_variation_code("010101001", [])
        assert code == "010101001001"

    def test_skips_used(self):
        used = ["010101001001", "010101001002"]
        code = suggest_variation_code("010101001", used)
        assert code == "010101001003"

    def test_gaps_filled(self):
        used = ["010101001001", "010101001003"]
        code = suggest_variation_code("010101001", used)
        assert code == "010101001002"

    def test_hyphenated_existing(self):
        used = ["01-01-01-001-001"]
        code = suggest_variation_code("010101001", used)
        assert code == "010101001002"


# ─── batch validate ──────────────────────────────────────────────────────────

class TestBatchValidate:
    def test_mixed_results(self):
        codes = ["010101001001", "BADINPUT", "030201003001"]
        results = validate_boq_codes(codes)
        assert len(results) == 3
        assert results[0].valid is True
        assert results[1].valid is False
        assert results[2].valid is True
        assert results[2].segments.profession_name == "通用安装工程"
