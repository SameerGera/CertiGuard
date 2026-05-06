"""
End-to-End Test: ML Pipeline (Phases 1-3)

This demonstrates the complete ML workflow:
1. Ingestion → 2. Extraction → 3. Harvester → MLOutput
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ingestion.crawler import FileCrawler
from src.ingestion.format_detector import FormatDetector
from src.ingestion.doc_classifier import DocClassifier
from src.extraction.layout_analyzer import LayoutAnalyzer
from src.extraction.section_classifier import SectionClassifier
from src.extraction.criterion_segmenter import CriterionSegmenter
from src.extraction.entity_extractor import EntityExtractor
from src.extraction.nature_classifier import NatureClassifier
from src.harvester.synonym_registry import SynonymRegistry
from src.harvester.chunker import SmartChunker
from src.harvester.segment_router import SegmentRouter
from src.harvester.aggregator import Aggregator
from src.api.ml_output import MLOutput
from src.models.document import DocumentFormat, DocumentClassification
from src.models.criterion import CriterionNature, AggregationMode
from src.models.evidence import ExtractedEntity


def main():
    print("=" * 60)
    print("CertiGuard ML Pipeline End-to-End Test")
    print("=" * 60)
    print()

    # ============================================================
    # PHASE 1: INGESTION
    # ============================================================
    print("PHASE 1: INGESTION")
    print("-" * 40)

    print("\n[1.1] FileCrawler - Crawl directory")
    # Simulate crawling a bidder directory
    crawler = FileCrawler()
    print(f"  - Supported extensions: {crawler.supported_extensions}")
    print(f"  - Max file size: {crawler.max_file_size / 1024 / 1024:.0f} MB")

    print("\n[1.2] FormatDetector - Detect file formats")
    detector = FormatDetector()
    print(f"  - Can detect: PDF (digital/scanned), DOCX, XLSX, IMAGE")

    print("\n[1.3] DocClassifier - Classify documents")
    classifier = DocClassifier()

    test_docs = [
        ("Annual turnover Rs 5 Crore P&L statement", "FINANCIAL"),
        ("ISO 9001:2015 Certificate", "CERTIFICATE"),
        ("GST Registration Certificate GSTIN 27AABCI1234A1ZX", "TAX_DOC"),
        ("Work Order WO/2024/001", "WORK_ORDER"),
        ("Company Profile Infrastructure", "PROFILE"),
    ]

    for text, expected in test_docs:
        result = classifier.classify(text, DocumentFormat.PDF_DIGITAL)
        status = "OK" if result.value == expected else "FAIL"
        print(f"  {status} '{text[:35]}...' -> {result.value}")

    # ============================================================
    # PHASE 2: EXTRACTION
    # ============================================================
    print("\n\nPHASE 2: EXTRACTION")
    print("-" * 40)

    print("\n[2.1] LayoutAnalyzer - Analyze document layout")
    layout_analyzer = LayoutAnalyzer()
    print(f"  - Returns: blocks, tables, headers, TOC")

    print("\n[2.2] SectionClassifier - Classify tender sections")
    section_clf = SectionClassifier()

    test_sections = [
        "ELIGIBILITY CRITERIA",
        "TECHNICAL SPECIFICATIONS",
        "SCOPE OF WORK",
        "INSTRUCTIONS TO BIDDERS",
    ]

    for section in test_sections:
        result = section_clf.classify_text(section)
        print(f"  '{section}' -> {result.value}")

    print("\n[2.3] CriterionSegmenter - Extract criteria from tender")
    segmenter = CriterionSegmenter(use_llm=False)

    tender_text = """
    ELIGIBILITY CRITERIA FOR BIDDERS

    1. Minimum Annual Turnover: The bidder should have minimum turnover of Rs. 5 Crore
       in any three of last five financial years.

    2. ISO Certification: Bidder must have valid ISO 9001:2015 certificate.

    3. Experience: Minimum 5 years experience in security services.

    4. GST Registration: Bidder must have valid GST registration.

    5. PAN: Must have valid PAN card.
    """

    criteria = segmenter.extract_criteria(tender_text, "CRPF-2025-001")
    print(f"  Extracted {len(criteria)} criteria:")
    for c in criteria:
        print(f"    - {c.id}: {c.label} ({c.nature.value}, {c.type.value})")
        if c.threshold:
            print(f"        Threshold: {c.threshold.value:,} {c.threshold.unit}")

    print("\n[2.4] EntityExtractor - Extract entities from documents")
    entity_extractor = EntityExtractor()

    test_texts = [
        "Annual Turnover Rs. 5 Crore for FY 2023-24",
        "GSTIN 27AABCI1234A1ZX PAN AABCU1234R",
        "Established: Sharma Construction Pvt Ltd",
    ]

    for text in test_texts:
        entities = entity_extractor.extract_entities(
            text, ["turnover", "gst_number", "company_name"]
        )
        for e in entities:
            print(f"  '{text[:30]}...' -> {e.entity_type}: {e.value}")

    print("\n[2.5] NatureClassifier - Classify criteria as MANDATORY/OPTIONAL")
    nature_clf = NatureClassifier()

    test_natures = [
        "Bidder must have ISO 9001 certificate",
        "ISO certification is preferred",
        "Additional certifications are optional",
    ]

    for text in test_natures:
        result = nature_clf.classify(text)
        print(f"  '{text}' -> {result.value}")

    # ============================================================
    # PHASE 3: HARVESTER
    # ============================================================
    print("\n\nPHASE 3: HARVESTER")
    print("-" * 40)

    print("\n[3.1] SynonymRegistry - Map synonyms")
    registry = SynonymRegistry()

    synonyms = registry.lookup("turnover")
    print(f"  'turnover' synonyms: {synonyms[:4]}")

    canonical = registry.get_canonical("gross revenue")
    print(f"  'gross revenue' to canonical: {canonical}")

    print("\n[3.2] SmartChunker - Chunk documents")
    chunker = SmartChunker(max_chars=500)

    sample_text = """
    This is a large document with multiple paragraphs.
    
    First paragraph contains some information about turnover.
    
    Second paragraph has details about the company.
    
    Third paragraph includes certification details.
    """

    chunks = chunker._chunk_text_by_size(sample_text, page_number=1)
    print(f"  Created {len(chunks)} chunks from sample text")

    print("\n[3.3] SegmentRouter - Route chunks to criteria")
    router = SegmentRouter()

    chunks = [
        {"chunk_id": "c1", "text": "Annual turnover Rs 5 crore in FY 2023"},
        {"chunk_id": "c2", "text": "Address: 123 Main Street"},
        {"chunk_id": "c3", "text": "ISO 9001:2015 certificate"},
    ]
    criteria_dict = [
        {"criterion_id": "crit1", "label": "Minimum Turnover", "canonical_entities": ["turnover", "revenue"]},
        {"criterion_id": "crit2", "label": "ISO Certification", "canonical_entities": ["iso", "certificate"]},
    ]

    assignments = router.route(chunks, criteria_dict)
    print(f"  Routed {len(assignments)} chunks to criteria")

    print("\n[3.4] Aggregator - Aggregate evidence")
    aggregator = Aggregator()

    entities = [
        ExtractedEntity(entity_type="turnover", value="5 Crore", normalized_value="50000000", confidence=0.9),
        ExtractedEntity(entity_type="turnover", value="6 Crore", normalized_value="60000000", confidence=0.85),
        ExtractedEntity(entity_type="turnover", value="4 Crore", normalized_value="40000000", confidence=0.8),
    ]

    result = aggregator.aggregate(
        entities,
        criterion_id="C001",
        aggregation_mode=AggregationMode.AVERAGE_LAST_3_FY,
        entity_type="turnover",
    )

    print(f" Aggregated: {result.value} ({result.method})")
    print(f"  Confidence: {result.confidence:.2f}")
    print(f"  Threshold check: {result.value} >= 50000000? {aggregator.compare_threshold(result, 50000000, '>=')}")

    # ============================================================
    # COMPLETE ML OUTPUT
    # ============================================================
    print("\n\n" + "=" * 60)
    print("COMPLETE ML OUTPUT (Ready for Backend)")
    print("=" * 60)

    # Build the final MLOutput
    ml_output = MLOutput.from_criteria_and_evidence(
        tender_id="CRPF-2025-001",
        tender_name="Security Services Tender 2025",
        criteria=criteria,
        bidder_evidence=[],
        processing_metadata={
            "documents_processed": 10,
            "vlm_calls": 5,
            "total_tokens": 15000,
        },
    )

    print(f"\nTender ID: {ml_output.tender_id}")
    print(f"Tender Name: {ml_output.tender_name}")
    print(f"Criteria Count: {len(ml_output.criteria)}")
    print(f"Bidders Processed: {len(ml_output.bidder_evidence)}")
    print(f"Processing Metadata: {ml_output.processing_metadata}")

    print("\n" + "=" * 60)
    print("END-TO-END TEST COMPLETE!")
    print("=" * 60)
    print("\nThis MLOutput is now ready to be passed to the Backend Engineer")
    print("for phases 4-6 (Verification, Verdict, Audit).")


if __name__ == "__main__":
    main()