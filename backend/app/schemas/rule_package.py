from pydantic import BaseModel


class RulePackageCreate(BaseModel):
    name: str
    region: str = ""
    management_rate: float = 0.08
    profit_rate: float = 0.05
    regulatory_rate: float = 0.03
    tax_rate: float = 0.09
    rounding_rule: str = "ROUND_HALF_UP"
    version: str = "1.0"


class RulePackageOut(BaseModel):
    id: int
    name: str
    region: str
    management_rate: float
    profit_rate: float
    regulatory_rate: float
    tax_rate: float
    rounding_rule: str
    version: str


class RulePackageBindRequest(BaseModel):
    rule_package_id: int
