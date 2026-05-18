from pydantic import BaseModel


class BoqItemOut(BaseModel):
    id: int
    project_id: int
    code: str
    name: str
    characteristics: str = ""
    unit: str
    quantity: float
    division: str = ""
    sort_order: int = 0
    item_ref: str = ""
    trade_section: str = ""
    description_en: str = ""
    rate: float = 0
    amount: float = 0
    remark: str = ""
    code_segments_json: str = "{}"
    feature_json: str = "[]"
    calc_rule: str = ""
    work_content: str = ""
    is_provisional: int = 0
    pricing_standard_id: int | None = None


class BoqItemCreate(BaseModel):
    code: str
    name: str
    characteristics: str = ""
    unit: str
    quantity: float
    division: str = ""
    sort_order: int = 0
    item_ref: str = ""
    trade_section: str = ""
    description_en: str = ""
    rate: float = 0
    remark: str = ""
    feature_json: str = ""
    work_content: str = ""
    is_provisional: int = 0
    pricing_standard_id: int | None = None


class BoqItemUpdate(BaseModel):
    name: str | None = None
    characteristics: str | None = None
    unit: str | None = None
    quantity: float | None = None
    division: str | None = None
    sort_order: int | None = None
    item_ref: str | None = None
    trade_section: str | None = None
    description_en: str | None = None
    rate: float | None = None
    remark: str | None = None
    feature_json: str | None = None
    work_content: str | None = None
    is_provisional: int | None = None
    pricing_standard_id: int | None = None
    code: str | None = None


class BoqImportResult(BaseModel):
    imported: int
    skipped: int
    items: list[BoqItemOut]
