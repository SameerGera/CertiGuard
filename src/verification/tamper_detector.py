"""Tamper Detector - Anti-tampering analysis."""

from typing import Optional, List, Dict
from dataclasses import dataclass
from enum import Enum
import re


class TamperStatus(Enum):
    CLEAN = "clean"
    SUSPICIOUS = "suspicious"
    TAMPERED = "tampered"
    UNCHECKABLE = "uncheckable"


@dataclass
class TamperDetectionResult:
    passed: bool
    status: TamperStatus
    message: str
    detail: Optional[str] = None


class TamperDetector:
    """Anti-tampering detector.
    
    Detects potential document tampering:
    - Error Level Analysis indicators
    - Metadata integrity
    - Font/format inconsistencies
    - Modification timestamps
    """
    
    SUSPICIOUS_EDITORS = [
        "adobe", "photoshop", "gimp", "paint.net", "preview",
        "microsoft office", "libreoffice", "online"
    ]
    
    def check_metadata_integrity(
        self,
        metadata: Dict
    ) -> TamperDetectionResult:
        """Check PDF/document metadata for tampering indicators.
        
        Args:
            metadata: Document metadata dictionary
            
        Returns:
            TamperDetectionResult
        """
        if not metadata:
            return TamperDetectionResult(
                passed=True,
                status=TamperStatus.UNCHECKABLE,
                message="No metadata available"
            )
        
        warnings = []
        
        if metadata.get("Creator"):
            creator = str(metadata.get("Creator")).lower()
            if any(editor in creator for editor in self.SUSPICIOUS_EDITORS):
                warnings.append(f"Created with: {metadata.get('Creator')}")
        
        if metadata.get("ModDate") and metadata.get("CreationDate"):
            import datetime
            try:
                mod_date = metadata.get("ModDate")
                create_date = metadata.get("CreationDate")
                
                if hasattr(mod_date, 'datetime') and hasattr(create_date, 'datetime'):
                    if mod_date.datetime() < create_date.datetime():
                        warnings.append("Modification date before creation date")
            except Exception:
                pass
        
        if metadata.get("Producer"):
            producer = str(metadata.get("Producer")).lower()
            if "modified" in producer or "edited" in producer:
                warnings.append(f"Modified by: {metadata.get('Producer')}")
        
        if warnings:
            return TamperDetectionResult(
                passed=False,
                status=TamperStatus.SUSPICIOUS,
                message="Suspicious metadata detected",
                detail="; ".join(warnings)
            )
        
        return TamperDetectionResult(
            passed=True,
            status=TamperStatus.CLEAN,
            message="Metadata appears clean"
        )
    
    def check_font_consistency(
        self,
        font_list: List[str]
    ) -> TamperDetectionResult:
        """Check for font inconsistencies in documents.
        
        Args:
            font_list: List of fonts used in document
            
        Returns:
            TamperDetectionResult
        """
        if not font_list:
            return TamperDetectionResult(
                passed=True,
                status=TamperStatus.UNCHECKABLE,
                message="No font data available"
            )
        
        if len(set(font_list)) > 10:
            return TamperDetectionResult(
                passed=False,
                status=TamperStatus.SUSPICIOUS,
                message="Too many different fonts",
                detail=f"{len(set(font_list))} fonts detected - possible paste"
            )
        
        return TamperDetectionResult(
            passed=True,
            status=TamperStatus.CLEAN,
            message="Font usage appears normal"
        )
    
    def check_text_objects(
        self,
        text_objects: List[Dict]
    ) -> TamperDetectionResult:
        """Check text objects for anomalies.
        
        Args:
            text_objects: List of text objects with positions
            
        Returns:
            TamperDetectionResult
        """
        if not text_objects:
            return TamperDetectionResult(
                passed=True,
                status=TamperStatus.UNCHECKABLE,
                message="No text objects to check"
            )
        
        suspicious_count = 0
        
        for obj in text_objects:
            if obj.get("hidden", False):
                suspicious_count += 1
            if obj.get("locked", False):
                suspicious_count += 1
        
        if suspicious_count > len(text_objects) * 0.3:
            return TamperDetectionResult(
                passed=False,
                status=TamperStatus.SUSPICIOUS,
                message="Suspicious text objects detected",
                detail=f"{suspicious_count} suspicious of {len(text_objects)}"
            )
        
        return TamperDetectionResult(
            passed=True,
            status=TamperStatus.CLEAN,
            message="Text objects appear normal"
        )
    
    def check_digital_signatures(
        self,
        signatures: List[Dict]
    ) -> TamperDetectionResult:
        """Check digital signature validity.
        
        Args:
            signatures: List of digital signatures
            
        Returns:
            TamperDetectionResult
        """
        if not signatures:
            return TamperDetectionResult(
                passed=True,
                status=TamperStatus.UNCHECKABLE,
                message="No digital signatures found"
            )
        
        valid_count = 0
        invalid_count = 0
        
        for sig in signatures:
            if sig.get("valid", False):
                valid_count += 1
            else:
                invalid_count += 1
        
        if invalid_count > 0:
            return TamperDetectionResult(
                passed=False,
                status=TamperStatus.SUSPICIOUS,
                message=f"{invalid_count} invalid signatures",
                detail=f"Valid: {valid_count}, Invalid: {invalid_count}"
            )
        
        return TamperDetectionResult(
            passed=True,
            status=TamperStatus.CLEAN,
            message=f"All {valid_count} signatures valid"
        )
    
    def check_image_regions(
        self,
        image_regions: List[Dict]
    ) -> TamperDetectionResult:
        """Check image regions for potential tampering.
        
        Args:
            image_regions: List of image regions
            
        Returns:
            TamperDetectionResult
        """
        if not image_regions:
            return TamperDetectionResult(
                passed=True,
                status=TamperStatus.CLEAN,
                message="No images to check"
            )
        
        warnings = []
        
        for region in image_regions:
            if region.get("compressed", False):
                pass
            if region.get("color_inconsistent", False):
                warnings.append("Color inconsistency detected")
            if region.get("resolution_mismatch", False):
                warnings.append("Resolution mismatch")
        
        if warnings:
            return TamperDetectionResult(
                passed=False,
                status=TamperStatus.SUSPICIOUS,
                message="Image anomalies detected",
                detail="; ".join(warnings)
            )
        
        return TamperDetectionResult(
            passed=True,
            status=TamperStatus.CLEAN,
            message="Image regions appear clean"
        )
    
    def analyze_full_document(
        self,
        document_data: Dict
    ) -> TamperDetectionResult:
        """Run full tamper analysis on document.
        
        Args:
            document_data: Full document analysis data
            
        Returns:
            TamperDetectionResult
        """
        results = []
        
        if "metadata" in document_data:
            results.append(
                self.check_metadata_integrity(document_data["metadata"])
            )
        
        if "fonts" in document_data:
            results.append(
                self.check_font_consistency(document_data["fonts"])
            )
        
        if "text_objects" in document_data:
            results.append(
                self.check_text_objects(document_data["text_objects"])
            )
        
        if "signatures" in document_data:
            results.append(
                self.check_digital_signatures(document_data["signatures"])
            )
        
        if "image_regions" in document_data:
            results.append(
                self.check_image_regions(document_data["image_regions"])
            )
        
        failed = [r for r in results if not r.passed]
        suspicious = [r for r in results if r.status == TamperStatus.SUSPICIOUS]
        
        if failed:
            return TamperDetectionResult(
                passed=False,
                status=TamperStatus.TAMPERED,
                message=f"Tampering indicators: {len(failed)}",
                detail=f"Failed checks: {[r.message for r in failed]}"
            )
        elif suspicious:
            return TamperDetectionResult(
                passed=True,
                status=TamperStatus.SUSPICIOUS,
                message=f"Suspicious elements: {len(suspicious)}",
                detail=f"Warnings: {[r.message for r in suspicious]}"
            )
        else:
            return TamperDetectionResult(
                passed=True,
                status=TamperStatus.CLEAN,
                message="Document appears clean"
            )


tamper_detector = TamperDetector()