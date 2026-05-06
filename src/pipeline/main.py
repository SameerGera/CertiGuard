"""Pipeline orchestration."""

import argparse
import sys
from typing import List, Dict, Any
from dataclasses import dataclass


@dataclass
class PipelineConfig:
    tender_id: str
    tender_path: str
    bidders_dir: str
    output_dir: str
    max_file_size_mb: int = 100
    vlm_timeout: int = 60


class PipelineOrchestrator:
    def __init__(self, config: PipelineConfig):
        self.config = config

    def run(self) -> Dict[str, Any]:
        results = {"tender_id": self.config.tender_id, "bidders": [], "errors": []}

        from src.verification.rule_engine import rule_engine
        from src.verification.identity_binding import identity_binder
        from src.verification.temporal_validity import temporal_validator
        from src.verdict.verdict_engine import verdict_engine
        from src.verdict.yellow_flag import yellow_flag_generator
        from src.audit.record_generator import record_generator
        from src.audit.exporters import exporters

        results["verification"] = "initialized"
        results["verdict"] = "initialized"
        results["audit"] = "initialized"

        return results

    def verify_bidder(self, bidder_id: str, evidence: List[Dict]) -> Dict[str, Any]:
        from src.verification.rule_engine import rule_engine

        checks = []

        for ev in evidence:
            if ev.get("entity_type") == "gstin":
                result = rule_engine.validate_gstin(ev.get("value", ""))
                checks.append({"type": "gstin", "passed": result.passed, "detail": result.message})

            if ev.get("entity_type") == "pan":
                result = rule_engine.validate_pan(ev.get("value", ""))
                checks.append({"type": "pan", "passed": result.passed, "detail": result.message})

        return {"checks": checks, "passed": all(c.get("passed") for c in checks)}

    def process_bidder(self, bidder_id: str, bidder_name: str, evidence: List[Dict]) -> Dict[str, Any]:
        verification_result = self.verify_bidder(bidder_id, evidence)

        verdict = "ELIGIBLE" if verification_result.get("passed") else "NOT_ELIGIBLE"

        return {
            "bidder_id": bidder_id,
            "bidder_name": bidder_name,
            "overall_verdict": verdict,
            "overall_confidence": 0.95,
            "verification": verification_result,
            "criteria_results": []
        }


def main():
    parser = argparse.ArgumentParser(description="CertiGuard Pipeline")
    parser.add_argument("--tender-id", required=True, help="Tender ID")
    parser.add_argument("--tender-path", required=True, help="Path to tender PDF")
    parser.add_argument("--bidders-dir", required=True, help="Path to bidders folder")
    parser.add_argument("--output-dir", required=True, help="Output directory")
    parser.add_argument("--max-file-size", type=int, default=100, help="Max file size in MB")
    parser.add_argument("--vlm-timeout", type=int, default=60, help="VLM timeout in seconds")

    args = parser.parse_args()

    config = PipelineConfig(
        tender_id=args.tender_id,
        tender_path=args.tender_path,
        bidders_dir=args.bidders_dir,
        output_dir=args.output_dir,
        max_file_size_mb=args.max_file_size,
        vlm_timeout=args.vlm_timeout
    )

    orchestrator = PipelineOrchestrator(config)
    results = orchestrator.run()

    print(f"CertiGuard initialized for tender: {args.tender_id}")
    print(f"Results: {results}")


if __name__ == "__main__":
    main()