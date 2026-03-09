"""Service for parsing Excel BOQ files and persisting to DB."""

from __future__ import annotations

import io
from dataclasses import dataclass

import openpyxl
from sqlalchemy.orm import Session

from app.models.boq_item import BoqItem


# ---------------------------------------------------------------------------
# Column mapping – tries to match common Chinese / English header variants
# ---------------------------------------------------------------------------

_HEADER_MAP: dict[str, str] = {
    # code
    "编码": "code", "编号": "code", "code": "code", "项目编码": "code",
    # name
    "名称": "name", "项目名称": "name", "name": "name",
    # unit
    "单位": "unit", "计量单位": "unit", "unit": "unit",
    # quantity
    "工程量": "quantity", "数量": "quantity", "quantity": "quantity", "qty": "quantity",
    # characteristics
    "项目特征": "characteristics", "特征": "characteristics", "characteristics": "characteristics", "项目特征描述": "characteristics",
    # HK format headers
    "ref": "item_ref", "item ref": "item_ref", "reference": "item_ref", "参考号": "item_ref",
    "trade": "trade_section", "trade section": "trade_section", "工种": "trade_section",
    "description": "description_en", "description (en)": "description_en", "英文描述": "description_en",
    "rate": "rate", "单价": "rate", "unit rate": "rate",
    "amount": "amount", "金额": "amount",
    "remark": "remark", "remarks": "remark", "备注": "remark",
    "分部": "division", "division": "division",
}


@dataclass
class ImportStats:
    imported: int
    skipped: int
    items: list[BoqItem]


def _normalize(header: str) -> str | None:
    """Try to map a raw header string to a known field name."""
    h = header.strip().lower()
    return _HEADER_MAP.get(h)


def parse_and_import(
    file_bytes: bytes,
    project_id: int,
    db: Session,
) -> ImportStats:
    """Parse an .xlsx byte stream and insert rows into boq_items.

    Returns a summary of what was imported / skipped.
    """
    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
    ws = wb.active
    if ws is None:
        return ImportStats(imported=0, skipped=0, items=[])

    rows = list(ws.iter_rows(values_only=True))
    if len(rows) < 2:
        return ImportStats(imported=0, skipped=0, items=[])

    # --- Discover column mapping from header row --------------------------
    raw_headers = rows[0]
    col_map: dict[int, str] = {}
    for idx, cell in enumerate(raw_headers):
        if cell is None:
            continue
        field = _normalize(str(cell))
        if field:
            col_map[idx] = field

    found = set(col_map.values())

    # Detect if this is a HK-format file
    is_hk_format = "item_ref" in found or "trade_section" in found or "description_en" in found

    # For HK format, item_ref or trade can serve as "code"
    if is_hk_format:
        required = {"unit"}  # More lenient — we can derive code from item_ref
        if not ("name" in found or "description_en" in found):
            return ImportStats(imported=0, skipped=len(rows) - 1, items=[])
    else:
        required = {"code", "name", "unit"}

    if not required.issubset(found):
        return ImportStats(imported=0, skipped=len(rows) - 1, items=[])

    # --- Parse data rows --------------------------------------------------
    imported_items: list[BoqItem] = []
    skipped = 0
    for row in rows[1:]:
        record: dict[str, str | float] = {}
        for idx, field in col_map.items():
            val = row[idx] if idx < len(row) else None
            if val is not None:
                record[field] = val

        # Minimal validation
        code = str(record.get("code", "")).strip()
        name = str(record.get("name", "")).strip()
        unit = str(record.get("unit", "")).strip()

        # HK format: derive code from item_ref, name from description_en
        item_ref = str(record.get("item_ref", "")).strip()
        trade_section = str(record.get("trade_section", "")).strip()
        description_en = str(record.get("description_en", "")).strip()

        if is_hk_format:
            if not code and item_ref:
                code = item_ref
            if not name and description_en:
                name = description_en
            if not name:
                skipped += 1
                continue
        else:
            if not code or not name or not unit:
                skipped += 1
                continue

        try:
            quantity = float(record.get("quantity", 0))
        except (ValueError, TypeError):
            quantity = 0.0

        try:
            rate = float(record.get("rate", 0))
        except (ValueError, TypeError):
            rate = 0.0

        try:
            amount = float(record.get("amount", 0))
        except (ValueError, TypeError):
            amount = rate * quantity if rate else 0.0

        characteristics = str(record.get("characteristics", "")).strip()
        remark = str(record.get("remark", "")).strip()
        division = str(record.get("division", "")).strip() or trade_section

        item = BoqItem(
            project_id=project_id,
            code=code,
            name=name,
            unit=unit,
            quantity=quantity,
            characteristics=characteristics,
            item_ref=item_ref,
            trade_section=trade_section,
            description_en=description_en,
            rate=rate,
            amount=amount or (rate * quantity),
            remark=remark,
            division=division,
        )
        db.add(item)
        imported_items.append(item)

    db.commit()
    for item in imported_items:
        db.refresh(item)

    wb.close()
    return ImportStats(imported=len(imported_items), skipped=skipped, items=imported_items)
