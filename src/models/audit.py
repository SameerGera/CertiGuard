from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class AuditRecord(BaseModel):
    record_id: str
    timestamp: datetime = Field(default_factory=datetime.now)
    tender_id: str
    criterion_id: str
    bidder_id: str
    ai_verdict: str = ""
    ai_confidence: float = 0.0
    human_override: Optional[dict] = None
    merkle_hash: str = ""
    evidence_refs: list[str] = Field(default_factory=list)