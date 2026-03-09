"""AI-powered BOQ item generation based on project description keywords.

Rule-based template engine that maps description keywords to standard BOQ
item templates. Each template set covers a common construction scope
(foundation, structure, MEP, finishing, etc.).
"""

from dataclasses import dataclass, field


@dataclass
class BoqSuggestion:
    code: str
    name: str
    unit: str
    quantity: float
    division: str
    reason: str  # why this item was suggested
    characteristics: str = ""  # 项目特征


# ── Template library ──────────────────────────────────────────────

_FOUNDATION_ITEMS: list[dict] = [
    {"code": "010101", "name": "土方开挖", "unit": "m³", "qty": 500, "division": "基础工程",
     "characteristics": "1.土壤类别：三类土\n2.开挖深度：≤3m\n3.弃土运距：场内堆放"},
    {"code": "010102", "name": "土方回填", "unit": "m³", "qty": 300, "division": "基础工程",
     "characteristics": "1.填方材料：原土回填\n2.压实系数：≥0.94\n3.分层厚度：每层≤300mm"},
    {"code": "010201", "name": "混凝土垫层 C15", "unit": "m³", "qty": 50, "division": "基础工程",
     "characteristics": "1.混凝土强度等级：C15\n2.垫层厚度：100mm\n3.碎石粒径：5~31.5mm"},
    {"code": "010202", "name": "钢筋混凝土基础 C30", "unit": "m³", "qty": 200, "division": "基础工程",
     "characteristics": "1.混凝土强度等级：C30\n2.基础类型：独立基础\n3.抗渗等级：P6"},
    {"code": "010203", "name": "基础钢筋", "unit": "t", "qty": 15, "division": "基础工程",
     "characteristics": "1.钢筋种类：HRB400\n2.连接方式：机械连接/绑扎搭接\n3.保护层厚度：40mm"},
    {"code": "010301", "name": "防水层施工", "unit": "m²", "qty": 400, "division": "基础工程",
     "characteristics": "1.防水材料：SBS改性沥青防水卷材\n2.厚度：4mm\n3.铺贴层数：两道"},
]

_STRUCTURE_ITEMS: list[dict] = [
    {"code": "020101", "name": "框架柱混凝土 C30", "unit": "m³", "qty": 120, "division": "主体结构",
     "characteristics": "1.混凝土强度等级：C30\n2.柱截面尺寸：400×400mm\n3.浇筑方式：泵送"},
    {"code": "020102", "name": "框架梁混凝土 C30", "unit": "m³", "qty": 180, "division": "主体结构",
     "characteristics": "1.混凝土强度等级：C30\n2.梁截面尺寸：250×500mm\n3.浇筑方式：泵送"},
    {"code": "020103", "name": "现浇楼板混凝土 C30", "unit": "m³", "qty": 300, "division": "主体结构",
     "characteristics": "1.混凝土强度等级：C30\n2.板厚：120mm\n3.浇筑方式：泵送"},
    {"code": "020104", "name": "主体结构钢筋", "unit": "t", "qty": 50, "division": "主体结构",
     "characteristics": "1.钢筋种类：HRB400\n2.连接方式：机械连接/绑扎搭接\n3.保护层厚度：梁25mm、柱30mm"},
    {"code": "020201", "name": "模板工程", "unit": "m²", "qty": 2000, "division": "主体结构",
     "characteristics": "1.模板材质：木胶合板\n2.支撑体系：钢管扣件式\n3.周转次数：≥5次"},
    {"code": "020301", "name": "砌体填充墙 200mm", "unit": "m³", "qty": 150, "division": "主体结构",
     "characteristics": "1.砌块种类：蒸压加气混凝土砌块\n2.墙体厚度：200mm\n3.砂浆强度等级：M5"},
]

_FINISHING_ITEMS: list[dict] = [
    {"code": "030101", "name": "内墙抹灰", "unit": "m²", "qty": 2000, "division": "装饰装修",
     "characteristics": "1.抹灰砂浆：混合砂浆M5\n2.抹灰厚度：20mm\n3.基层处理：界面剂"},
    {"code": "030102", "name": "外墙抹灰", "unit": "m²", "qty": 1200, "division": "装饰装修",
     "characteristics": "1.抹灰砂浆：防水砂浆\n2.抹灰厚度：20mm\n3.挂网处理：镀锌钢丝网"},
    {"code": "030201", "name": "地面找平层", "unit": "m²", "qty": 800, "division": "装饰装修",
     "characteristics": "1.找平材料：1:3水泥砂浆\n2.找平厚度：30mm\n3.表面要求：压光"},
    {"code": "030202", "name": "地砖铺贴", "unit": "m²", "qty": 600, "division": "装饰装修",
     "characteristics": "1.地砖规格：600×600mm\n2.铺贴方式：干铺法\n3.勾缝材料：白水泥"},
    {"code": "030301", "name": "天棚抹灰", "unit": "m²", "qty": 800, "division": "装饰装修",
     "characteristics": "1.抹灰砂浆：混合砂浆M5\n2.抹灰厚度：15mm\n3.表面要求：压光"},
    {"code": "030401", "name": "涂料饰面", "unit": "m²", "qty": 3000, "division": "装饰装修",
     "characteristics": "1.涂料种类：乳胶漆\n2.涂刷遍数：两底两面\n3.基层处理：腻子找平"},
    {"code": "030501", "name": "门窗工程（塑钢窗）", "unit": "m²", "qty": 200, "division": "装饰装修",
     "characteristics": "1.窗框材质：塑钢型材\n2.玻璃类型：5+9A+5中空玻璃\n3.开启方式：平开"},
]

_MEP_ITEMS: list[dict] = [
    {"code": "040101", "name": "给水管道安装 PPR", "unit": "m", "qty": 300, "division": "安装工程",
     "characteristics": "1.管材：PPR管\n2.管径：DN20~DN50\n3.连接方式：热熔连接"},
    {"code": "040102", "name": "排水管道安装 PVC", "unit": "m", "qty": 200, "division": "安装工程",
     "characteristics": "1.管材：PVC-U管\n2.管径：DN75~DN110\n3.连接方式：粘接"},
    {"code": "040201", "name": "电气配管布线", "unit": "m", "qty": 500, "division": "安装工程",
     "characteristics": "1.配管：PVC线管\n2.导线：BV铜芯线\n3.敷设方式：暗敷"},
    {"code": "040202", "name": "配电箱安装", "unit": "台", "qty": 10, "division": "安装工程",
     "characteristics": "1.配电箱类型：低压配电箱\n2.安装方式：暗装\n3.箱体材质：钢板喷塑"},
    {"code": "040203", "name": "照明灯具安装", "unit": "套", "qty": 100, "division": "安装工程",
     "characteristics": "1.灯具类型：LED面板灯\n2.功率：18W\n3.安装方式：嵌入式"},
    {"code": "040301", "name": "消防管道安装", "unit": "m", "qty": 200, "division": "安装工程",
     "characteristics": "1.管材：镀锌钢管\n2.管径：DN65~DN100\n3.连接方式：沟槽连接"},
]

_ROAD_ITEMS: list[dict] = [
    {"code": "050101", "name": "路基土方", "unit": "m³", "qty": 3000, "division": "道路工程",
     "characteristics": "1.土壤类别：三类土\n2.压实度：≥96%\n3.路基宽度：按设计"},
    {"code": "050102", "name": "级配碎石基层", "unit": "m²", "qty": 2000, "division": "道路工程",
     "characteristics": "1.材料：级配碎石\n2.厚度：200mm\n3.压实度：≥98%"},
    {"code": "050201", "name": "水泥稳定碎石", "unit": "m²", "qty": 2000, "division": "道路工程",
     "characteristics": "1.水泥掺量：5%\n2.厚度：180mm\n3.龄期强度：≥3MPa"},
    {"code": "050301", "name": "沥青混凝土面层", "unit": "m²", "qty": 2000, "division": "道路工程",
     "characteristics": "1.面层类型：AC-13细粒式\n2.厚度：50mm\n3.沥青标号：70号A级"},
    {"code": "050401", "name": "路缘石安装", "unit": "m", "qty": 800, "division": "道路工程",
     "characteristics": "1.材质：花岗岩\n2.规格：150×300×1000mm\n3.基础：C15混凝土"},
]

_LANDSCAPE_ITEMS: list[dict] = [
    {"code": "060101", "name": "绿化种植土回填", "unit": "m³", "qty": 200, "division": "园林绿化",
     "characteristics": "1.土壤类型：种植土\n2.有机质含量：≥3%\n3.回填厚度：≥500mm"},
    {"code": "060201", "name": "乔木种植", "unit": "株", "qty": 50, "division": "园林绿化",
     "characteristics": "1.树种：香樟/桂花\n2.胸径：10~12cm\n3.土球直径：≥80cm"},
    {"code": "060202", "name": "灌木种植", "unit": "m²", "qty": 300, "division": "园林绿化",
     "characteristics": "1.品种：红叶石楠/金森女贞\n2.冠幅：30~40cm\n3.种植密度：25株/m²"},
    {"code": "060301", "name": "草坪铺设", "unit": "m²", "qty": 500, "division": "园林绿化",
     "characteristics": "1.草种：百慕大/马尼拉\n2.铺设方式：满铺\n3.养护期：90天"},
]

# ── Keyword → template mapping ────────────────────────────────────

_KEYWORD_MAP: list[tuple[list[str], list[dict], str]] = [
    (["基础", "地基", "桩基", "土方"], _FOUNDATION_ITEMS, "基础工程相关"),
    (["主体", "结构", "框架", "混凝土", "钢筋", "楼"], _STRUCTURE_ITEMS, "主体结构相关"),
    (["装修", "装饰", "抹灰", "涂料", "地砖", "门窗", "精装"], _FINISHING_ITEMS, "装饰装修相关"),
    (["安装", "水电", "给排水", "电气", "管道", "消防", "暖通"], _MEP_ITEMS, "安装工程相关"),
    (["道路", "公路", "路面", "沥青", "市政"], _ROAD_ITEMS, "道路工程相关"),
    (["园林", "绿化", "景观", "种植"], _LANDSCAPE_ITEMS, "园林绿化相关"),
]

# ── Building type → full scope ────────────────────────────────────

_BUILDING_TYPES: list[tuple[list[str], list[list[dict]], str]] = [
    (
        ["办公楼", "办公", "写字楼"],
        [_FOUNDATION_ITEMS, _STRUCTURE_ITEMS, _FINISHING_ITEMS, _MEP_ITEMS],
        "办公楼标准配置",
    ),
    (
        ["住宅", "住宅楼", "居民楼", "小区", "公寓"],
        [_FOUNDATION_ITEMS, _STRUCTURE_ITEMS, _FINISHING_ITEMS, _MEP_ITEMS],
        "住宅楼标准配置",
    ),
    (
        ["学校", "教学楼", "教学"],
        [_FOUNDATION_ITEMS, _STRUCTURE_ITEMS, _FINISHING_ITEMS, _MEP_ITEMS],
        "教学楼标准配置",
    ),
    (
        ["厂房", "工业", "车间", "仓库"],
        [_FOUNDATION_ITEMS, _STRUCTURE_ITEMS, _MEP_ITEMS],
        "工业厂房标准配置",
    ),
]


def _scale_quantity(qty: float, floors: int) -> float:
    """Scale base quantity by number of floors."""
    if floors <= 1:
        return qty
    return round(qty * (0.5 + 0.5 * floors), 1)


def _detect_floors(description: str) -> int:
    """Try to extract number of floors from description."""
    import re
    m = re.search(r"(\d+)\s*[层楼F]", description)
    if m:
        return int(m.group(1))
    return 1


def generate_boq_items(description: str) -> list[BoqSuggestion]:
    """Generate BOQ item suggestions from a natural language description.

    Strategy:
    1. Check if description matches a building type → return full scope.
    2. Otherwise match by individual scope keywords.
    3. Scale quantities by detected floor count.
    """
    desc = description.strip()
    if not desc:
        return []

    floors = _detect_floors(desc)
    matched_templates: list[tuple[list[dict], str]] = []

    # 1. Try building type match first
    for keywords, template_groups, reason in _BUILDING_TYPES:
        if any(kw in desc for kw in keywords):
            for tg in template_groups:
                matched_templates.append((tg, reason))
            break

    # 2. If no building type matched, try individual scope keywords
    if not matched_templates:
        for keywords, templates, reason in _KEYWORD_MAP:
            if any(kw in desc for kw in keywords):
                matched_templates.append((templates, reason))

    # 3. Fallback: if nothing matched, give foundation + structure
    if not matched_templates:
        matched_templates.append((_FOUNDATION_ITEMS, "默认推荐：基础工程"))
        matched_templates.append((_STRUCTURE_ITEMS, "默认推荐：主体结构"))

    # Deduplicate and build suggestions
    seen_codes: set[str] = set()
    suggestions: list[BoqSuggestion] = []

    for templates, reason in matched_templates:
        for t in templates:
            if t["code"] in seen_codes:
                continue
            seen_codes.add(t["code"])
            suggestions.append(BoqSuggestion(
                code=t["code"],
                name=t["name"],
                unit=t["unit"],
                quantity=_scale_quantity(t["qty"], floors),
                division=t["division"],
                reason=f"AI 推荐 ({reason})" + (f" — 按 {floors} 层缩放" if floors > 1 else ""),
                characteristics=t.get("characteristics", ""),
            ))

    return suggestions
