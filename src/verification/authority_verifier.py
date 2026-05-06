"""Authority Verifier - Cross-check certifying bodies against registry."""

import json
import os
from typing import Optional, List, Dict
from dataclasses import dataclass
from enum import Enum


class AuthorityStatus(Enum):
    VERIFIED = "verified"
    UNKNOWN = "unknown"
    SUSPENDED = "suspended"
    REVOKED = "revoked"


@dataclass
class AuthorityVerificationResult:
    passed: bool
    status: AuthorityStatus
    message: str
    detail: Optional[str] = None


class AuthorityVerifier:
    """Authority verification against known certifying bodies.
    
    Checks issuing authorities against a known registry.
    Supports NABCB, GST portal, income tax department, etc.
    """
    
    DEFAULT_REGISTRY = {
        "nabcb": {
            "name": "National Accreditation Board for Certification Bodies",
            "accreditation": "NABCB",
            "type": "certification_body",
            "status": "active"
        },
        "bureau veritas": {
            "name": "Bureau Veritas (India) Pvt Ltd",
            "accreditation": "NABCB",
            "type": "certification_body",
            "status": "active"
        },
        "sgs": {
            "name": "SGS India Pvt Ltd",
            "accreditation": "NABCB",
            "type": "certification_body",
            "status": "active"
        },
        "tuv": {
            "name": "TUV India Pvt Ltd",
            "accreditation": "NABCB",
            "type": "certification_body",
            "status": "active"
        },
        "intertek": {
            "name": "Intertek India Pvt Ltd",
            "accreditation": "NABCB",
            "type": "certification_body",
            "status": "active"
        },
        "dnv": {
            "name": "DNV GL Business Assurance",
            "accreditation": "NABCB",
            "type": "certification_body",
            "status": "active"
        },
        "cci": {
            "name": "Certification Council of India",
            "accreditation": "NABCB",
            "type": "certification_body",
            "status": "active"
        },
        "qcs": {
            "name": "QCS Certification Pvt Ltd",
            "accreditation": "NABCB",
            "type": "certification_body",
            "status": "active"
        },
        "iso": {
            "name": "International Organization for Standardization",
            "accreditation": None,
            "type": "standards_body",
            "status": "active"
        },
        "gst": {
            "name": "Goods and Services Tax Department",
            "accreditation": None,
            "type": "government",
            "status": "active"
        },
        "income tax": {
            "name": "Income Tax Department",
            "accreditation": None,
            "type": "government",
            "status": "active"
        },
        "epf": {
            "name": "Employees' Provident Fund Organisation",
            "accreditation": None,
            "type": "government",
            "status": "active"
        },
        "esi": {
            "name": "Employees' State Insurance Corporation",
            "accreditation": None,
            "type": "government",
            "status": "active"
        },
        "dgft": {
            "name": "Director General of Foreign Trade",
            "accreditation": None,
            "type": "government",
            "status": "active"
        },
        "rdso": {
            "name": "Research Designs and Standards Organisation",
            "accreditation": None,
            "type": "railway",
            "status": "active"
        },
        "cdsco": {
            "name": "Central Drugs Standard Control Organisation",
            "accreditation": None,
            "type": "government",
            "status": "active"
        },
    }
    
    def __init__(self, registry_path: Optional[str] = None):
        """Initialize with optional custom registry.
        
        Args:
            registry_path: Path to JSON registry file (optional)
        """
        self._registry = self.DEFAULT_REGISTRY.copy()
        
        if registry_path and os.path.exists(registry_path):
            with open(registry_path, 'r') as f:
                custom = json.load(f)
                self._registry.update(custom)
    
    def load_registry(self, registry_path: str) -> bool:
        """Load custom registry from JSON file."""
        if not os.path.exists(registry_path):
            return False
        
        try:
            with open(registry_path, 'r') as f:
                custom = json.load(f)
                self._registry.update(custom)
            return True
        except Exception:
            return False
    
    def _normalize(self, name: str) -> str:
        """Normalize authority name for lookup."""
        return name.strip().lower().replace(" ", "").replace(".", "")
    
    def verify_authority(self, authority_name: str) -> AuthorityVerificationResult:
        """Verify certifying authority is in registry.
        
        Args:
            authority_name: Name of certifying body from document
            
        Returns:
            AuthorityVerificationResult
        """
        if not authority_name:
            return AuthorityVerificationResult(
                passed=False,
                status=AuthorityStatus.UNKNOWN,
                message="Authority name is empty"
            )
        
        normalized = self._normalize(authority_name)
        
        if normalized in self._registry:
            info = self._registry[normalized]
            
            if info.get("status") == "suspended":
                return AuthorityVerificationResult(
                    passed=False,
                    status=AuthorityStatus.SUSPENDED,
                    message=f"Authority is suspended: {info.get('name')}",
                    detail=info.get("name")
                )
            elif info.get("status") == "revoked":
                return AuthorityVerificationResult(
                    passed=False,
                    status=AuthorityStatus.REVOKED,
                    message=f"Authority status is revoked: {info.get('name')}",
                    detail=info.get("name")
                )
            else:
                return AuthorityVerificationResult(
                    passed=True,
                    status=AuthorityStatus.VERIFIED,
                    message=f"Verified: {info.get('name')}",
                    detail=info.get("accreditation")
                )
        
        for key, info in self._registry.items():
            if key in normalized or normalized in key:
                return AuthorityVerificationResult(
                    passed=True,
                    status=AuthorityStatus.VERIFIED,
                    message=f"Fuzzy match: {info.get('name')}",
                    detail=info.get("accreditation")
                )
        
        return AuthorityVerificationResult(
            passed=False,
            status=AuthorityStatus.UNKNOWN,
            message=f"Unknown certifying authority: {authority_name}",
            detail="Not in registry - requires manual verification"
        )
    
    def verify_certificate_type(
        self,
        certificate_body: str,
        cert_type: str
    ) -> AuthorityVerificationResult:
        """Verify certificate type is issued by appropriate body.
        
        Args:
            certificate_body: Name of issuing body
            cert_type: Type of certificate (ISO 9001, ISO 14001, etc.)
            
        Returns:
            AuthorityVerificationResult
        """
        auth_result = self.verify_authority(certificate_body)
        
        if not auth_result.passed:
            return auth_result
        
        iso_cert_types = ["9001", "14001", "45001", "27001", "22301", "50001"]
        
        if any(cert_type.startswith(iso_type) for iso_type in iso_cert_types):
            if auth_result.status == AuthorityStatus.VERIFIED:
                return AuthorityVerificationResult(
                    passed=True,
                    status=AuthorityStatus.VERIFIED,
                    message=f"Valid ISO certificate from verified body",
                    detail=f"{cert_type} by {auth_result.detail}"
                )
        
        return auth_result
    
    def get_registry_info(self, authority_name: str) -> Optional[Dict]:
        """Get full registry info for authority."""
        normalized = self._normalize(authority_name)
        
        if normalized in self._registry:
            return self._registry[normalized]
        
        for key, info in self._registry.items():
            if key in normalized or normalized in key:
                return info
        
        return None
    
    def list_active_authorities(self) -> List[str]:
        """List all active authorities in registry."""
        return [
            key for key, info in self._registry.items()
            if info.get("status") == "active"
        ]


authority_verifier = AuthorityVerifier()