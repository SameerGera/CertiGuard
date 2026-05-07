"""CertiGuard - Main entry point with real pipeline integration."""

import sys
import os
import json
from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import FastAPI, HTTPException, Query, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

app = FastAPI(title="CertiGuard API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Storage for processed tenders (in-memory for demo)
PROCESSED_RESULTS: Dict[str, Dict] = {}
TENDERS_LIST = [
    {"tender_id": "T001", "tender_name": "CRPF Uniform Supply 2026", "bidder_count": 4, "status": "active", "submission_deadline": "2026-06-15"},
    {"tender_id": "T002", "tender_name": "CRPF IT Equipment 2026", "bidder_count": 5, "status": "active", "submission_deadline": "2026-07-01"},
    {"tender_id": "T003", "tender_name": "CRPF Security Services", "bidder_count": 3, "status": "active", "submission_deadline": "2026-04-15"},
]


# ============ Models ============

class OverrideInput(BaseModel):
    criterion_id: str
    bidder_id: str
    override_verdict: str
    officer_id: str
    officer_name: str
    rationale: str
    signature: str


class ProcessTenderRequest(BaseModel):
    tender_id: str
    tender_name: str


# ============ Pipeline Integration ============

def run_pipeline_async(tender_id: str, tender_path: str, bidders_dir: str, output_dir: str):
    """Run pipeline in background."""
    try:
        from backend.src.pipeline.main import run_pipeline
        result = run_pipeline(tender_id, tender_path, bidders_dir, output_dir)
        PROCESSED_RESULTS[tender_id] = result
        print(f"[API] Pipeline completed for tender: {tender_id}")
    except Exception as e:
        print(f"[API] Pipeline failed: {e}")
        PROCESSED_RESULTS[tender_id] = {"error": str(e)}


# ============ Routes ============

@app.get("/")
def root():
    return {"status": "CertiGuard API", "version": "0.1.0"}


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.get("/api/v1/tenders")
def get_tenders():
    # Update status based on processed results
    updated_tenders = []
    for tender in TENDERS_LIST:
        tender_id = tender["tender_id"]
        if tender_id in PROCESSED_RESULTS:
            result = PROCESSED_RESULTS[tender_id]
            if "bidders" in result and result["bidders"]:
                # Check if all bidders have final verdicts (no NEEDS_REVIEW)
                all_final = all(
                    b["overall_verdict"] in ["ELIGIBLE", "NOT_ELIGIBLE"] 
                    for b in result["bidders"]
                )
                if all_final:
                    tender = {**tender, "status": "completed"}
        updated_tenders.append(tender)
    return {"tenders": updated_tenders}


@app.get("/api/v1/tenders/{tender_id}")
def get_tender_detail(tender_id: str):
    """Get tender details including extracted criteria."""
    # Find tender info
    tender_info = next((t for t in TENDERS_LIST if t["tender_id"] == tender_id), None)
    if not tender_info:
        raise HTTPException(status_code=404, detail="Tender not found")
    
    # Run pipeline to get criteria if already processed
    if tender_id in PROCESSED_RESULTS:
        result = PROCESSED_RESULTS[tender_id]
        return {
            "tender_id": tender_id,
            "tender_name": result.get("tender_name", tender_info["tender_name"]),
            "submission_deadline": result.get("submission_deadline", tender_info.get("submission_deadline", "")),
            "status": tender_info["status"],
            "bidder_count": tender_info["bidder_count"],
            "criteria": result.get("criteria", []),
            "criteria_extracted": True
        }
    
    # Parse tender document to extract criteria
    base_dir = Path(__file__).parent / "backend" / "test_data"
    tender_path = str(base_dir / "tender" / f"tender_{tender_id.split('T')[1]}.pdf")
    
    if os.path.exists(tender_path):
        try:
            from backend.src.pipeline.main import run_pipeline
            result = run_pipeline(tender_id, tender_path, str(base_dir / "bidders"), str(base_dir / "output"))
            PROCESSED_RESULTS[tender_id] = result
            return {
                "tender_id": tender_id,
                "tender_name": result.get("tender_name", tender_info["tender_name"]),
                "submission_deadline": result.get("submission_deadline", tender_info.get("submission_deadline", "")),
                "status": tender_info["status"],
                "bidder_count": tender_info["bidder_count"],
                "criteria": result.get("criteria", []),
                "criteria_extracted": True
            }
        except Exception as e:
            print(f"Error parsing tender: {e}")
    
    return {
        "tender_id": tender_id,
        "tender_name": tender_info["tender_name"],
        "submission_deadline": tender_info.get("submission_deadline", ""),
        "status": tender_info["status"],
        "bidder_count": tender_info["bidder_count"],
        "criteria": [],
        "criteria_extracted": False
    }


@app.get("/api/v1/review/queue")
def get_review_queue(tender_id: str = Query(...)):
    # Check if we have real pipeline results
    if tender_id in PROCESSED_RESULTS:
        result = PROCESSED_RESULTS[tender_id]
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])
        return result

    # Fall back to mock data for demo - but also store it so overrides work
    mock_data = build_mock_verdict(tender_id)
    PROCESSED_RESULTS[tender_id] = mock_data
    return mock_data


@app.get("/api/v1/review/criterion/{criterion_id}")
def get_criterion_detail(criterion_id: str, bidder_id: str = Query(...)):
    # Check pipeline results first
    for tender_id, result in PROCESSED_RESULTS.items():
        if "bidders" in result:
            for bidder in result["bidders"]:
                if bidder["bidder_id"] == bidder_id:
                    for criterion in bidder["criterion_results"]:
                        if criterion["criterion_id"] == criterion_id:
                            detail = criterion.copy()
                            detail["bidder_name"] = bidder["bidder_name"]
                            return detail

    raise HTTPException(status_code=404, detail="Criterion not found")


@app.post("/api/v1/process/tender")
def process_tender(
    tender_id: str = Query(...),
    tender_name: str = Query(...),
    background_tasks: BackgroundTasks = None
):
    """Process a tender using the ML pipeline."""
    # Paths for test data
    base_dir = Path(__file__).parent / "backend" / "test_data"
    tender_path = str(base_dir / "tender" / f"tender_{tender_id.split('T')[1]}.pdf")
    bidders_dir = str(base_dir / "bidders")
    output_dir = str(base_dir / "output")

    # Create directories
    os.makedirs(base_dir / "tender", exist_ok=True)
    os.makedirs(bidders_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)

    # Check if test data exists
    if not os.path.exists(tender_path):
        # Create sample tender
        create_sample_tender(tender_id, tender_name, tender_path)

    # Run pipeline in background
    try:
        from backend.src.pipeline.main import run_pipeline
        result = run_pipeline(tender_id, tender_path, bidders_dir, output_dir)
        PROCESSED_RESULTS[tender_id] = result
        return {
            "status": "completed",
            "tender_id": tender_id,
            "result": result
        }
    except Exception as e:
        return {
            "status": "error",
            "tender_id": tender_id,
            "error": str(e)
        }


@app.get("/api/v1/process/tender")
def process_tender_get(
    tender_id: str = Query(...),
    tender_name: str = Query(...)
):
    """Process a tender using GET request."""
    return process_tender(tender_id, tender_name, None)


def create_sample_tender(tender_id: str, tender_name: str, filepath: str):
    """Create a sample tender PDF."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        from reportlab.lib.units import inch

        c = canvas.Canvas(filepath, pagesize=A4)
        width, height = A4

        c.setFont("Helvetica-Bold", 16)
        c.drawString(1*inch, height - 1*inch, "TENDER DOCUMENT")

        c.setFont("Helvetica", 12)
        y = height - 1.5*inch

        lines = [
            f"Tender ID: {tender_id}",
            f"Tender Name: {tender_name}",
            "Submission Deadline: 2026-06-15",
            "",
            "EVALUATION CRITERIA:",
            "",
            "1. Valid GST Registration (MANDATORY)",
            "2. Minimum 3 Years Experience (MANDATORY)",
            "3. Annual Turnover above 50 Lakh (DESIRABLE)",
        ]

        for line in lines:
            c.drawString(1*inch, y, line)
            y -= 0.25*inch

        c.save()
    except Exception as e:
        print(f"Failed to create tender: {e}")


@app.post("/api/v1/override/apply")
def apply_override(override: OverrideInput):
    # Find the tender that has this bidder and update the verdict
    updated_tender = None
    for tender_id, result in PROCESSED_RESULTS.items():
        if "bidders" in result:
            for bidder in result["bidders"]:
                if bidder["bidder_id"] == override.bidder_id:
                    for criterion in bidder["criterion_results"]:
                        if criterion["criterion_id"] == override.criterion_id:
                            criterion["verdict"] = override.override_verdict
                            criterion["override"] = {
                                "officer_id": override.officer_id,
                                "officer_name": override.officer_name,
                                "rationale": override.rationale,
                                "signature": override.signature,
                                "timestamp": datetime.now().isoformat()
                            }
                            updated_tender = tender_id
                    
                    # Recalculate overall verdict
                    verdicts = [c["verdict"] for c in bidder["criterion_results"]]
                    if "NOT_ELIGIBLE" in verdicts:
                        bidder["overall_verdict"] = "NOT_ELIGIBLE"
                        bidder["verdict_reason"] = "Failed mandatory criterion"
                    elif "NEEDS_REVIEW" in verdicts:
                        bidder["overall_verdict"] = "NEEDS_REVIEW"
                        yellow_flags = sum(1 for c in bidder["criterion_results"] if c.get("yellow_flags"))
                        bidder["verdict_reason"] = f"{yellow_flags} criteria need review"
                    else:
                        bidder["overall_verdict"] = "ELIGIBLE"
                        bidder["verdict_reason"] = "All criteria eligible"
                    
                    bidder["overall_confidence"] = 1.0
                    break
    
    return {
        "applied": True,
        "tender_id": updated_tender,
        "officer_id": override.officer_id,
        "officer_name": override.officer_name,
        "override_verdict": override.override_verdict,
        "rationale": override.rationale,
        "signature": override.signature,
        "timestamp": datetime.now().isoformat()
    }


@app.get("/api/v1/report/generate")
def generate_report(tender_id: str = Query(...), format: str = Query("pdf")):
    if tender_id in PROCESSED_RESULTS:
        result = PROCESSED_RESULTS[tender_id]
        return {
            "format": format,
            "tender_id": tender_id,
            "data": result,
            "generated_at": datetime.now().isoformat()
        }

    return build_mock_report(tender_id, format)


@app.get("/api/v1/report/download/{format}")
def download_report(format: str, tender_id: str = Query(...)):
    if tender_id not in PROCESSED_RESULTS:
        return {"error": "Tender not processed", "tender_id": tender_id}

    result = PROCESSED_RESULTS[tender_id]
    
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)) + "/backend")
    from src.audit.exporters import exporters
    from src.audit.report_generator import report_generator
    
    tender_id_safe = tender_id.replace("/", "_").replace("\\", "_")
    
    if format == "json":
        output_path = str(output_dir / f"{tender_id_safe}_report.json")
        success = exporters.export_json(result, output_path)
    elif format == "xlsx":
        output_path = str(output_dir / f"{tender_id_safe}_report.xlsx")
        success = exporters.export_xlsx(result, output_path)
    elif format == "pdf":
        output_path = str(output_dir / f"{tender_id_safe}_report.pdf")
        success = report_generator.generate_pdf(tender_id, result.get("bidders", []), output_path)
    else:
        return {"error": f"Unsupported format: {format}"}
    
    if success and Path(output_path).exists():
        return {
            "format": format,
            "tender_id": tender_id,
            "download_url": f"/api/v1/report/file/{tender_id_safe}/{format}",
            "file_path": output_path
        }
    
    return {"error": f"Failed to generate {format} report"}


@app.get("/api/v1/report/file/{tender_id}/{format}")
def serve_report_file(tender_id: str, format: str):
    """Serve the generated report file."""
    output_dir = Path("output")
    filename_map = {
        "json": f"{tender_id}_report.json",
        "xlsx": f"{tender_id}_report.xlsx",
        "pdf": f"{tender_id}_report.pdf"
    }
    
    filename = filename_map.get(format)
    if not filename:
        return {"error": f"Unknown format: {format}"}
    
    file_path = output_dir / filename
    
    if not file_path.exists():
        return {"error": "File not found. Generate report first."}
    
    media_map = {
        "json": "application/json",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "pdf": "application/pdf"
    }
    
    from fastapi.responses import FileResponse
    return FileResponse(
        path=str(file_path),
        media_type=media_map.get(format, "application/octet-stream"),
        filename=f"certiguard_{tender_id}_report.{format}"
    )

def build_mock_verdict(tender_id: str) -> dict:
    """Different mock data for each tender."""
    
    if tender_id == "T001":
        # Uniform Supply - Mix of outcomes
        return {
            "tender_id": "T001",
            "tender_name": "CRPF Uniform Supply 2026",
            "submission_deadline": "2026-06-15",
            "bidders": [
                {
                    "bidder_id": "B001",
                    "bidder_name": "Alpha Textiles Ltd",
                    "criterion_results": [
                        {"criterion_id": "C001", "criterion_label": "Valid GST Registration", "verdict": "ELIGIBLE", "ai_confidence": 0.98, "verification_checks": [{"check_name": "GSTIN Format", "passed": True, "detail": "Valid GSTIN: 07AABCM4532L1ZK", "confidence": 0.98}], "yellow_flags": None, "evidence_refs": ["gstin"], "reason": "GSTIN verified and active"},
                        {"criterion_id": "C002", "criterion_label": "Minimum 3 Years Experience", "verdict": "NEEDS_REVIEW", "ai_confidence": 0.65, "verification_checks": [{"check_name": "Experience Years", "passed": True, "detail": "Experience mentioned in documents", "confidence": 0.7}], "yellow_flags": [{"trigger_type": "AMBIGUOUS", "reason": "Experience dates unclear - multiple date formats found", "affected_entity": "experience", "confidence_delta": -0.3}], "evidence_refs": ["experience"], "reason": "Date format unclear - requires manual verification"},
                        {"criterion_id": "C003", "criterion_label": "Annual Turnover above 50L", "verdict": "ELIGIBLE", "ai_confidence": 0.95, "verification_checks": [{"check_name": "Turnover Validation", "passed": True, "detail": "Turnover: Rs. 78.5 Lakh", "confidence": 0.95}], "yellow_flags": None, "evidence_refs": ["turnover"], "reason": "Turnover 78.5L exceeds 50L threshold"},
                    ],
                    "overall_verdict": "NEEDS_REVIEW",
                    "overall_confidence": 0.86,
                    "verdict_reason": "1 criterion needs review"
                },
                {
                    "bidder_id": "B002",
                    "bidder_name": "Beta Garments Pvt Ltd",
                    "criterion_results": [
                        {"criterion_id": "C001", "criterion_label": "Valid GST Registration", "verdict": "NOT_ELIGIBLE", "ai_confidence": 0.92, "verification_checks": [{"check_name": "GSTIN Format", "passed": False, "detail": "GST expired on 31-Mar-2025", "confidence": 0.92}], "yellow_flags": None, "evidence_refs": ["gstin"], "reason": "GST registration expired"},
                        {"criterion_id": "C002", "criterion_label": "Minimum 3 Years Experience", "verdict": "ELIGIBLE", "ai_confidence": 0.88, "verification_checks": [{"check_name": "Experience Years", "passed": True, "detail": "4 years verified", "confidence": 0.88}], "yellow_flags": None, "evidence_refs": ["experience"], "reason": "Experience: 4 years"},
                        {"criterion_id": "C003", "criterion_label": "Annual Turnover above 50L", "verdict": "ELIGIBLE", "ai_confidence": 0.9, "verification_checks": [{"check_name": "Turnover Validation", "passed": True, "detail": "45L - optional criterion", "confidence": 0.9}], "yellow_flags": None, "evidence_refs": ["turnover"], "reason": "Desirable criterion - below threshold but optional"},
                    ],
                    "overall_verdict": "NOT_ELIGIBLE",
                    "overall_confidence": 0.9,
                    "verdict_reason": "Failed mandatory criterion (GST)"
                },
                {
                    "bidder_id": "B003",
                    "bidder_name": "Gamma Industries",
                    "criterion_results": [
                        {"criterion_id": "C001", "criterion_label": "Valid GST Registration", "verdict": "ELIGIBLE", "ai_confidence": 0.99, "verification_checks": [{"check_name": "GSTIN Format", "passed": True, "detail": "Valid and active", "confidence": 0.99}], "yellow_flags": None, "evidence_refs": ["gstin"], "reason": "Active GST registration"},
                        {"criterion_id": "C002", "criterion_label": "Minimum 3 Years Experience", "verdict": "ELIGIBLE", "ai_confidence": 0.85, "verification_checks": [{"check_name": "Experience Years", "passed": True, "detail": "5 years verified", "confidence": 0.85}], "yellow_flags": None, "evidence_refs": ["experience"], "reason": "Experience: 5 years"},
                        {"criterion_id": "C003", "criterion_label": "Annual Turnover above 50L", "verdict": "ELIGIBLE", "ai_confidence": 0.88, "verification_checks": [{"check_name": "Turnover Validation", "passed": True, "detail": "52L verified from ITR", "confidence": 0.88}], "yellow_flags": None, "evidence_refs": ["turnover"], "reason": "Turnover 52L - just above threshold"},
                    ],
                    "overall_verdict": "ELIGIBLE",
                    "overall_confidence": 0.91,
                    "verdict_reason": "All criteria met"
                },
                {
                    "bidder_id": "B004",
                    "bidder_name": "Delta Uniforms LLP",
                    "criterion_results": [
                        {"criterion_id": "C001", "criterion_label": "Valid GST Registration", "verdict": "ELIGIBLE", "ai_confidence": 0.97, "verification_checks": [{"check_name": "GSTIN Format", "passed": True, "detail": "Valid GSTIN", "confidence": 0.97}], "yellow_flags": None, "evidence_refs": ["gstin"], "reason": "GST verified"},
                        {"criterion_id": "C002", "criterion_label": "Minimum 3 Years Experience", "verdict": "NOT_ELIGIBLE", "ai_confidence": 0.85, "verification_checks": [{"check_name": "Experience Years", "passed": False, "detail": "Only 2 years of experience", "confidence": 0.85}], "yellow_flags": None, "evidence_refs": ["experience"], "reason": "Only 2 years - below 3 year minimum"},
                        {"criterion_id": "C003", "criterion_label": "Annual Turnover above 50L", "verdict": "ELIGIBLE", "ai_confidence": 0.92, "verification_checks": [{"check_name": "Turnover Validation", "passed": True, "detail": "65L verified", "confidence": 0.92}], "yellow_flags": None, "evidence_refs": ["turnover"], "reason": "Turnover 65L"},
                    ],
                    "overall_verdict": "NOT_ELIGIBLE",
                    "overall_confidence": 0.91,
                    "verdict_reason": "Failed mandatory criterion (Experience)"
                },
            ],
            "audit_records": [],
            "yellow_flag_summary": {"total": 1, "by_type": {"AMBIGUOUS": 1}}
        }
    
    elif tender_id == "T002":
        # IT Equipment - Most need review, complex criteria
        return {
            "tender_id": "T002",
            "tender_name": "CRPF IT Equipment 2026",
            "submission_deadline": "2026-07-01",
            "bidders": [
                {
                    "bidder_id": "B001",
                    "bidder_name": "TechVision Systems Pvt Ltd",
                    "criterion_results": [
                        {"criterion_id": "C001", "criterion_label": "Valid GST Registration", "verdict": "ELIGIBLE", "ai_confidence": 0.99, "verification_checks": [{"check_name": "GSTIN Format", "passed": True, "detail": "Valid", "confidence": 0.99}], "yellow_flags": None, "evidence_refs": ["gstin"], "reason": "Active GST"},
                        {"criterion_id": "C002", "criterion_label": "ISO 9001 Certification", "verdict": "NEEDS_REVIEW", "ai_confidence": 0.55, "verification_checks": [{"check_name": "ISO Certificate", "passed": True, "detail": "Certificate found", "confidence": 0.6}], "yellow_flags": [{"trigger_type": "EXPIRING_SOON", "reason": "Certificate expires in 25 days", "affected_entity": "iso_cert", "confidence_delta": -0.4}], "evidence_refs": ["iso_cert"], "reason": "ISO certificate expiring soon - needs review"},
                        {"criterion_id": "C003", "criterion_label": "Annual Turnover above 1 Crore", "verdict": "ELIGIBLE", "ai_confidence": 0.94, "verification_checks": [{"check_name": "Turnover Validation", "passed": True, "detail": "2.5 Cr verified", "confidence": 0.94}], "yellow_flags": None, "evidence_refs": ["turnover"], "reason": "Turnover 2.5Cr"},
                    ],
                    "overall_verdict": "NEEDS_REVIEW",
                    "overall_confidence": 0.83,
                    "verdict_reason": "1 criterion needs review"
                },
                {
                    "bidder_id": "B002",
                    "bidder_name": "DataCore Technologies",
                    "criterion_results": [
                        {"criterion_id": "C001", "criterion_label": "Valid GST Registration", "verdict": "ELIGIBLE", "ai_confidence": 0.98, "verification_checks": [{"check_name": "GSTIN Format", "passed": True, "detail": "Valid", "confidence": 0.98}], "yellow_flags": None, "evidence_refs": ["gstin"], "reason": "Active GST"},
                        {"criterion_id": "C002", "criterion_label": "ISO 9001 Certification", "verdict": "ELIGIBLE", "ai_confidence": 0.91, "verification_checks": [{"check_name": "ISO Certificate", "passed": True, "detail": "Valid until 2027", "confidence": 0.91}], "yellow_flags": None, "evidence_refs": ["iso_cert"], "reason": "ISO 9001 valid till 2027"},
                        {"criterion_id": "C003", "criterion_label": "Annual Turnover above 1 Crore", "verdict": "NEEDS_REVIEW", "ai_confidence": 0.58, "verification_checks": [{"check_name": "Turnover Validation", "passed": True, "detail": "1.05 Cr - just above threshold", "confidence": 0.58}], "yellow_flags": [{"trigger_type": "CLOSE_THRESHOLD", "reason": "Turnover 1.05Cr very close to 1Cr threshold", "affected_entity": "turnover", "confidence_delta": -0.35}], "evidence_refs": ["turnover"], "reason": "Close to threshold - needs verification"},
                    ],
                    "overall_verdict": "NEEDS_REVIEW",
                    "overall_confidence": 0.82,
                    "verdict_reason": "1 criterion needs review"
                },
                {
                    "bidder_id": "B003",
                    "bidder_name": "CloudNet Solutions Ltd",
                    "criterion_results": [
                        {"criterion_id": "C001", "criterion_label": "Valid GST Registration", "verdict": "NOT_ELIGIBLE", "ai_confidence": 0.95, "verification_checks": [{"check_name": "GSTIN Format", "passed": False, "detail": "GST suspended", "confidence": 0.95}], "yellow_flags": None, "evidence_refs": ["gstin"], "reason": "GST status shows 'Suspended'"},
                        {"criterion_id": "C002", "criterion_label": "ISO 9001 Certification", "verdict": "ELIGIBLE", "ai_confidence": 0.88, "verification_checks": [{"check_name": "ISO Certificate", "passed": True, "detail": "Valid", "confidence": 0.88}], "yellow_flags": None, "evidence_refs": ["iso_cert"], "reason": "ISO valid"},
                        {"criterion_id": "C003", "criterion_label": "Annual Turnover above 1 Crore", "verdict": "ELIGIBLE", "ai_confidence": 0.96, "verification_checks": [{"check_name": "Turnover Validation", "passed": True, "detail": "3.2 Cr", "confidence": 0.96}], "yellow_flags": None, "evidence_refs": ["turnover"], "reason": "Turnover 3.2Cr"},
                    ],
                    "overall_verdict": "NOT_ELIGIBLE",
                    "overall_confidence": 0.93,
                    "verdict_reason": "Failed mandatory criterion (GST suspended)"
                },
                {
                    "bidder_id": "B004",
                    "bidder_name": "InfraTech Enterprises",
                    "criterion_results": [
                        {"criterion_id": "C001", "criterion_label": "Valid GST Registration", "verdict": "ELIGIBLE", "ai_confidence": 0.97, "verification_checks": [{"check_name": "GSTIN Format", "passed": True, "detail": "Valid", "confidence": 0.97}], "yellow_flags": None, "evidence_refs": ["gstin"], "reason": "Active GST"},
                        {"criterion_id": "C002", "criterion_label": "ISO 9001 Certification", "verdict": "ELIGIBLE", "ai_confidence": 0.93, "verification_checks": [{"check_name": "ISO Certificate", "passed": True, "detail": "Valid until 2028", "confidence": 0.93}], "yellow_flags": None, "evidence_refs": ["iso_cert"], "reason": "ISO 9001 valid"},
                        {"criterion_id": "C003", "criterion_label": "Annual Turnover above 1 Crore", "verdict": "ELIGIBLE", "ai_confidence": 0.95, "verification_checks": [{"check_name": "Turnover Validation", "passed": True, "detail": "1.8 Cr", "confidence": 0.95}], "yellow_flags": None, "evidence_refs": ["turnover"], "reason": "Turnover 1.8Cr"},
                    ],
                    "overall_verdict": "ELIGIBLE",
                    "overall_confidence": 0.95,
                    "verdict_reason": "All criteria met"
                },
                {
                    "bidder_id": "B005",
                    "bidder_name": "ByteWise India",
                    "criterion_results": [
                        {"criterion_id": "C001", "criterion_label": "Valid GST Registration", "verdict": "NEEDS_REVIEW", "ai_confidence": 0.5, "verification_checks": [{"check_name": "GSTIN Format", "passed": True, "detail": "Format valid but portal shows mismatch", "confidence": 0.5}], "yellow_flags": [{"trigger_type": "CROSS_DOCUMENT_CONFLICT", "reason": "GSTIN in certificate doesn't match GST portal data", "affected_entity": "gstin", "confidence_delta": -0.45}], "evidence_refs": ["gstin"], "reason": "GSTIN mismatch - manual verification required"},
                        {"criterion_id": "C002", "criterion_label": "ISO 9001 Certification", "verdict": "ELIGIBLE", "ai_confidence": 0.9, "verification_checks": [{"check_name": "ISO Certificate", "passed": True, "detail": "Valid", "confidence": 0.9}], "yellow_flags": None, "evidence_refs": ["iso_cert"], "reason": "ISO valid"},
                        {"criterion_id": "C003", "criterion_label": "Annual Turnover above 1 Crore", "verdict": "ELIGIBLE", "ai_confidence": 0.87, "verification_checks": [{"check_name": "Turnover Validation", "passed": True, "detail": "1.5 Cr", "confidence": 0.87}], "yellow_flags": None, "evidence_refs": ["turnover"], "reason": "Turnover 1.5Cr"},
                    ],
                    "overall_verdict": "NEEDS_REVIEW",
                    "overall_confidence": 0.76,
                    "verdict_reason": "1 criterion needs review"
                },
            ],
            "audit_records": [],
            "yellow_flag_summary": {"total": 3, "by_type": {"EXPIRING_SOON": 1, "CLOSE_THRESHOLD": 1, "CROSS_DOCUMENT_CONFLICT": 1}}
        }
    
    else:  # T003
        # Security Services - Fewer bidders, mostly complete
        return {
            "tender_id": "T003",
            "tender_name": "CRPF Security Services",
            "submission_deadline": "2026-04-15",
            "bidders": [
                {
                    "bidder_id": "B001",
                    "bidder_name": "SecureForce Guards LLP",
                    "criterion_results": [
                        {"criterion_id": "C001", "criterion_label": "Valid GST Registration", "verdict": "ELIGIBLE", "ai_confidence": 0.99, "verification_checks": [{"check_name": "GSTIN Format", "passed": True, "detail": "Valid", "confidence": 0.99}], "yellow_flags": None, "evidence_refs": ["gstin"], "reason": "Active GST"},
                        {"criterion_id": "C002", "criterion_label": "PSU License Valid", "verdict": "ELIGIBLE", "ai_confidence": 0.96, "verification_checks": [{"check_name": "PSU License", "passed": True, "detail": "Valid till Dec 2026", "confidence": 0.96}], "yellow_flags": None, "evidence_refs": ["psu_license"], "reason": "PSU License valid"},
                        {"criterion_id": "C003", "criterion_label": "Minimum 5 Years Experience", "verdict": "ELIGIBLE", "ai_confidence": 0.92, "verification_checks": [{"check_name": "Experience Validation", "passed": True, "detail": "7 years verified", "confidence": 0.92}], "yellow_flags": None, "evidence_refs": ["experience"], "reason": "7 years of security services experience"},
                    ],
                    "overall_verdict": "ELIGIBLE",
                    "overall_confidence": 0.96,
                    "verdict_reason": "All criteria met"
                },
                {
                    "bidder_id": "B002",
                    "bidder_name": "Vigilant Security Corp",
                    "criterion_results": [
                        {"criterion_id": "C001", "criterion_label": "Valid GST Registration", "verdict": "ELIGIBLE", "ai_confidence": 0.98, "verification_checks": [{"check_name": "GSTIN Format", "passed": True, "detail": "Valid", "confidence": 0.98}], "yellow_flags": None, "evidence_refs": ["gstin"], "reason": "Active GST"},
                        {"criterion_id": "C002", "criterion_label": "PSU License Valid", "verdict": "NOT_ELIGIBLE", "ai_confidence": 0.94, "verification_checks": [{"check_name": "PSU License", "passed": False, "detail": "License expired", "confidence": 0.94}], "yellow_flags": None, "evidence_refs": ["psu_license"], "reason": "PSU License expired in March 2026"},
                        {"criterion_id": "C003", "criterion_label": "Minimum 5 Years Experience", "verdict": "ELIGIBLE", "ai_confidence": 0.88, "verification_checks": [{"check_name": "Experience Validation", "passed": True, "detail": "6 years", "confidence": 0.88}], "yellow_flags": None, "evidence_refs": ["experience"], "reason": "6 years verified"},
                    ],
                    "overall_verdict": "NOT_ELIGIBLE",
                    "overall_confidence": 0.93,
                    "verdict_reason": "Failed mandatory criterion (PSU License)"
                },
                {
                    "bidder_id": "B003",
                    "bidder_name": "Guardian Services Ltd",
                    "criterion_results": [
                        {"criterion_id": "C001", "criterion_label": "Valid GST Registration", "verdict": "ELIGIBLE", "ai_confidence": 0.97, "verification_checks": [{"check_name": "GSTIN Format", "passed": True, "detail": "Valid", "confidence": 0.97}], "yellow_flags": None, "evidence_refs": ["gstin"], "reason": "Active GST"},
                        {"criterion_id": "C002", "criterion_label": "PSU License Valid", "verdict": "ELIGIBLE", "ai_confidence": 0.95, "verification_checks": [{"check_name": "PSU License", "passed": True, "detail": "Valid", "confidence": 0.95}], "yellow_flags": None, "evidence_refs": ["psu_license"], "reason": "PSU License valid"},
                        {"criterion_id": "C003", "criterion_label": "Minimum 5 Years Experience", "verdict": "ELIGIBLE", "ai_confidence": 0.9, "verification_checks": [{"check_name": "Experience Validation", "passed": True, "detail": "5 years", "confidence": 0.9}], "yellow_flags": None, "evidence_refs": ["experience"], "reason": "Exactly 5 years"},
                    ],
                    "overall_verdict": "ELIGIBLE",
                    "overall_confidence": 0.94,
                    "verdict_reason": "All criteria met"
                },
            ],
            "audit_records": [],
            "yellow_flag_summary": {"total": 0, "by_type": {}}
        }


def build_mock_report(tender_id: str, format: str) -> dict:
    return {
        "format": format,
        "tender_id": tender_id,
        "data": build_mock_verdict(tender_id),
        "generated_at": datetime.now().isoformat()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)