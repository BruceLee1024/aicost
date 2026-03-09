"""Seed standard BOQ codes from GB50500 into the database."""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.db.session import SessionLocal
from app.models.boq_standard_code import BoqStandardCode

STANDARD_CODES = [
    # ── A 土石方工程 ──
    {"standard_code": "010101001", "name": "平整场地", "standard_unit": "m²", "division": "土石方工程", "chapter": "A.1",
     "measurement_rule": "按设计图示尺寸以建筑物首层面积计算", "common_characteristics": "1.土壤类别\n2.弃土运距"},
    {"standard_code": "010101002", "name": "挖一般土方", "standard_unit": "m³", "division": "土石方工程", "chapter": "A.1",
     "measurement_rule": "按设计图示尺寸以体积计算", "common_characteristics": "1.土壤类别\n2.挖土深度\n3.弃土运距"},
    {"standard_code": "010101003", "name": "挖沟槽土方", "standard_unit": "m³", "division": "土石方工程", "chapter": "A.1",
     "measurement_rule": "按设计图示尺寸以沟槽长度乘以沟槽断面积计算", "common_characteristics": "1.土壤类别\n2.挖土深度\n3.沟槽宽度"},
    {"standard_code": "010101004", "name": "挖基坑土方", "standard_unit": "m³", "division": "土石方工程", "chapter": "A.1",
     "measurement_rule": "按设计图示尺寸以体积计算", "common_characteristics": "1.土壤类别\n2.挖土深度\n3.基坑底面积"},
    {"standard_code": "010102001", "name": "回填方", "standard_unit": "m³", "division": "土石方工程", "chapter": "A.1",
     "measurement_rule": "按设计图示尺寸以体积计算", "common_characteristics": "1.填方材料种类\n2.密实度要求\n3.运距"},
    # ── A 地基处理与桩基 ──
    {"standard_code": "010201001", "name": "预制钢筋混凝土方桩", "standard_unit": "m", "division": "地基处理与桩基", "chapter": "A.2",
     "measurement_rule": "按设计图示尺寸以桩长计算", "common_characteristics": "1.桩截面尺寸\n2.混凝土强度等级\n3.送桩深度"},
    {"standard_code": "010201002", "name": "预制钢筋混凝土管桩", "standard_unit": "m", "division": "地基处理与桩基", "chapter": "A.2",
     "measurement_rule": "按设计图示尺寸以桩长计算", "common_characteristics": "1.桩径\n2.壁厚\n3.混凝土强度等级"},
    # ── A 砌筑 ──
    {"standard_code": "010301001", "name": "砖基础", "standard_unit": "m³", "division": "砌筑工程", "chapter": "A.3",
     "measurement_rule": "按设计图示尺寸以体积计算", "common_characteristics": "1.砖品种、规格\n2.砂浆强度等级"},
    {"standard_code": "010302001", "name": "砖墙", "standard_unit": "m³", "division": "砌筑工程", "chapter": "A.3",
     "measurement_rule": "按设计图示尺寸以体积计算，扣除门窗洞口等", "common_characteristics": "1.墙体厚度\n2.砖品种规格\n3.砂浆强度等级"},
    {"standard_code": "010303001", "name": "砌块墙", "standard_unit": "m³", "division": "砌筑工程", "chapter": "A.3",
     "measurement_rule": "按设计图示尺寸以体积计算", "common_characteristics": "1.砌块品种规格\n2.墙体厚度\n3.砂浆强度等级"},
    # ── A 混凝土及钢筋混凝土 ──
    {"standard_code": "010401001", "name": "现浇混凝土基础", "standard_unit": "m³", "division": "混凝土及钢筋混凝土工程", "chapter": "A.4",
     "measurement_rule": "按设计图示尺寸以体积计算，不扣除构件内钢筋、预埋件所占体积",
     "common_characteristics": "1.混凝土强度等级\n2.基础类型（独立/条形/筏板）\n3.垫层"},
    {"standard_code": "010402001", "name": "现浇混凝土柱", "standard_unit": "m³", "division": "混凝土及钢筋混凝土工程", "chapter": "A.4",
     "measurement_rule": "按设计图示尺寸以体积计算", "common_characteristics": "1.混凝土强度等级\n2.柱截面尺寸\n3.柱高"},
    {"standard_code": "010403001", "name": "现浇混凝土梁", "standard_unit": "m³", "division": "混凝土及钢筋混凝土工程", "chapter": "A.4",
     "measurement_rule": "按设计图示尺寸以体积计算", "common_characteristics": "1.混凝土强度等级\n2.梁截面尺寸\n3.梁跨度"},
    {"standard_code": "010404001", "name": "现浇混凝土墙", "standard_unit": "m³", "division": "混凝土及钢筋混凝土工程", "chapter": "A.4",
     "measurement_rule": "按设计图示尺寸以体积计算", "common_characteristics": "1.混凝土强度等级\n2.墙厚\n3.墙高"},
    {"standard_code": "010405001", "name": "现浇混凝土板", "standard_unit": "m³", "division": "混凝土及钢筋混凝土工程", "chapter": "A.4",
     "measurement_rule": "按设计图示尺寸以体积计算", "common_characteristics": "1.混凝土强度等级\n2.板厚\n3.板类型（有梁板/平板）"},
    {"standard_code": "010406001", "name": "现浇混凝土楼梯", "standard_unit": "m³", "division": "混凝土及钢筋混凝土工程", "chapter": "A.4",
     "measurement_rule": "按设计图示尺寸以体积计算，含休息平台", "common_characteristics": "1.混凝土强度等级\n2.梯段宽度\n3.踏步数量"},
    {"standard_code": "010407001", "name": "钢筋工程", "standard_unit": "t", "division": "混凝土及钢筋混凝土工程", "chapter": "A.4",
     "measurement_rule": "按设计图示钢筋长度乘以单位理论质量计算", "common_characteristics": "1.钢筋种类（HPB/HRB）\n2.规格（直径）\n3.连接方式"},
    {"standard_code": "010408001", "name": "模板工程", "standard_unit": "m²", "division": "混凝土及钢筋混凝土工程", "chapter": "A.4",
     "measurement_rule": "按混凝土与模板的接触面积计算", "common_characteristics": "1.模板材质\n2.支撑高度\n3.构件类型"},
    # ── A 金属结构 ──
    {"standard_code": "010501001", "name": "钢柱", "standard_unit": "t", "division": "金属结构工程", "chapter": "A.5",
     "measurement_rule": "按设计图示尺寸以质量计算", "common_characteristics": "1.钢材品种\n2.柱截面形式\n3.连接方式"},
    # ── A 屋面及防水 ──
    {"standard_code": "010601001", "name": "屋面防水", "standard_unit": "m²", "division": "屋面及防水工程", "chapter": "A.6",
     "measurement_rule": "按设计图示尺寸以面积计算", "common_characteristics": "1.防水材料种类\n2.厚度/层数\n3.基层处理"},
    # ── B 装饰装修 ──
    {"standard_code": "020101001", "name": "天棚抹灰", "standard_unit": "m²", "division": "楼地面装饰工程", "chapter": "B.1",
     "measurement_rule": "按设计图示尺寸以面积计算", "common_characteristics": "1.砂浆种类\n2.抹灰厚度"},
    {"standard_code": "020201001", "name": "地面找平层", "standard_unit": "m²", "division": "楼地面装饰工程", "chapter": "B.2",
     "measurement_rule": "按设计图示尺寸以面积计算", "common_characteristics": "1.找平材料\n2.找平厚度"},
    {"standard_code": "020202001", "name": "块料楼地面", "standard_unit": "m²", "division": "楼地面装饰工程", "chapter": "B.2",
     "measurement_rule": "按设计图示尺寸以面积计算", "common_characteristics": "1.块料品种规格\n2.铺贴方式\n3.勾缝材料"},
    {"standard_code": "020301001", "name": "内墙面抹灰", "standard_unit": "m²", "division": "墙柱面装饰工程", "chapter": "B.3",
     "measurement_rule": "按设计图示尺寸以面积计算，扣除门窗洞口面积", "common_characteristics": "1.砂浆种类强度等级\n2.抹灰厚度"},
    {"standard_code": "020401001", "name": "涂料", "standard_unit": "m²", "division": "涂料油漆裱糊工程", "chapter": "B.4",
     "measurement_rule": "按设计图示尺寸以面积计算", "common_characteristics": "1.涂料种类\n2.涂刷遍数\n3.基层处理"},
    # ── C 安装工程 ──
    {"standard_code": "030101001", "name": "给水管道", "standard_unit": "m", "division": "给排水工程", "chapter": "C.1",
     "measurement_rule": "按设计图示管道中心线长度以延长米计算", "common_characteristics": "1.管材种类\n2.管径\n3.连接方式"},
    {"standard_code": "030102001", "name": "排水管道", "standard_unit": "m", "division": "给排水工程", "chapter": "C.1",
     "measurement_rule": "按设计图示管道中心线长度以延长米计算", "common_characteristics": "1.管材种类\n2.管径\n3.连接方式"},
    {"standard_code": "030201001", "name": "电缆敷设", "standard_unit": "m", "division": "电气工程", "chapter": "C.2",
     "measurement_rule": "按设计图示以延长米计算", "common_characteristics": "1.电缆型号规格\n2.敷设方式"},
    {"standard_code": "030202001", "name": "配电箱安装", "standard_unit": "台", "division": "电气工程", "chapter": "C.2",
     "measurement_rule": "按设计图示数量计算", "common_characteristics": "1.配电箱类型\n2.安装方式\n3.回路数"},
]


def seed():
    db = SessionLocal()
    try:
        existing = {row.standard_code for row in db.query(BoqStandardCode).all()}
        added = 0
        for item in STANDARD_CODES:
            if item["standard_code"] in existing:
                continue
            db.add(BoqStandardCode(**item))
            added += 1
        db.commit()
        print(f"Seeded {added} standard BOQ codes ({len(existing)} already existed).")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
