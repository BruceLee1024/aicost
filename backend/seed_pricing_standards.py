"""Seed GB50500-2013 and GB/T 50500-2024 pricing standards + fee structure trees.

Also back-fills existing Projects with pricing_standard_id = GB50500-2013 (default).

Usage:
    PYTHONPATH=. python seed_pricing_standards.py
"""

import json
import sqlite3
import sys

DB_PATH = "valuation.db"

# ─── Standard definitions ────────────────────────────────────────────────────

STANDARDS = [
    {
        "code": "GB50500-2013",
        "name_zh": "建设工程工程量清单计价规范（GB 50500-2013）",
        "name_en": "Code of Valuation with Bill of Quantities for Construction Works (GB 50500-2013)",
        "year": 2013,
        "region": "全国",
        "profession": "general",
        "effective_date": "2013-07-01",
        "description": "现行国家标准，适用于建设工程发承包及实施阶段的计价活动。",
        "rounding_rule": "round2",
        "coding_rule_json": json.dumps({
            "boq_code_length": 12,
            "segments": [
                {"name": "chapter", "start": 1, "end": 2},
                {"name": "section", "start": 3, "end": 4},
                {"name": "item", "start": 5, "end": 6},
                {"name": "detail", "start": 7, "end": 9},
                {"name": "variation", "start": 10, "end": 12},
            ],
        }),
        "fee_structure_json": json.dumps({
            "root": ["fen_bu", "cuo_shi", "other", "gui_fei", "tax"],
        }),
        "is_active": 1,
    },
    {
        "code": "GBT50500-2024",
        "name_zh": "建设工程工程量清单计价标准（GB/T 50500-2024）",
        "name_en": "Standard of Valuation with Bill of Quantities for Construction Works (GB/T 50500-2024)",
        "year": 2024,
        "region": "全国",
        "profession": "building",
        "effective_date": "2025-01-01",
        "description": "新版国家标准，引入动态人工费指数，强化项目特征结构化，适用于房屋建筑与市政工程。",
        "rounding_rule": "round2",
        "coding_rule_json": json.dumps({
            "boq_code_length": 12,
            "segments": [
                {"name": "chapter", "start": 1, "end": 2},
                {"name": "section", "start": 3, "end": 4},
                {"name": "item", "start": 5, "end": 6},
                {"name": "detail", "start": 7, "end": 9},
                {"name": "variation", "start": 10, "end": 12},
            ],
            "dynamic_labor_index": True,
        }),
        "fee_structure_json": json.dumps({
            "root": ["fen_bu", "cuo_shi", "other", "gui_fei", "tax"],
            "dynamic_labor": True,
        }),
        "is_active": 1,
    },
]

# ─── Fee structure trees ──────────────────────────────────────────────────────
# Each entry: (fee_code, name, formula, base_code, default_rate, is_competitive, is_leaf, sort_order, description, parent_code)
# parent_code=None → root node

FEE_TREES = {
    "GB50500-2013": [
        # Root nodes
        ("fen_bu",   "分部分项工程费", "sum",    "",          0.0,   0, 0, 1, "清单综合单价×工程量之和", None),
        ("cuo_shi",  "措施项目费",     "sum",    "",          0.0,   0, 0, 2, "通用措施+专业措施", None),
        ("other",    "其他项目费",     "sum",    "",          0.0,   0, 0, 3, "暂列金额+专业工程暂估价+计日工+总承包服务费", None),
        ("gui_fei",  "规费",           "rate",   "fen_bu",    0.035, 0, 0, 4, "社会保险费+住房公积金", None),
        ("tax",      "税金",           "rate",   "subtotal",  0.09,  0, 1, 5, "增值税（一般计税法9%）", None),
        # 分部分项子项
        ("fen_bu.clr",  "人工费",     "sum", "fen_bu",  0.0, 0, 1, 11, "综合单价中人工费合计", "fen_bu"),
        ("fen_bu.clm",  "材料费",     "sum", "fen_bu",  0.0, 0, 1, 12, "综合单价中材料费合计", "fen_bu"),
        ("fen_bu.clj",  "机械费",     "sum", "fen_bu",  0.0, 0, 1, 13, "综合单价中机械费合计", "fen_bu"),
        ("fen_bu.qfei", "企业管理费", "rate", "fen_bu", 0.055, 1, 1, 14, "企业管理费费率×（人工费+机械费）", "fen_bu"),
        ("fen_bu.lirun","利润",        "rate", "fen_bu", 0.05,  1, 1, 15, "利润率×（人工费+机械费）", "fen_bu"),
        # 措施项目子项
        ("cuo_shi.anquanwm", "安全文明施工费", "rate", "fen_bu", 0.02,  0, 1, 21, "强制性，不参与竞争", "cuo_shi"),
        ("cuo_shi.temp",     "临时设施费",     "rate", "fen_bu", 0.015, 1, 1, 22, "可竞争", "cuo_shi"),
        ("cuo_shi.other",    "其他通用措施费", "rate", "fen_bu", 0.01,  1, 1, 23, "可竞争", "cuo_shi"),
        # 其他项目子项
        ("other.zljine",  "暂列金额",      "fixed", "", 0.0, 0, 1, 31, "招标人估计的不确定金额", "other"),
        ("other.zhjia",   "专业工程暂估价", "fixed", "", 0.0, 0, 1, 32, "专业工程暂估价之和", "other"),
        ("other.jirg",    "计日工",        "sum",   "", 0.0, 1, 1, 33, "计日工明细合计", "other"),
        ("other.zb_svc",  "总承包服务费",  "rate",  "zhjia", 0.015, 1, 1, 34, "总承包管理协调服务费", "other"),
        # 规费子项
        ("gui_fei.shebx", "社会保险费", "rate", "fen_bu.clr", 0.285, 0, 1, 41, "养老+医疗+失业+工伤+生育保险", "gui_fei"),
        ("gui_fei.gjjin", "住房公积金", "rate", "fen_bu.clr", 0.08,  0, 1, 42, "住房公积金", "gui_fei"),
    ],
    "GBT50500-2024": [
        # Root nodes（与2013版结构相同，扩展动态人工费）
        ("fen_bu",   "分部分项工程费", "sum",  "",         0.0,   0, 0, 1, "清单综合单价×工程量之和（2024版含动态人工费调整）", None),
        ("cuo_shi",  "措施项目费",     "sum",  "",         0.0,   0, 0, 2, "通用措施+专业措施", None),
        ("other",    "其他项目费",     "sum",  "",         0.0,   0, 0, 3, "暂列金额+专业工程暂估价+计日工+总承包服务费", None),
        ("gui_fei",  "规费",           "rate", "fen_bu",   0.035, 0, 0, 4, "社会保险费+住房公积金（2024版按实际费率）", None),
        ("tax",      "税金",           "rate", "subtotal", 0.09,  0, 1, 5, "增值税（一般计税法9%）", None),
        # 分部分项子项（2024版人工费拆为基期+动态调差）
        ("fen_bu.clr",       "人工费（基期）",   "sum",  "fen_bu",     0.0,   0, 1, 11, "基期综合单价中人工费合计", "fen_bu"),
        ("fen_bu.clr_delta", "人工费动态调差",   "rate", "fen_bu.clr", 0.0,   0, 1, 12, "动态指数调整额 = 基期人工费 × (指数-1)", "fen_bu"),
        ("fen_bu.clm",       "材料费",           "sum",  "fen_bu",     0.0,   0, 1, 13, "综合单价中材料费合计", "fen_bu"),
        ("fen_bu.clj",       "机械费",           "sum",  "fen_bu",     0.0,   0, 1, 14, "综合单价中机械费合计", "fen_bu"),
        ("fen_bu.qfei",      "企业管理费",       "rate", "fen_bu",     0.055, 1, 1, 15, "企业管理费费率×（人工费+机械费）", "fen_bu"),
        ("fen_bu.lirun",     "利润",             "rate", "fen_bu",     0.05,  1, 1, 16, "利润率×（人工费+机械费）", "fen_bu"),
        # 措施项目子项
        ("cuo_shi.anquanwm", "安全文明施工费", "rate", "fen_bu", 0.02,  0, 1, 21, "强制性，不参与竞争", "cuo_shi"),
        ("cuo_shi.temp",     "临时设施费",     "rate", "fen_bu", 0.015, 1, 1, 22, "可竞争", "cuo_shi"),
        ("cuo_shi.other",    "其他通用措施费", "rate", "fen_bu", 0.01,  1, 1, 23, "可竞争", "cuo_shi"),
        # 其他项目子项
        ("other.zljine",  "暂列金额",      "fixed", "",      0.0,   0, 1, 31, "招标人估计的不确定金额", "other"),
        ("other.zhjia",   "专业工程暂估价", "fixed", "",      0.0,   0, 1, 32, "专业工程暂估价之和", "other"),
        ("other.jirg",    "计日工",        "sum",   "",      0.0,   1, 1, 33, "计日工明细合计", "other"),
        ("other.zb_svc",  "总承包服务费",  "rate",  "zhjia", 0.015, 1, 1, 34, "总承包管理协调服务费", "other"),
        # 规费子项
        ("gui_fei.shebx", "社会保险费", "rate", "fen_bu.clr", 0.285, 0, 1, 41, "养老+医疗+失业+工伤+生育保险（2024版费率参考省级标准）", "gui_fei"),
        ("gui_fei.gjjin", "住房公积金", "rate", "fen_bu.clr", 0.08,  0, 1, 42, "住房公积金", "gui_fei"),
    ],
}


def seed(db_path: str = DB_PATH) -> None:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    std_id_map: dict[str, int] = {}

    # ── Insert / upsert standards ─────────────────────────────────────────────
    for s in STANDARDS:
        cur.execute(
            "SELECT id FROM pricing_standards WHERE code = ? AND region = ?",
            (s["code"], s["region"]),
        )
        row = cur.fetchone()
        if row:
            std_id_map[s["code"]] = row["id"]
            print(f"[SKIP] PricingStandard already exists: {s['code']} (id={row['id']})")
        else:
            cur.execute(
                """INSERT INTO pricing_standards
                   (code, name_zh, name_en, year, region, profession,
                    coding_rule_json, fee_structure_json, rounding_rule,
                    effective_date, description, is_active)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    s["code"], s["name_zh"], s["name_en"], s["year"],
                    s["region"], s["profession"],
                    s["coding_rule_json"], s["fee_structure_json"],
                    s["rounding_rule"], s["effective_date"],
                    s["description"], s["is_active"],
                ),
            )
            sid = cur.lastrowid
            std_id_map[s["code"]] = sid
            print(f"[INSERT] PricingStandard: {s['code']} (id={sid})")

    # ── Insert fee structure trees ────────────────────────────────────────────
    for std_code, nodes in FEE_TREES.items():
        sid = std_id_map[std_code]
        # Check if tree already seeded
        cur.execute("SELECT COUNT(*) FROM fee_structures WHERE pricing_standard_id = ?", (sid,))
        if cur.fetchone()[0] > 0:
            print(f"[SKIP] FeeStructure tree already seeded for {std_code}")
            continue

        # Build a map of fee_code → db_id after insert (for parent linking)
        code_to_id: dict[str, int] = {}
        for node in nodes:
            fee_code, name, formula, base_code, default_rate, is_competitive, is_leaf, sort_order, description, parent_code = node
            parent_id = code_to_id.get(parent_code) if parent_code else None
            cur.execute(
                """INSERT INTO fee_structures
                   (pricing_standard_id, parent_id, fee_code, name, formula,
                    base_code, default_rate, is_competitive, is_leaf, sort_order, description)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (sid, parent_id, fee_code, name, formula, base_code,
                 default_rate, is_competitive, is_leaf, sort_order, description),
            )
            code_to_id[fee_code] = cur.lastrowid
        print(f"[INSERT] FeeStructure tree for {std_code}: {len(nodes)} nodes")

    # ── Back-fill existing projects ───────────────────────────────────────────
    gb2013_id = std_id_map.get("GB50500-2013")
    if gb2013_id:
        cur.execute(
            "UPDATE projects SET pricing_standard_id = ? WHERE pricing_standard_id IS NULL",
            (gb2013_id,),
        )
        affected = cur.rowcount
        print(f"[BACKFILL] {affected} project(s) assigned to GB50500-2013 (id={gb2013_id})")

    conn.commit()
    conn.close()
    print("Done.")


if __name__ == "__main__":
    db = sys.argv[1] if len(sys.argv) > 1 else DB_PATH
    seed(db)
