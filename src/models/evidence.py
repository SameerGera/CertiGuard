from typing import Optional
from pydantic import BaseModel, Field


class ExtractedEntity(BaseModel):
    entity_type: str
    value: str
    normalized_value: Optional[str] = None
    bounding_box: Optional[list[int]] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class EvidenceSegment(BaseModel):
    segment_id: str
    file_name: str
    file_hash: str
    page_number: int = 1
    segment_text: str = ""
    extracted_entities: list[ExtractedEntity] = Field(default_factory=list)
    ocr_confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    extraction_method: str = "unknown"


class BidderEvidence(BaseModel):
    bidder_id: str
    bidder_name: str
    documents: list[dict] = Field(default_factory=list)
    evidence_segments: list[EvidenceSegment] = Field(default_factory=list)