from __future__ import annotations
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


# ─── Enums ───────────────────────────────────────────────────────────────────

class SchemaType(str, Enum):
    EMVCO = "emvco"           # classic card transaction dataset
    EMVCO_3DS = "emvco_3ds"   # 3-D Secure / money-laundering dataset


class RuleSeverity(str, Enum):
    HIGH   = "high"
    MEDIUM = "medium"
    LOW    = "low"


class RuleCategory(str, Enum):
    VELOCITY       = "velocity"
    AMOUNT         = "amount"
    DEVICE         = "device"
    GEOGRAPHY      = "geography"
    AUTHENTICATION = "authentication"
    BEHAVIORAL     = "behavioral"
    ACCOUNT        = "account"
    MERCHANT       = "merchant"


class OperatorType(str, Enum):
    GT  = "gt"    # >
    GTE = "gte"   # >=
    LT  = "lt"    # <
    LTE = "lte"   # <=
    EQ  = "eq"    # ==
    NEQ = "neq"   # !=
    IN  = "in"
    NOT_IN = "not_in"
    CONTAINS = "contains"


class RuleMode(str, Enum):
    NORMAL   = "normal"    # derive rules purely from user prompt
    ASSISTED = "assisted"  # use blueprint + prompt


# ─── Rule Models ─────────────────────────────────────────────────────────────

class RuleCondition(BaseModel):
    """Single atomic condition evaluated against a dataset column."""
    field: str
    operator: OperatorType
    value: Any
    description: str = ""


class FraudRule(BaseModel):
    id: str                                        # e.g. "R001"
    name: str
    description: str
    category: RuleCategory
    severity: RuleSeverity
    logic_expression: str                          # human-readable, e.g. "velocity_24h > 10"
    conditions: list[RuleCondition] = Field(default_factory=list)
    # if True the rule fires when ANY condition matches (OR); else ALL (AND)
    match_any: bool = False
    tags: list[str] = Field(default_factory=list)


# ─── Request models ──────────────────────────────────────────────────────────

class GenerateRulesRequest(BaseModel):
    scenario: str = Field(..., description="Fraud scenario name or free-text description")
    mode: RuleMode = RuleMode.NORMAL
    blueprint: Optional[dict] = Field(None, description="Blueprint JSON (assisted mode only)")
    schema_type: Optional[SchemaType] = None     # auto-detected if omitted
    available_columns: list[str] = Field(default_factory=list)
    num_rules: int = Field(10, ge=3, le=25)


class EvaluateRequest(BaseModel):
    rules: list[FraudRule]
    selected_rule_ids: Optional[list[str]] = None  # None → evaluate all


# ─── Response models ─────────────────────────────────────────────────────────

class GenerateRulesResponse(BaseModel):
    model_config = {"protected_namespaces": ()}

    scenario_summary: str
    schema_type: SchemaType
    rules: list[FraudRule]
    model_used: str


class RuleResult(BaseModel):
    rule_id: str
    rule_name: str
    severity: RuleSeverity
    category: RuleCategory
    flagged_count: int
    flag_rate: float           # fraction 0–1
    true_positive_count: int   # flagged AND fraud_label == 1
    false_positive_count: int  # flagged AND fraud_label == 0
    precision: float
    recall: float
    f1: float
    logic_expression: str
    sample_flagged_ids: list[str] = Field(default_factory=list)


class DatasetSummary(BaseModel):
    total_rows: int
    fraud_rows: int
    non_fraud_rows: int
    fraud_rate: float
    schema_type: SchemaType
    columns: list[str]
    missing_value_counts: dict[str, int]


class EvaluationMetrics(BaseModel):
    total_records: int
    total_flagged: int          # union across all rules
    overall_flag_rate: float
    fraud_captured: int         # fraud rows caught by at least one rule
    overall_precision: float
    overall_recall: float
    overall_f1: float
    rule_results: list[RuleResult]
    dataset_summary: DatasetSummary
    flagged_sample: list[dict]  # up to 20 sample flagged rows


class UploadResponse(BaseModel):
    session_id: str
    filename: str
    rows: int
    schema_type: SchemaType
    columns: list[str]
    dataset_summary: DatasetSummary
