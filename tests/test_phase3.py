"""Tests for Phase 3: Harvester modules"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_synonym_registry():
    """Test SynonymRegistry"""
    from src.harvester.synonym_registry import SynonymRegistry

    registry = SynonymRegistry()

    syns = registry.lookup("turnover")
    assert "turnover" in syns
    assert "gross revenue" in syns

    canonical = registry.get_canonical("gross revenue")
    assert canonical == "turnover"

    is_syn = registry.is_synonym("turnover", "total income")
    assert is_syn == True

    print("[PASS] SynonymRegistry works")


def test_synonym_matching():
    """Test synonym matching in text"""
    from src.harvester.synonym_registry import SynonymRegistry

    registry = SynonymRegistry()

    text = "Company has ISO 9001 certificate and turnover of Rs. 5 Crore"
    matches = registry.match_in_text(text)
    assert "turnover" in matches or "certificate" in matches
    print(f"[PASS] Synonym matching found: {matches.keys()}")


def test_chunker():
    """Test SmartChunker"""
    from src.harvester.chunker import SmartChunker, DocumentChunk

    chunker = SmartChunker(max_chars=500)

    text = "This is a test document.\n\nWith multiple paragraphs.\n\nAnd some content."
    chunks = chunker._chunk_text_by_size(text, page_number=1)

    assert len(chunks) > 0
    assert isinstance(chunks[0], DocumentChunk)
    print(f"[PASS] SmartChunker created {len(chunks)} chunks")


def test_segment_router():
    """Test SegmentRouter"""
    from src.harvester.segment_router import SegmentRouter

    router = SegmentRouter()

    chunks = [
        {"chunk_id": "c1", "text": "Annual turnover Rs 5 crore"},
        {"chunk_id": "c2", "text": "Address: ABC Street"},
        {"chunk_id": "c3", "text": "ISO 9001 certificate"},
    ]
    criteria = [
        {"criterion_id": "crit1", "label": "Minimum Turnover", "canonical_entities": ["turnover", "revenue"]},
        {"criterion_id": "crit2", "label": "ISO Certification", "canonical_entities": ["iso", "certificate"]},
    ]

    assignments = router.route(chunks, criteria)
    print(f"[INFO] SegmentRouter routed {len(assignments)} chunks to criteria")

    similarity = router.compute_similarity(
        "Annual turnover requirement",
        "Turnover must be 5 crore"
    )
    print(f"[INFO] Similarity score: {similarity}")
    assert similarity > 0.1
    print("[PASS] SegmentRouter works")


def test_vlm_extractor():
    """Test VLMExtractor"""
    from src.harvester.vlm_extractor import VLMExtractor

    extractor = VLMExtractor(provider="openai")

    assert extractor.provider == "openai"
    assert extractor.model == "gpt-4o-mini"

    available = extractor.is_available()
    print(f"[INFO] VLM provider available: {available}")

    print("[PASS] VLMExtractor instantiation")


def test_ocr_engine():
    """Test OCREngine"""
    from src.harvester.ocr_engine import OCREngine

    engine = OCREngine()

    available = engine.is_available()
    print(f"[INFO] OCR engine available: {available}")

    print("[PASS] OCREngine instantiation")


def test_aggregator():
    """Test Aggregator"""
    from src.harvester.aggregator import Aggregator, AggregatedValue
    from src.models.evidence import ExtractedEntity
    from src.models.criterion import AggregationMode

    aggregator = Aggregator()

    entities = [
        ExtractedEntity(entity_type="turnover", value="₹5 Crore", normalized_value="50000000", confidence=0.9),
        ExtractedEntity(entity_type="turnover", value="₹6 Crore", normalized_value="60000000", confidence=0.85),
        ExtractedEntity(entity_type="turnover", value="₹4 Crore", normalized_value="40000000", confidence=0.8),
    ]

    result = aggregator.aggregate(
        entities,
        criterion_id="C001",
        aggregation_mode=AggregationMode.AVERAGE_LAST_3_FY,
        entity_type="turnover",
    )

    assert isinstance(result, AggregatedValue)
    assert result.method == "average_last_3"
    print(f"[PASS] Aggregated value: {result.value} (method: {result.method})")

    from src.harvester.aggregator import AggregatedValue as AggrVal
    threshold_pass = aggregator.compare_threshold(result, 50000000, ">=")
    print(f"[INFO] Threshold check (50000000 >= 50000000): {threshold_pass}")
    assert threshold_pass == True

    print("[PASS] Aggregator works")


def test_full_pipeline():
    """Test full Phase 1-3 integration"""
    from src.ingestion.doc_classifier import DocClassifier
    from src.extraction.criterion_segmenter import CriterionSegmenter
    from src.extraction.entity_extractor import EntityExtractor
    from src.harvester.synonym_registry import SynonymRegistry
    from src.harvester.aggregator import Aggregator
    from src.models.document import DocumentFormat, DocumentClassification
    from src.models.evidence import ExtractedEntity, BidderEvidence, EvidenceSegment
    from src.models.criterion import CriterionNature, CriterionType

    classifier = DocClassifier()
    doc_type = classifier.classify("Annual turnover statement", DocumentFormat.PDF_DIGITAL)
    assert doc_type == DocumentClassification.FINANCIAL

    segmenter = CriterionSegmenter(use_llm=False)
    criteria = segmenter.extract_criteria("Minimum turnover Rs 5 Crore", "TNDR-001")
    assert len(criteria) >= 1

    extractor = EntityExtractor()
    entities = extractor.extract_entities("Turnover Rs 5 Crore", ["turnover"])
    assert len(entities) >= 1

    registry = SynonymRegistry()
    synonyms = registry.lookup("turnover")
    assert len(synonyms) > 1

    aggregator = Aggregator()
    result = aggregator.aggregate(
        entities,
        criterion_id="C001",
        entity_type="turnover",
    )
    assert result.value > 0

    print("[PASS] Full Phase 1-3 pipeline integration")


if __name__ == "__main__":
    print("Running Phase 3 Harvester tests...")
    print()

    test_synonym_registry()
    test_synonym_matching()
    test_chunker()
    test_segment_router()
    test_vlm_extractor()
    test_ocr_engine()
    test_aggregator()
    test_full_pipeline()

    print()
    print("=" * 50)
    print("All Phase 3 (Harvester) tests PASSED!")
    print("=" * 50)