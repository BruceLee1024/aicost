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


class BoqImportResult(BaseModel):
    imported: int
    skipped: int
    items: list[BoqItemOut]
