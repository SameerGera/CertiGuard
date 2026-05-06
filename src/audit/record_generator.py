"""Audit record generation."""

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field


@dataclass
class HumanOverride:
    applied: bool
    officer_id: str
    override_verdict: str
    rationale: str
    signature: str
    timestamp: str


@dataclass
class AuditRecord:
    record_id: str
    timestamp: str
    tender_id: str
    criterion_id: str
    bidder_id: str
    ai_verdict: str
    ai_confidence: float
    verification_checks: List[Dict]
    yellow_flags: List[Dict] = field(default_factory=list)
    human_override: Optional[HumanOverride] = None
    merkle_hash: str = ""


class RecordGenerator:
    def create_record(
        self,
        tender_id: str,
        criterion_id: str,
        bidder_id: str,
        ai_verdict: str,
        ai_confidence: float,
        verification_checks: List[Dict],
        yellow_flags: Optional[List[Dict]] = None
    ) -> AuditRecord:

        record = AuditRecord(
            record_id=str(uuid.uuid4()),
            timestamp=datetime.utcnow().isoformat() + "Z",
            tender_id=tender_id,
            criterion_id=criterion_id,
            bidder_id=bidder_id,
            ai_verdict=ai_verdict,
            ai_confidence=ai_confidence,
            verification_checks=verification_checks,
            yellow_flags=yellow_flags or []
        )
        return record

    def apply_override(
        self,
        record: AuditRecord,
        officer_id: str,
        override_verdict: str,
        rationale: str,
        signature: str
    ) -> AuditRecord:

        record.human_override = HumanOverride(
            applied=True,
            officer_id=officer_id,
            override_verdict=override_verdict,
            rationale=rationale,
            signature=signature,
            timestamp=datetime.utcnow().isoformat() + "Z"
        )
        return record

    def to_dict(self, record: AuditRecord) -> Dict[str, Any]:
        data = {
            "record_id": record.record_id,
            "timestamp": record.timestamp,
            "tender_id": record.tender_id,
            "criterion_id": record.criterion_id,
            "bidder_id": record.bidder_id,
            "ai_verdict": record.ai_verdict,
            "ai_confidence": record.ai_confidence,
            "verification_checks": record.verification_checks,
            "yellow_flags": record.yellow_flags
        }
        if record.human_override:
            data["human_override"] = {
                "applied": True,
                "officer_id": record.human_override.officer_id,
                "override_verdict": record.human_override.override_verdict,
                "rationale": record.human_override.rationale,
                "signature": record.human_override.signature,
                "timestamp": record.human_override.timestamp
            }
        return data


record_generator = RecordGenerator()