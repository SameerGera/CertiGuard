from datetime import date
from typing import Optional
from pydantic import BaseModel, Field

from src.models.criterion import Criterion
from src.models.evidence import BidderEvidence


class CriterionOutput(BaseModel):
    id: str
    label: str
    nature: str
    type: str
    canonical_entities: list[str] = Field(default_factory=list)
    threshold: Optional[dict] = None
    aggregation: str = "SINGLE"
    temporal_scope: Optional[str] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    raw_text: str = ""
    source_page: int = 0


class MLOutput(BaseModel):
    tender_id: str
    tender_name: str
    submission_deadline: Optional[date] = None
    criteria: list[CriterionOutput] = Field(default_factory=list)
    bidder_evidence: list[BidderEvidence] = Field(default_factory=list)
    processing_metadata: dict = Field(default_factory=dict)

    @classmethod
    def from_criteria_and_evidence(
        cls,
        tender_id: str,
        tender_name: str,
        criteria: list[Criterion],
        bidder_evidence: list[BidderEvidence],
        submission_deadline: Optional[date] = None,
        processing_metadata: Optional[dict] = None,
    ) -> "MLOutput":
        criterion_outputs = []
        for c in criteria:
            threshold = None
            if c.threshold:
                threshold = {
                    "value": c.threshold.value,
                    "unit": c.threshold.unit,
                    "operator": c.threshold.operator,
                }
            criterion_outputs.append(
                CriterionOutput(
                    id=c.id,
                    label=c.label,
                    nature=c.nature.value if hasattr(c.nature, "value") else c.nature,
                    type=c.type.value if hasattr(c.type, "value") else c.type,
                    canonical_entities=c.canonical_entities,
                    threshold=threshold,
                    aggregation=(
                        c.aggregation.value
                        if hasattr(c.aggregation, "value")
                        else c.aggregation
                    ),
                    temporal_scope=c.temporal_scope,
                    confidence=c.confidence,
                    raw_text=c.raw_text,
                    source_page=c.source_page,
                )
            )

        return cls(
            tender_id=tender_id,
            tender_name=tender_name,
            submission_deadline=submission_deadline,
            criteria=criterion_outputs,
            bidder_evidence=bidder_evidence,
            processing_metadata=processing_metadata or {},
        )