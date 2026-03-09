"""Seed HKSMM4 trade sections into boq_standard_codes table.

Usage:
    python seed_hksmm_sections.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from app.db.session import SessionLocal
from app.models.boq_standard_code import BoqStandardCode

HKSMM4_SECTIONS = [
    {
        "standard_code": "HK-A",
        "name": "前期工程/准备工程",
        "name_en": "Preliminaries",
        "standard_unit": "item",
        "division": "Preliminaries",
        "chapter": "Section A",
        "measurement_rule": "Preliminaries items are generally given as lump sums or fixed charges. Include site establishment, temporary works, insurance, and management costs.",
        "common_characteristics": "Site establishment; Temporary works; Insurance; Project management",
    },
    {
        "standard_code": "HK-B",
        "name": "拆卸工程",
        "name_en": "Demolition",
        "standard_unit": "m³",
        "division": "Demolition",
        "chapter": "Section B",
        "measurement_rule": "Demolition measured cube or super depending on element. Includes removal of existing structures, disposal of materials.",
        "common_characteristics": "Demolition of existing structures; Disposal; Temporary support",
    },
    {
        "standard_code": "HK-C",
        "name": "土方工程",
        "name_en": "Earthworks",
        "standard_unit": "m³",
        "division": "Earthworks",
        "chapter": "Section C",
        "measurement_rule": "Excavation measured cube. Reduce level excavation, trench excavation, pit excavation classified by depth. Backfilling measured cube.",
        "common_characteristics": "Excavation type; Depth range; Disposal method; Backfill material",
    },
    {
        "standard_code": "HK-D",
        "name": "打桩工程",
        "name_en": "Piling",
        "standard_unit": "m",
        "division": "Piling",
        "chapter": "Section D",
        "measurement_rule": "Piles measured linear metre for driven/bored piles. Pile caps measured cube. Mini-piles and rock-socketed piles included.",
        "common_characteristics": "Pile type; Diameter; Length; Load capacity; Ground conditions",
    },
    {
        "standard_code": "HK-E",
        "name": "混凝土工程",
        "name_en": "Concrete Work",
        "standard_unit": "m³",
        "division": "Concrete Work",
        "chapter": "Section E",
        "measurement_rule": "All concrete work measured cube except as otherwise provided. Formwork measured super. Reinforcement measured by weight (tonnes).",
        "common_characteristics": "Concrete grade; Element type (slab/beam/column/wall); Formwork type; Reinforcement grade",
    },
    {
        "standard_code": "HK-F",
        "name": "砌体工程",
        "name_en": "Masonry",
        "standard_unit": "m²",
        "division": "Masonry",
        "chapter": "Section F",
        "measurement_rule": "Brick/block walls measured super, classified by thickness. Facework measured separately. Damp proof courses measured linear.",
        "common_characteristics": "Wall thickness; Block/brick type; Mortar specification; Bond pattern",
    },
    {
        "standard_code": "HK-G",
        "name": "结构钢工程",
        "name_en": "Structural Steelwork",
        "standard_unit": "t",
        "division": "Structural Steelwork",
        "chapter": "Section G",
        "measurement_rule": "Structural steelwork measured by weight (tonnes). Includes fabrication, delivery, erection. Connections enumerated or included in rate.",
        "common_characteristics": "Steel grade; Section type; Surface treatment; Connection type",
    },
    {
        "standard_code": "HK-H",
        "name": "金属工程",
        "name_en": "Metalwork",
        "standard_unit": "kg",
        "division": "Metalwork",
        "chapter": "Section H",
        "measurement_rule": "General metalwork measured by weight or enumerated. Includes balustrades, handrails, gratings, ladders.",
        "common_characteristics": "Metal type; Finish; Location; Purpose",
    },
    {
        "standard_code": "HK-J",
        "name": "木工工程",
        "name_en": "Carpentry and Joinery",
        "standard_unit": "m²",
        "division": "Carpentry",
        "chapter": "Section J",
        "measurement_rule": "Timber measured linear or super depending on element. Doors and windows enumerated with full description.",
        "common_characteristics": "Timber species; Section size; Treatment; Purpose",
    },
    {
        "standard_code": "HK-K",
        "name": "防水工程",
        "name_en": "Waterproofing",
        "standard_unit": "m²",
        "division": "Waterproofing",
        "chapter": "Section K",
        "measurement_rule": "Waterproofing measured super. Membrane type, number of layers, surface preparation to be described.",
        "common_characteristics": "Membrane type; Application method; Number of layers; Surface preparation",
    },
    {
        "standard_code": "HK-L",
        "name": "屋面工程",
        "name_en": "Roofing",
        "standard_unit": "m²",
        "division": "Roofing",
        "chapter": "Section L",
        "measurement_rule": "Roof coverings measured super on slope. Flashings measured linear. Insulation measured super.",
        "common_characteristics": "Roof type; Material; Insulation; Slope; Flashing details",
    },
    {
        "standard_code": "HK-M",
        "name": "门窗五金",
        "name_en": "Ironmongery",
        "standard_unit": "nr",
        "division": "Ironmongery",
        "chapter": "Section M",
        "measurement_rule": "Ironmongery items enumerated. Schedule of ironmongery to be provided with full specification.",
        "common_characteristics": "Item type; Material; Finish; Door/window reference",
    },
    {
        "standard_code": "HK-N",
        "name": "玻璃幕墙工程",
        "name_en": "Structural Glazing",
        "standard_unit": "m²",
        "division": "Glazing",
        "chapter": "Section N",
        "measurement_rule": "Glazing measured super. Curtain walling measured super with full specification of framing and glass.",
        "common_characteristics": "Glass type; Thickness; Frame material; Performance specification",
    },
    {
        "standard_code": "HK-P",
        "name": "抹灰/批荡工程",
        "name_en": "Plastering and Rendering",
        "standard_unit": "m²",
        "division": "Plastering",
        "chapter": "Section P",
        "measurement_rule": "Plastering measured super. Classified by number of coats, thickness, and substrate. Screeds measured super.",
        "common_characteristics": "Plaster type; Number of coats; Total thickness; Surface finish",
    },
    {
        "standard_code": "HK-Q",
        "name": "瓷砖工程",
        "name_en": "Tiling",
        "standard_unit": "m²",
        "division": "Tiling",
        "chapter": "Section Q",
        "measurement_rule": "Floor and wall tiling measured super. Classified by tile size, material, and fixing method.",
        "common_characteristics": "Tile material; Size; Fixing method; Grout specification; Location",
    },
    {
        "standard_code": "HK-R",
        "name": "油漆工程",
        "name_en": "Painting and Decorating",
        "standard_unit": "m²",
        "division": "Painting",
        "chapter": "Section R",
        "measurement_rule": "Painting measured super. Classified by number of coats, surface type, and paint system.",
        "common_characteristics": "Paint system; Number of coats; Surface preparation; Surface type",
    },
    {
        "standard_code": "HK-S",
        "name": "排水工程",
        "name_en": "Drainage",
        "standard_unit": "m",
        "division": "Drainage",
        "chapter": "Section S",
        "measurement_rule": "Drains measured linear classified by pipe diameter and depth. Manholes enumerated with full description.",
        "common_characteristics": "Pipe material; Diameter; Depth; Gradient; Manhole type",
    },
    {
        "standard_code": "HK-T",
        "name": "水暖工程",
        "name_en": "Plumbing and Mechanical",
        "standard_unit": "nr",
        "division": "Plumbing",
        "chapter": "Section T",
        "measurement_rule": "Sanitary fittings enumerated. Pipework measured linear classified by diameter. HVAC components enumerated or measured as appropriate.",
        "common_characteristics": "System type; Pipe material; Diameter; Fitting type; Connection method",
    },
    {
        "standard_code": "HK-U",
        "name": "电气工程",
        "name_en": "Electrical Installation",
        "standard_unit": "nr",
        "division": "Electrical",
        "chapter": "Section U",
        "measurement_rule": "Cable measured linear classified by size. Points enumerated. Distribution boards and switchgear enumerated with full specification.",
        "common_characteristics": "Cable type; Size; Accessory type; Rating; Location",
    },
    {
        "standard_code": "HK-V",
        "name": "电梯工程",
        "name_en": "Lift Installation",
        "standard_unit": "nr",
        "division": "Lifts",
        "chapter": "Section V",
        "measurement_rule": "Lifts enumerated with full specification including capacity, speed, number of stops.",
        "common_characteristics": "Lift type; Capacity; Speed; Number of stops; Control system",
    },
    {
        "standard_code": "HK-W",
        "name": "外部工程",
        "name_en": "External Works",
        "standard_unit": "m²",
        "division": "External Works",
        "chapter": "Section W",
        "measurement_rule": "Roads and paths measured super. Fencing measured linear. Landscaping measured super or enumerated.",
        "common_characteristics": "Surface material; Subbase specification; Edge treatment; Planting type",
    },
    {
        "standard_code": "HK-X",
        "name": "暂定金额",
        "name_en": "Provisional Sums",
        "standard_unit": "sum",
        "division": "Provisional Sums",
        "chapter": "Section X",
        "measurement_rule": "Provisional sums stated as lump sums. Defined and undefined provisional sums to be distinguished.",
        "common_characteristics": "Defined or undefined; Purpose; Anticipated scope",
    },
    {
        "standard_code": "HK-Y",
        "name": "日工/计日工",
        "name_en": "Daywork",
        "standard_unit": "hr",
        "division": "Daywork",
        "chapter": "Section Y",
        "measurement_rule": "Daywork labour measured in hours by trade category. Materials at cost plus percentage. Plant at hire rates.",
        "common_characteristics": "Labour category; Hourly rate; Material handling; Plant type",
    },
]


def main():
    db = SessionLocal()
    try:
        inserted = 0
        for sec in HKSMM4_SECTIONS:
            existing = (
                db.query(BoqStandardCode)
                .filter(BoqStandardCode.standard_code == sec["standard_code"])
                .first()
            )
            if existing:
                continue
            record = BoqStandardCode(
                standard_code=sec["standard_code"],
                name=sec["name"],
                name_en=sec["name_en"],
                standard_unit=sec["standard_unit"],
                division=sec["division"],
                chapter=sec["chapter"],
                measurement_rule=sec["measurement_rule"],
                common_characteristics=sec["common_characteristics"],
                standard_version="HKSMM4-2018",
                standard_type="HKSMM4",
            )
            db.add(record)
            inserted += 1
        db.commit()
        print(f"HKSMM4 seed complete: inserted {inserted}, skipped {len(HKSMM4_SECTIONS) - inserted}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
