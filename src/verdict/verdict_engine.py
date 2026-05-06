"""Verdict Engine - Decision matrix."""

from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum


class VerdictStatus(Enum):
    ELIGIBLE = "eligible"
    NOT_ELIGIBLE = "not_eligible"
    NEEDS_REVIEW = "needs_review"


class EvidenceStatus(Enum):
    FOUND_CLEAR = "found_clear"
    FOUND_UNCLEAR = "found_unclear"
    PARTIALLY_FOUND = "partially_found"
    NOT_FOUND = "not_found"
    MULTIPLE_CONFLICT = "multiple_conflict"


@dataclass
class VerificationCheck:
    """Individual verification check result."""
    check_name: str
    passed: bool
    detail: str


@dataclass
class CriterionVerdict:
    """Verdict for one criterion."""
    criterion_id: str
    status: VerdictStatus
    confidence: float
    reason: str
    checks: List[VerificationCheck]
    evidence_refs: List[str]


@dataclass
class BidderVerdict:
    """Overall verdict for a bidder."""
    bidder_id: str
    bidder_name: str
    criteria_results: List[CriterionVerdict]
    overall_status: VerdictStatus
    overall_confidence: float
    verdict_reason: str


class VerdictEngine:
    """Verdict matrix implementation.
    
    Evidence Status + Verification Result -> Verdict:
    - FOUND, CLEAR + ALL PASSED = ELIGIBLE
    - FOUND, CLEAR + ANY FAILED = NOT_ELIGIBLE
    - FOUND, UNCLEAR + ANY = NEEDS_REVIEW
    - PARTIALLY_FOUND + ANY = NEEDS_REVIEW
    - NOT_FOUND + MANDATORY = NOT_ELIGIBLE
    - NOT_FOUND + OPTIONAL = SKIP
    - MULTIPLE_CONFLICT + ANY = NEEDS_REVIEW
    
    Overall Bidder Verdict:
    - All mandatory ELIGIBLE = OVERALL ELIGIBLE
    - Any mandatory NOT_ELIGIBLE = OVERALL NOT_ELIGIBLE
    - No NOT_ELIGIBLE + at least one NEEDS_REVIEW = OVERALL NEEDS_REVIEW
    """
    
    def determine_criterion_verdict(
        self,
        evidence_status: EvidenceStatus,
        verification_passed: bool,
        has_yellow_flags: bool,
        criterion_nature: str,
        confidence: float
    ) -> CriterionVerdict:
        """Determine verdict for a single criterion."""
        
        if evidence_status == EvidenceStatus.FOUND_CLEAR:
            if verification_passed:
                return CriterionVerdict(
                    criterion_id="",
                    status=VerdictStatus.ELIGIBLE,
                    confidence=min(1.0, confidence),
                    reason="Valid evidence found and all checks passed",
                    checks=[],
                    evidence_refs=[]
                )
            else:
                return CriterionVerdict(
                    criterion_id="",
                    status=VerdictStatus.NOT_ELIGIBLE,
                    confidence=confidence,
                    reason="Verification failed",
                    checks=[],
                    evidence_refs=[]
                )
        
        elif evidence_status in [
            EvidenceStatus.FOUND_UNCLEAR,
            EvidenceStatus.PARTIALLY_FOUND
        ]:
            return CriterionVerdict(
                criterion_id="",
                status=VerdictStatus.NEEDS_REVIEW,
                confidence=confidence,
                reason="Evidence unclear or partial",
                checks=[],
                evidence_refs=[]
            )
        
        elif evidence_status == EvidenceStatus.NOT_FOUND:
            if criterion_nature == "MANDATORY":
                return CriterionVerdict(
                    criterion_id="",
                    status=VerdictStatus.NOT_ELIGIBLE,
                    confidence=1.0,
                    reason="Mandatory evidence not found",
                    checks=[],
                    evidence_refs=[]
                )
            else:
                return CriterionVerdict(
                    criterion_id="",
                    status=VerdictStatus.ELIGIBLE,
                    confidence=1.0,
                    reason="Optional criterion - evidence not required",
                    checks=[],
                    evidence_refs=[]
                )
        
        elif evidence_status == EvidenceStatus.MULTIPLE_CONFLICT:
            return CriterionVerdict(
                criterion_id="",
                status=VerdictStatus.NEEDS_REVIEW,
                confidence=confidence,
                reason="Conflicting evidence detected",
                checks=[],
                evidence_refs=[]
            )
        
        return CriterionVerdict(
            criterion_id="",
            status=VerdictStatus.NEEDS_REVIEW,
            confidence=confidence,
            reason="Unknown evidence status",
            checks=[],
            evidence_refs=[]
        )
    
    def determine_overall_verdict(
        self,
        criteria_results: List[CriterionVerdict],
        mandatory_ids: List[str]
    ) -> BidderVerdict:
        """Determine overall bidder verdict."""
        
        mandatory_results = [
            r for r in criteria_results
            if r.criterion_id in mandatory_ids
        ]
        
        if not mandatory_results:
            elligible_count = sum(
                1 for r in criteria_results
                if r.status == VerdictStatus.ELIGIBLE
            )
            not_eligible_count = sum(
                1 for r in criteria_results
                if r.status == VerdictStatus.NOT_ELIGIBLE
            )
            needs_review_count = sum(
                1 for r in criteria_results
                if r.status == VerdictStatus.NEEDS_REVIEW
            )
            
            if not_eligible_count > 0:
                return BidderVerdict(
                    bidder_id="",
                    bidder_name="",
                    criteria_results=criteria_results,
                    overall_status=VerdictStatus.NOT_ELIGIBLE,
                    overall_confidence=1.0,
                    verdict_reason=f"{not_eligible_count} criteria failed"
                )
            elif needs_review_count > 0:
                return BidderVerdict(
                    bidder_id="",
                    bidder_name="",
                    criteria_results=criteria_results,
                    overall_status=VerdictStatus.NEEDS_REVIEW,
                    overall_confidence=0.5,
                    verdict_reason=f"{needs_review_count} criteria need review"
                )
            else:
                return BidderVerdict(
                    bidder_id="",
                    bidder_name="",
                    criteria_results=criteria_results,
                    overall_status=VerdictStatus.ELIGIBLE,
                    overall_confidence=1.0,
                    verdict_reason="All criteria passed"
                )
        
        has_not_eligible = any(
            r.status == VerdictStatus.NOT_ELIGIBLE
            for r in mandatory_results
        )
        
        has_needs_review = any(
            r.status == VerdictStatus.NEEDS_REVIEW
            for r in mandatory_results
        )
        
        if has_not_eligible:
            return BidderVerdict(
                bidder_id="",
                bidder_name="",
                criteria_results=criteria_results,
                overall_status=VerdictStatus.NOT_ELIGIBLE,
                overall_confidence=1.0,
                verdict_reason="Mandatory criteria failed"
            )
        elif has_needs_review:
            return BidderVerdict(
                bidder_id="",
                bidder_name="",
                criteria_results=criteria_results,
                overall_status=VerdictStatus.NEEDS_REVIEW,
                overall_confidence=0.5,
                verdict_reason="Mandatory criteria need review"
            )
        else:
            return BidderVerdict(
                bidder_id="",
                bidder_name="",
                criteria_results=criteria_results,
                overall_status=VerdictStatus.ELIGIBLE,
                overall_confidence=1.0,
                verdict_reason="All mandatory criteria passed"
            )
    
    def apply_yellow_flags(
        self,
        verdict: CriterionVerdict,
        confidence_delta: float
    ) -> CriterionVerdict:
        """Apply confidence reduction from yellow flags."""
        if confidence_delta > 0:
            new_confidence = max(0.0, verdict.confidence - confidence_delta)
            
            if new_confidence < 0.7:
                return CriterionVerdict(
                    criterion_id=verdict.criterion_id,
                    status=VerdictStatus.NEEDS_REVIEW,
                    confidence=new_confidence,
                    reason=f"{verdict.reason} (confidence reduced by {confidence_delta:.2f})",
                    checks=verdict.checks,
                    evidence_refs=verdict.evidence_refs
                )
        
        return verdict
    
    def evaluate_bidder(
        self,
        bidder_id: str,
        bidder_name: str,
        evidence_data: Dict[str, Any]
    ) -> BidderVerdict:
        """Evaluate a bidder.
        
        Args:
            bidder_id: Bidder ID
            bidder_name: Bidder name
            evidence_data: Evidence and verification results
            
        Returns:
            BidderVerdict
        """
        criteria_results = []
        
        for criterion_id, data in evidence_data.get("criteria", {}).items():
            evidence_status = data.get("evidence_status", EvidenceStatus.NOT_FOUND)
            verification_passed = data.get("verification_passed", False)
            has_yellow_flags = data.get("has_yellow_flags", False)
            criterion_nature = data.get("nature", "MANDATORY")
            confidence = data.get("confidence", 0.5)
            
            result = self.determine_criterion_verdict(
                evidence_status=evidence_status,
                verification_passed=verification_passed,
                has_yellow_flags=has_yellow_flags,
                criterion_nature=criterion_nature,
                confidence=confidence
            )
            result.criterion_id = criterion_id
            criteria_results.append(result)
        
        mandatory_ids = [
            c["id"] for c in evidence_data.get("mandatory_criteria", [])
        ]
        
        return self.determine_overall_verdict(criteria_results, mandatory_ids)


verdict_engine = VerdictEngine()