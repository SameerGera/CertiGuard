from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class CriterionNature(str, Enum):
    MANDATORY = "MANDATORY"
    OPTIONAL = "OPTIONAL"
    DESIRABLE = "DESIRABLE"


class CriterionType(str, Enum):
    FINANCIAL = "FINANCIAL"
    CERTIFICATION = "CERTIFICATION"
    EXPERIENCE = "EXPERIENCE"
    LEGAL = "LEGAL"
    TECHNICAL = "TECHNICAL"


class AggregationMode(str, Enum):
    SINGLE = "SINGLE"
    AVERAGE_LAST_3_FY = "AVERAGE_LAST_3_FY"
    AVERAGE_LAST_5_FY = "AVERAGE_LAST_5_FY"
    COUNT = "COUNT"
    SUM = "SUM"


class CriterionThreshold(BaseModel):
    value: float
    unit: str = "INR"
    operator: str = ">="


class Criterion(BaseModel):
    id: str
    label: str
    nature: CriterionNature
    type: CriterionType
    canonical_entities: list[str] = Field(default_factory=list)
    threshold: Optional[CriterionThreshold] = None
    aggregation: AggregationMode = AggregationMode.SINGLE
    temporal_scope: Optional[str] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    raw_text: str = ""
    source_page: int = 0