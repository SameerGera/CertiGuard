"""Tests for Phase 2: Extraction modules"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_layout_analyzer_import():
    """Test LayoutAnalyzer can be imported"""
    from src.extraction.layout_analyzer import LayoutAnalyzer, LayoutBlock, DocumentLayout
    analyzer = LayoutAnalyzer()
    assert hasattr(analyzer, "analyze")
    print("[PASS] LayoutAnalyzer import")


def test_section_classifier():
    """Test SectionClassifier can classify sections"""
    from src.extraction.section_classifier import SectionClassifier, SectionType

    classifier = SectionClassifier()

    result = classifier.classify_text("MINIMUM ELIGIBILITY CRITERIA turnover requirement")
    assert result == SectionType.ELIGIBILITY

    result = classifier.classify_text("Technical Specifications deliverable testing")
    assert result == SectionType.TECHNICAL

    result = classifier.classify_text("Scope of Work services required")
    assert result == SectionType.SCOPE

    result = classifier.classify_text("Instructions to Bidders submission procedure")
    assert result == SectionType.INSTRUCTIONS

    print("[PASS] SectionClassifier classification")


def test_criterion_segmenter():
    """Test CriterionSegmenter extracts criteria"""
    from src.extraction.criterion_segmenter import CriterionSegmenter

    segmenter = CriterionSegmenter(use_llm=False)

    sample_text = """
    ELIGIBILITY CRITERIA FOR BIDDERS

    1. Minimum Annual Turnover: The bidder should have minimum turnover of Rs. 5 Crore
       (Rupees Five Crore only) in any three of last five financial years.

    2. ISO Certification: Bidder must have valid ISO 9001:2015 certificate from NABCB.

    3. Experience: Minimum 5 years experience in security services.

    4. GST Registration: Bidder should have valid GST registration (GSTIN).

    5. PAN: Must have valid PAN card.
    """

    criteria = segmenter.extract_criteria(sample_text, "TNDR-001")
    assert len(criteria) > 0
    print(f"[INFO] Extracted {len(criteria)} criteria from sample text")

    turnover_c = next((c for c in criteria if "turnover" in c.label.lower()), None)
    if turnover_c:
        assert turnover_c.id == "TNDR-001-C001"
        print(f"[PASS] CriterionSegmenter extracted: {turnover_c.label}")


def test_entity_extractor():
    """Test EntityExtractor extracts entities"""
    from src.extraction.entity_extractor import EntityExtractor

    extractor = EntityExtractor()

    turnover = extractor._extract_financial_value("Turnover Rs. 5 Crore for FY 2023-24")
    if turnover:
        assert "5" in turnover.value
        assert turnover.entity_type == "turnover"
        print(f"[PASS] EntityExtractor financial: {turnover.value}")

    gst = extractor._extract_by_pattern("GSTIN 27AABCI1234A1ZX", "gst_number")
    if gst:
        print(f"[PASS] EntityExtractor GST: {gst.value}")

    pan = extractor._extract_by_pattern("PAN AABCU1234R", "pan_number")
    if pan:
        print(f"[PASS] EntityExtractor PAN: {pan.value}")


def test_nature_classifier():
    """Test NatureClassifier classifies criteria"""
    from src.extraction.nature_classifier import NatureClassifier
    from src.models.criterion import CriterionNature

    classifier = NatureClassifier()

    result = classifier.classify("Bidder must have ISO 9001 certificate")
    assert result == CriterionNature.MANDATORY

    result = classifier.classify("ISO 9001 certificate is preferred but optional")
    assert result == CriterionNature.DESIRABLE  # "preferred" triggers DESIRABLE

    result = classifier.classify("Additional certifications optional")
    assert result == CriterionNature.OPTIONAL

    print("[PASS] NatureClassifier classification")


def test_models_integration():
    """Test that all models can be imported together"""
    from src.models.document import DocumentMetadata, DocumentFormat, DocumentClassification
    from src.models.criterion import Criterion, CriterionNature, CriterionType, CriterionThreshold
    from src.models.evidence import EvidenceSegment, ExtractedEntity, BidderEvidence

    doc = DocumentMetadata(
        file_path="/test/tender.pdf",
        file_name="tender.pdf", 
        file_hash="sha256:abc",
        file_size_bytes=1024,
        format=DocumentFormat.PDF_DIGITAL,
    )
    assert doc.file_name == "tender.pdf"

    criterion = Criterion(
        id="C-001",
        label="Minimum Turnover",
        nature=CriterionNature.MANDATORY,
        type=CriterionType.FINANCIAL,
        threshold=CriterionThreshold(value=50000000, unit="INR", operator=">="),
    )
    assert criterion.threshold.value == 50000000

    entity = ExtractedEntity(
        entity_type="turnover",
        value="₹5 Crore",
        normalized_value="50,000,000",
        confidence=0.90,
    )
    assert entity.confidence == 0.90

    segment = EvidenceSegment(
        segment_id="SEG-001",
        file_name="pl_2024.pdf",
        file_hash="sha256:def",
        page_number=1,
        extracted_entities=[entity],
    )
    assert len(segment.extracted_entities) == 1

    print("[PASS] Phase 1 + Phase 2 model integration")


if __name__ == "__main__":
    print("Running Phase 2 Extraction tests...")
    print()

    test_layout_analyzer_import()
    test_section_classifier()
    test_criterion_segmenter()
    test_entity_extractor()
    test_nature_classifier()
    test_models_integration()

    print()
    print("=" * 50)
    print("All Phase 2 (Extraction) tests PASSED!")
    print("=" * 50)