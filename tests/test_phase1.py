"""Tests for Phase 1: Ingestion modules"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_crawler():
    """Test FileCrawler can be instantiated"""
    from src.ingestion.crawler import FileCrawler
    crawler = FileCrawler()
    assert hasattr(crawler, "crawl")
    print("[PASS] FileCrawler instantiation")


def test_format_detector():
    """Test FormatDetector can be instantiated"""
    from src.ingestion.format_detector import FormatDetector
    detector = FormatDetector()
    assert hasattr(detector, "detect")
    print("[PASS] FormatDetector instantiation")


def test_doc_classifier():
    """Test DocClassifier can classify documents"""
    from src.ingestion.doc_classifier import DocClassifier
    from src.models.document import DocumentFormat, DocumentClassification

    classifier = DocClassifier()
    
    result = classifier.classify("Annual turnover Rs 5 crore P&L statement", DocumentFormat.PDF_DIGITAL)
    assert result == DocumentClassification.FINANCIAL
    
    result = classifier.classify("ISO 9001:2015 Certificate issued by NABCB", DocumentFormat.PDF_DIGITAL)
    assert result == DocumentClassification.CERTIFICATE
    
    result = classifier.classify("GST Registration Certificate GSTIN 27AABCI1234", DocumentFormat.PDF_DIGITAL)
    assert result == DocumentClassification.TAX_DOC
    
    result = classifier.classify("Work Order No. WO/2024/001 dated 01/01/2024", DocumentFormat.PDF_DIGITAL)
    assert result == DocumentClassification.WORK_ORDER
    
    result = classifier.classify("Company Profile Infrastructure details", DocumentFormat.PDF_DIGITAL)
    assert result == DocumentClassification.PROFILE
    
    result = classifier.classify("Random text with no meaning xyz", DocumentFormat.PDF_DIGITAL)
    assert result == DocumentClassification.UNKNOWN
    
    print("[PASS] DocClassifier classification works")


def test_models():
    """Test that all models can be imported"""
    from src.models.document import DocumentMetadata, DocumentFormat, DocumentClassification
    from src.models.criterion import Criterion, CriterionNature, CriterionType, CriterionThreshold
    from src.models.evidence import BidderEvidence, EvidenceSegment, ExtractedEntity
    
    doc = DocumentMetadata(
        file_path="/test/file.pdf",
        file_name="file.pdf",
        file_hash="sha256:abc123",
        file_size_bytes=1024,
        format=DocumentFormat.PDF_DIGITAL,
    )
    assert doc.file_name == "file.pdf"
    
    criterion = Criterion(
        id="C-001",
        label="Minimum Turnover",
        nature=CriterionNature.MANDATORY,
        type=CriterionType.FINANCIAL,
        threshold=CriterionThreshold(value=50000000, unit="INR", operator=">="),
    )
    assert criterion.id == "C-001"
    assert criterion.threshold.value == 50000000
    
    segment = EvidenceSegment(
        segment_id="SEG-001",
        file_name="pan_card.pdf",
        file_hash="sha256:def456",
        page_number=1,
    )
    assert segment.segment_id == "SEG-001"
    
    print("[PASS] All models can be instantiated")


if __name__ == "__main__":
    print("Running Phase 1 Ingestion tests...")
    print()
    
    test_crawler()
    test_format_detector()
    test_doc_classifier()
    test_models()
    
    print()
    print("=" * 50)
    print("All Phase 1 (Ingestion) tests PASSED!")
    print("=" * 50)