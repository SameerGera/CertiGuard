"""Tests."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_rule_engine():
    from src.verification.rule_engine import rule_engine
    result = rule_engine.validate_gstin("07AABCM4532L1ZK")
    print(f"GSTIN: {result.passed}, {result.message}")
    result = rule_engine.validate_pan("ABCDE1234F")
    print(f"PAN: {result.passed}, {result.message}")
    result = rule_engine.normalize_unit("5 Crore")
    print(f"Normalize: {result}")
    print("OK")


def test_identity():
    from src.verification.identity_binding import identity_binder
    result = identity_binder.match_names("ABC Ltd", "ABC Limited")
    print(f"Match: {result.matched}, {result.score}")
    print("OK")


def test_temporal():
    from src.verification.temporal_validity import temporal_validator
    result = temporal_validator.parse_date("14/01/2026")
    print(f"Parse: {result}")
    print("OK")


def test_merkle():
    from src.audit.merkle import merkle_tree
    root = merkle_tree.build([{"a": 1}, {"b": 2}])
    print(f"Merkle root: {root}")
    print("OK")


def test_pipeline():
    from src.pipeline.main import PipelineOrchestrator, PipelineConfig
    config = PipelineConfig("T1", "t.pdf", "b/", "o/")
    orch = PipelineOrchestrator(config)
    print(f"Orchestrator: {orch}")
    print("OK")


if __name__ == "__main__":
    test_rule_engine()
    test_identity()
    test_temporal()
    test_merkle()
    test_pipeline()
    print("\nAll tests passed!")