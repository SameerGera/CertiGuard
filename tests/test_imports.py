"""Test imports."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_imports():
    try:
        from src.verification.rule_engine import rule_engine
        from src.verification.identity_binding import identity_binder
        from src.verification.temporal_validity import temporal_validator
        from src.verification.authority_verifier import authority_verifier
        from src.verification.tamper_detector import tamper_detector
        from src.verification.consistency_checker import consistency_checker
        from src.verdict.yellow_flag import yellow_flag_generator
        from src.verdict.verdict_engine import verdict_engine
        from src.audit.merkle import merkle_tree
        from src.audit.record_generator import record_generator
        from src.audit.report_generator import report_generator
        from src.audit.exporters import exporters
        from src.pipeline.main import PipelineOrchestrator
        from src.pipeline.parallel_runner import parallel_runner
        print("All imports OK")
        return True
    except Exception as e:
        print(f"Import error: {e}")
        return False


if __name__ == "__main__":
    test_imports()