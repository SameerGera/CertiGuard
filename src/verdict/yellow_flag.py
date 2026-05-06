"""Yellow Flag Protocol - Decision tree for manual review triggers."""

from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum


class YellowFlagTrigger(Enum):
    LOW_EXTRACTION_CONFIDENCE = "low_extraction_confidence"
    HIGH_OCR_ERROR = "high_ocr_error"
    MISSING_MANDATORY_FIELD = "missing_mandatory_field"
    CROSS_DOCUMENT_CONFLICT = "cross_document_conflict"
    TAMPER_INDICATOR = "tamper_indicator"
    QUALITATIVE_CLAIM = "qualitative_claim"
    HANDWRITTEN_DETECTED = "handwritten_detected"
    EXPIRING_SOON = "expiring_soon"
    UNKNOWN_AUTHORITY = "unknown_authority"
    NAME_MISMATCH = "name_mismatch"
    UNIT_MISMATCH = "unit_mismatch"
    EXPIRED_CERTIFICATE = "expired_certificate"


@dataclass
class YellowFlag:
    """Yellow flag instance."""
    trigger: YellowFlagTrigger
    reason: str
    affected_entity: str
    confidence_delta: float
    severity: str = "medium"


@dataclass
class YellowFlagResult:
    """Result of yellow flag analysis."""
    raised: bool
    flags: List[YellowFlag]
    total_delta: float


class YellowFlagGenerator:
    """Yellow flag decision tree.
    
    9 triggers that cause NEEDS_REVIEW verdict:
    1. Extraction confidence < 0.70
    2. OCR word error rate > 0.15
    3. Missing mandatory entity field
    4. Cross-document value conflict
    5. Tamper indicator detected
    6. Qualitative claim (not numeric)
    7. Handwritten content (conf < 0.60)
    8. Expiry within 30 days
    9. Unknown issuing authority
    """
    
    CONFIDENCE_THRESHOLD = 0.70
    OCR_ERROR_THRESHOLD = 0.15
    HANDWRITTEN_CONFIDENCE_THRESHOLD = 0.60
    EXPIRY_GRACE_DAYS = 30
    
    def check_extraction_confidence(
        self,
        confidence: float
    ) -> Optional[YellowFlag]:
        """Trigger: Low extraction confidence."""
        if confidence < self.CONFIDENCE_THRESHOLD:
            return YellowFlag(
                trigger=YellowFlagTrigger.LOW_EXTRACTION_CONFIDENCE,
                reason=f"Extraction confidence {confidence:.2f} < {self.CONFIDENCE_THRESHOLD}",
                affected_entity="extraction",
                confidence_delta=self.CONFIDENCE_THRESHOLD - confidence,
                severity="high" if confidence < 0.5 else "medium"
            )
        return None
    
    def check_ocr_error_rate(
        self,
        error_rate: float
    ) -> Optional[YellowFlag]:
        """Trigger: High OCR error rate."""
        if error_rate > self.OCR_ERROR_THRESHOLD:
            return YellowFlag(
                trigger=YellowFlagTrigger.HIGH_OCR_ERROR,
                reason=f"OCR error rate {error_rate:.2f} > {self.OCR_ERROR_THRESHOLD}",
                affected_entity="ocr",
                confidence_delta=min(0.3, error_rate - self.OCR_ERROR_THRESHOLD),
                severity="high" if error_rate > 0.25 else "medium"
            )
        return None
    
    def check_missing_field(
        self,
        field_name: str,
        is_mandatory: bool
    ) -> Optional[YellowFlag]:
        """Trigger: Missing mandatory field."""
        if is_mandatory:
            return YellowFlag(
                trigger=YellowFlagTrigger.MISSING_MANDATORY_FIELD,
                reason=f"Missing mandatory field: {field_name}",
                affected_entity=field_name,
                confidence_delta=0.3,
                severity="high"
            )
        return None
    
    def check_cross_document_conflict(
        self,
        entity_type: str,
        values: List[str]
    ) -> Optional[YellowFlag]:
        """Trigger: Conflicting values across documents."""
        unique = set(values)
        if len(unique) > 1:
            return YellowFlag(
                trigger=YellowFlagTrigger.CROSS_DOCUMENT_CONFLICT,
                reason=f"{entity_type} has conflicting values: {list(unique)}",
                affected_entity=entity_type,
                confidence_delta=0.2,
                severity="medium"
            )
        return None
    
    def check_tamper(
        self,
        status: str
    ) -> Optional[YellowFlag]:
        """Trigger: Tamper indicator detected."""
        if status in ["suspicious", "tampered"]:
            return YellowFlag(
                trigger=YellowFlagTrigger.TAMPER_INDICATOR,
                reason=f"Tamper status: {status}",
                affected_entity="document_integrity",
                confidence_delta=0.4,
                severity="high"
            )
        return None
    
    def check_qualitative_claim(
        self,
        claim_type: str
    ) -> Optional[YellowFlag]:
        """Trigger: Qualitative claim instead of numeric."""
        if claim_type in ["qualitative_claim", "approximate", "range"]:
            return YellowFlag(
                trigger=YellowFlagTrigger.QUALITATIVE_CLAIM,
                reason=f"Qualitative claim: {claim_type}",
                affected_entity="value_extraction",
                confidence_delta=0.2,
                severity="medium"
            )
        return None
    
    def check_handwritten(
        self,
        confidence: float
    ) -> Optional[YellowFlag]:
        """Trigger: Handwritten content with low confidence."""
        if confidence < self.HANDWRITTEN_CONFIDENCE_THRESHOLD:
            return YellowFlag(
                trigger=YellowFlagTrigger.HANDWRITTEN_DETECTED,
                reason=f"Handwritten confidence {confidence:.2f} < {self.HANDWRITTEN_CONFIDENCE_THRESHOLD}",
                affected_entity="document_content",
                confidence_delta=self.HANDWRITTEN_CONFIDENCE_THRESHOLD - confidence,
                severity="high"
            )
        return None
    
    def check_expiring_soon(
        self,
        days_until_expiry: int
    ) -> Optional[YellowFlag]:
        """Trigger: Certificate expiring soon."""
        if 0 <= days_until_expiry <= self.EXPIRY_GRACE_DAYS:
            return YellowFlag(
                trigger=YellowFlagTrigger.EXPIRING_SOON,
                reason=f"Expires in {days_until_expiry} days (within {self.EXPIRY_GRACE_DAYS} day grace)",
                affected_entity="certificate_expiry",
                confidence_delta=0.1,
                severity="medium"
            )
        return None
    
    def check_expired(
        self,
        days_since_expiry: int
    ) -> Optional[YellowFlag]:
        """Trigger: Certificate expired."""
        if days_since_expiry > 0:
            return YellowFlag(
                trigger=YellowFlagTrigger.EXPIRED_CERTIFICATE,
                reason=f"Certificate expired {days_since_expiry} days ago",
                affected_entity="certificate_expiry",
                confidence_delta=0.5,
                severity="high"
            )
        return None
    
    def check_unknown_authority(
        self,
        authority_name: str
    ) -> Optional[YellowFlag]:
        """Trigger: Unknown issuing authority."""
        if authority_name:
            return YellowFlag(
                trigger=YellowFlagTrigger.UNKNOWN_AUTHORITY,
                reason=f"Unknown authority: {authority_name}",
                affected_entity="certifying_body",
                confidence_delta=0.2,
                severity="medium"
            )
        return None
    
    def check_name_mismatch(
        self,
        match_score: float
    ) -> Optional[YellowFlag]:
        """Trigger: Name mismatch but partial match."""
        if match_score < 0.80 and match_score > 0.5:
            return YellowFlag(
                trigger=YellowFlagTrigger.NAME_MISMATCH,
                reason=f"Name match score {match_score:.2f} suggests partial match",
                affected_entity="company_name",
                confidence_delta=0.2,
                severity="medium"
            )
        return None
    
    def analyze(
        self,
        verification_results: Dict[str, Any]
    ) -> YellowFlagResult:
        """Run full yellow flag analysis.
        
        Args:
            verification_results: Dict of verification results
            
        Returns:
            YellowFlagResult with all flags
        """
        flags = []
        
        if "extraction_confidence" in verification_results:
            flag = self.check_extraction_confidence(
                verification_results["extraction_confidence"]
            )
            if flag:
                flags.append(flag)
        
        if "ocr_error_rate" in verification_results:
            flag = self.check_ocr_error_rate(
                verification_results["ocr_error_rate"]
            )
            if flag:
                flags.append(flag)
        
        if "missing_mandatory_field" in verification_results:
            flag = self.check_missing_field(
                verification_results["missing_mandatory_field"],
                True
            )
            if flag:
                flags.append(flag)
        
        if "cross_document_values" in verification_results:
            vals = verification_results["cross_document_values"]
            if isinstance(vals, dict):
                for entity_type, values in vals.items():
                    flag = self.check_cross_document_conflict(entity_type, values)
                    if flag:
                        flags.append(flag)
        
        if "tamper_status" in verification_results:
            flag = self.check_tamper(verification_results["tamper_status"])
            if flag:
                flags.append(flag)
        
        if "claim_type" in verification_results:
            flag = self.check_qualitative_claim(verification_results["claim_type"])
            if flag:
                flags.append(flag)
        
        if " handwritten_confidence" in verification_results:
            flag = self.check_handwritten(
                verification_results[" handwritten_confidence"]
            )
            if flag:
                flags.append(flag)
        
        if "days_until_expiry" in verification_results:
            flag = self.check_expiring_soon(
                verification_results["days_until_expiry"]
            )
            if flag:
                flags.append(flag)
        
        if "authority_name" in verification_results:
            flag = self.check_unknown_authority(
                verification_results["authority_name"]
            )
            if flag:
                flags.append(flag)
        
        total_delta = sum(f.confidence_delta for f in flags)
        
        return YellowFlagResult(
            raised=len(flags) > 0,
            flags=flags,
            total_delta=total_delta
        )


yellow_flag_generator = YellowFlagGenerator()