"""CertiGuard - Main entry point with real pipeline integration."""

import sys
import os
import json
import re
import asyncio
import threading
from datetime import datetime
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, HTTPException, Query, UploadFile, File, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

app = FastAPI(title="CertiGuard API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Thread-safe storage for processed tenders
class ThreadSafeStorage:
    def __init__(self):
        self._lock = threading.RLock()
        self._data: Dict[str, Dict] = {}
        self._tenders: List[Dict] = []
    
    def get_result(self, key: str) -> Optional[Dict]:
        with self._lock:
            return self._data.get(key)
    
    def set_result(self, key: str, value: Dict) -> None:
        with self._lock:
            self._data[key] = value
    
    def get_all_results(self) -> Dict[str, Dict]:
        with self._lock:
            return dict(self._data)
    
    def get_tenders(self) -> List[Dict]:
        with self._lock:
            return list(self._tenders)
    
    def set_tenders(self, tenders: List[Dict]) -> None:
        with self._lock:
            self._tenders = tenders
    
    def add_tender(self, tender: Dict) -> None:
        with self._lock:
            self._tenders.append(tender)
    
    def tender_exists(self, tender_id: str) -> bool:
        with self._lock:
            return any(t["tender_id"] == tender_id for t in self._tenders)

storage = ThreadSafeStorage()

INITIAL_TENDERS = [
    {"tender_id": "T001", "tender_name": "CRPF Uniform Supply 2026", "bidder_count": 4, "status": "active", "submission_deadline": "2026-06-15"},
    {"tender_id": "T002", "tender_name": "CRPF Security Services 2026", "bidder_count": 3, "status": "active", "submission_deadline": "2026-07-15"},
    {"tender_id": "T003", "tender_name": "CRPF IT Equipment 2026", "bidder_count": 5, "status": "active", "submission_deadline": "2026-07-01"},
]
storage.set_tenders(INITIAL_TENDERS)


# ============ Models ============

class OverrideInput(BaseModel):
    criterion_id: str
    bidder_id: str
    override_verdict: str
    officer_id: str
    officer_name: str
    rationale: str
    signature: str
    
    @field_validator('override_verdict')
    @classmethod
    def validate_verdict(cls, v: str) -> str:
        valid_verdicts = ['ELIGIBLE', 'NOT_ELIGIBLE', 'NEEDS_REVIEW']
        if v not in valid_verdicts:
            raise ValueError(f'override_verdict must be one of {valid_verdicts}')
        return v
    
    @field_validator('rationale')
    @classmethod
    def validate_rationale(cls, v: str) -> str:
        if len(v) < 10:
            raise ValueError('Rationale must be at least 10 characters')
        return v


class ProcessTenderRequest(BaseModel):
    tender_id: str
    tender_name: str


def sanitize_tender_id(tender_id: str) -> str:
    """Validate and sanitize tender ID to prevent path traversal."""
    if not tender_id:
        raise HTTPException(status_code=400, detail="Tender ID is required")
    if not re.match(r'^T\d{3,}$', tender_id):
        raise HTTPException(status_code=400, detail="Invalid tender ID format. Expected format: T001")
    return tender_id


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent path traversal."""
    safe_chars = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
    if safe_chars.startswith('.') or safe_chars.startswith('_'):
        safe_chars = 'file' + safe_chars
    return safe_chars


# ============ Pipeline Integration ============

def run_pipeline_async(tender_id: str, tender_path: str, bidders_dir: str, output_dir: str):
    """Run pipeline in background."""
    try:
        from backend.src.pipeline.main import run_pipeline
        result = run_pipeline(tender_id, tender_path, bidders_dir, output_dir)
        storage.set_result(tender_id, result)
        print(f"[API] Pipeline completed for tender: {tender_id}")
    except Exception as e:
        print(f"[API] Pipeline failed: {e}")
        storage.set_result(tender_id, {"error": str(e)})


# ============ Routes ============

@app.get("/")
def root():
    return {"status": "CertiGuard API", "version": "0.1.0"}


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.get("/api/v1/tenders")
def get_tenders():
    updated_tenders = []
    tenders = storage.get_tenders()
    results = storage.get_all_results()
    for tender in tenders:
        tender_id = tender["tender_id"]
        if tender_id in results:
            result = results[tender_id]
            if "bidders" in result and result["bidders"]:
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
    safe_tender_id = sanitize_tender_id(tender_id)
    
    tenders = storage.get_tenders()
    tender_info = next((t for t in tenders if t["tender_id"] == safe_tender_id), None)
    if not tender_info:
        raise HTTPException(status_code=404, detail="Tender not found")
    
    result = storage.get_result(safe_tender_id)
    if result:
        return {
            "tender_id": safe_tender_id,
            "tender_name": result.get("tender_name", tender_info["tender_name"]),
            "submission_deadline": result.get("submission_deadline", tender_info.get("submission_deadline", "")),
            "status": tender_info["status"],
            "bidder_count": tender_info["bidder_count"],
            "criteria": result.get("criteria", []),
            "criteria_extracted": True
        }
    
    base_dir = Path(__file__).parent / "backend" / "test_data"
    tender_num = safe_tender_id.split('T')[1]
    tender_path = str(base_dir / "tender" / f"tender_{tender_num}.pdf")
    
    if os.path.exists(tender_path):
        try:
            from backend.src.pipeline.main import run_pipeline
            result = run_pipeline(safe_tender_id, tender_path, str(base_dir / "bidders"), str(base_dir / "output"))
            storage.set_result(safe_tender_id, result)
            return {
                "tender_id": safe_tender_id,
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
        "tender_id": safe_tender_id,
        "tender_name": tender_info["tender_name"],
        "submission_deadline": tender_info.get("submission_deadline", ""),
        "status": tender_info["status"],
        "bidder_count": tender_info["bidder_count"],
        "criteria": [],
        "criteria_extracted": False
    }


@app.get("/api/v1/review/queue")
def get_review_queue(tender_id: str = Query(...)):
    safe_tender_id = sanitize_tender_id(tender_id)
    result = storage.get_result(safe_tender_id)
    if result:
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])
        return result

    mock_data = build_mock_verdict(safe_tender_id)
    storage.set_result(safe_tender_id, mock_data)
    return mock_data


@app.get("/api/v1/review/criterion/{criterion_id}")
def get_criterion_detail(criterion_id: str, bidder_id: str = Query(...)):
    results = storage.get_all_results()
    for tender_id, result in results.items():
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
    safe_tender_id = sanitize_tender_id(tender_id)
    base_dir = Path(__file__).parent / "backend" / "test_data"
    tender_num = safe_tender_id.split('T')[1]
    tender_path = str(base_dir / "tender" / f"tender_{tender_num}.pdf")
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

    try:
        from backend.src.pipeline.main import run_pipeline
        result = run_pipeline(safe_tender_id, tender_path, bidders_dir, output_dir)
        storage.set_result(safe_tender_id, result)
        return {
            "status": "completed",
            "tender_id": safe_tender_id,
            "result": result
        }
    except Exception as e:
        return {
            "status": "error",
            "tender_id": safe_tender_id,
            "error": str(e)
        }


@app.get("/api/v1/process/tender")
def process_tender_get(
    tender_id: str = Query(...),
    tender_name: str = Query(...)
):
    """Process a tender using GET request."""
    safe_tender_id = sanitize_tender_id(tender_id)
    base_dir = Path(__file__).parent / "backend" / "test_data"
    tender_num = safe_tender_id.split('T')[1]
    tender_path = str(base_dir / "tender" / f"tender_{tender_num}.pdf")
    bidders_dir = str(base_dir / "bidders")
    output_dir = str(base_dir / "output")
    
    try:
        from backend.src.pipeline.main import run_pipeline
        result = run_pipeline(safe_tender_id, tender_path, bidders_dir, output_dir)
        storage.set_result(safe_tender_id, result)
        return {
            "status": "completed",
            "tender_id": safe_tender_id,
            "result": result
        }
    except Exception as e:
        return {
            "status": "error",
            "tender_id": safe_tender_id,
            "error": str(e)
        }


@app.post("/api/v1/upload/tender")
async def upload_tender(
    file: UploadFile = File(...),
    tender_id: str = Form(...),
    tender_name: str = Form(...)
):
    """Upload a tender document."""
    safe_tender_id = sanitize_tender_id(tender_id)
    upload_dir = Path("uploads") / safe_tender_id / "tender"
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    safe_filename = sanitize_filename(file.filename)
    if not safe_filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    
    file_path = upload_dir / safe_filename
    content = await file.read()
    if len(content) > 100 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File size exceeds 100MB limit")
    with open(file_path, "wb") as f:
        f.write(content)
    
    return {
        "status": "uploaded",
        "tender_id": safe_tender_id,
        "tender_name": tender_name,
        "file_path": str(file_path),
        "message": "Tender uploaded successfully. Now upload bidder documents."
    }


@app.post("/api/v1/upload/bidders")
async def upload_bidders(
    files: List[UploadFile] = File(...),
    tender_id: str = Form(...)
):
    """Upload bidder documents."""
    safe_tender_id = sanitize_tender_id(tender_id)
    upload_dir = Path("uploads") / safe_tender_id / "bidders"
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    uploaded = []
    for file in files:
        safe_filename = sanitize_filename(file.filename)
        if not safe_filename.lower().endswith('.pdf'):
            continue
        file_path = upload_dir / safe_filename
        content = await file.read()
        if len(content) > 100 * 1024 * 1024:
            continue
        with open(file_path, "wb") as f:
            f.write(content)
        uploaded.append(safe_filename)
    
    return {
        "status": "uploaded",
        "tender_id": safe_tender_id,
        "files": uploaded,
        "message": f"Uploaded {len(uploaded)} bidder documents. Ready to process."
    }


@app.post("/api/v1/upload/process")
async def process_uploaded(
    tender_id: str = Form(...),
    tender_name: str = Form(...)
):
    """Process uploaded tender and bidder documents."""
    safe_tender_id = sanitize_tender_id(tender_id)
    tender_path = Path("uploads") / safe_tender_id / "tender"
    bidders_dir = Path("uploads") / safe_tender_id / "bidders"
    output_dir = Path("uploads") / safe_tender_id / "output"
    
    tender_files = list(tender_path.glob("*.pdf"))
    if not tender_files:
        return {"error": "No tender document found"}
    
    try:
        from backend.src.pipeline.main import run_pipeline
        result = run_pipeline(
            tender_id=safe_tender_id,
            tender_path=str(tender_files[0]),
            bidders_dir=str(bidders_dir),
            output_dir=str(output_dir)
        )
        
        storage.set_result(safe_tender_id, result)
        
        if not storage.tender_exists(safe_tender_id):
            storage.add_tender({
                "tender_id": safe_tender_id,
                "tender_name": tender_name,
                "bidder_count": len(result.get("bidders", [])),
                "status": "active",
                "submission_deadline": result.get("submission_deadline", "2026-12-31")
            })
        
        return {
            "status": "processed",
            "tender_id": safe_tender_id,
            "bidders_count": len(result.get("bidders", [])),
            "result": result
        }
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/v1/upload/status/{tender_id}")
def get_upload_status(tender_id: str):
    """Check what's been uploaded for a tender."""
    safe_tender_id = sanitize_tender_id(tender_id)
    upload_dir = Path("uploads") / safe_tender_id
    
    tender_files = []
    bidder_files = []
    
    if (upload_dir / "tender").exists():
        tender_files = [f.name for f in (upload_dir / "tender").glob("*.pdf")]
    
    if (upload_dir / "bidders").exists():
        bidder_files = [f.name for f in (upload_dir / "bidders").glob("*.pdf")]
    
    return {
        "tender_id": safe_tender_id,
        "tender_uploaded": len(tender_files) > 0,
        "tender_files": tender_files,
        "bidders_uploaded": len(bidder_files),
        "bidder_files": bidder_files
    }


@app.get("/api/v1/criteria/{tender_id}")
def get_criteria(tender_id: str):
    """Get extracted criteria for a tender."""
    safe_tender_id = sanitize_tender_id(tender_id)
    
    default_criteria_map = {
        'T001': [
            {'id': 'C001', 'label': 'Valid GST Registration', 'type': 'compliance', 'nature': 'MANDATORY'},
            {'id': 'C002', 'label': 'Minimum 3 Years Experience', 'type': 'technical', 'nature': 'MANDATORY'},
            {'id': 'C003', 'label': 'Annual Turnover above 50L', 'type': 'financial', 'nature': 'DESIRABLE'},
        ],
        'T002': [
            {'id': 'C001', 'label': 'Valid GST Registration', 'type': 'compliance', 'nature': 'MANDATORY'},
            {'id': 'C002', 'label': 'Minimum 5 Years Experience', 'type': 'technical', 'nature': 'MANDATORY'},
            {'id': 'C003', 'label': 'Annual Turnover above 1 Crore', 'type': 'financial', 'nature': 'DESIRABLE'},
            {'id': 'C004', 'label': 'ISO 9001 Certification', 'type': 'compliance', 'nature': 'DESIRABLE'},
        ],
        'T003': [
            {'id': 'C001', 'label': 'Valid GST Registration', 'type': 'compliance', 'nature': 'MANDATORY'},
            {'id': 'C002', 'label': 'Minimum 2 Years Experience', 'type': 'technical', 'nature': 'MANDATORY'},
            {'id': 'C003', 'label': 'Annual Turnover above 25L', 'type': 'financial', 'nature': 'DESIRABLE'},
        ],
    }
    
    result = storage.get_result(safe_tender_id)
    if result:
        return {
            "tender_id": safe_tender_id,
            "criteria": result.get("criteria", default_criteria_map.get(safe_tender_id, [])),
            "criteria_approved": result.get("criteria_approved", False),
            "sign_off": result.get("sign_off", None)
        }
    else:
        return {
            "tender_id": safe_tender_id,
            "criteria": default_criteria_map.get(safe_tender_id, [
                {'id': 'C001', 'label': 'GST Registration', 'type': 'compliance', 'nature': 'MANDATORY'},
                {'id': 'C002', 'label': 'Experience', 'type': 'technical', 'nature': 'MANDATORY'},
                {'id': 'C003', 'label': 'Turnover', 'type': 'financial', 'nature': 'DESIRABLE'},
            ]),
            "criteria_approved": False,
            "sign_off": None
        }


@app.post("/api/v1/criteria/{tender_id}/approve")
def approve_criteria(tender_id: str, officer_id: str = Query(...), officer_name: str = Query(...), signature: str = Query(...)):
    """Approve extracted criteria before final evaluation."""
    safe_tender_id = sanitize_tender_id(tender_id)
    result = storage.get_result(safe_tender_id)
    if not result:
        return {"error": "Tender not processed"}
    
    result["criteria_approved"] = True
    result["criteria_approval"] = {
        "officer_id": officer_id,
        "officer_name": officer_name,
        "signature": signature,
        "timestamp": datetime.now().isoformat()
    }
    storage.set_result(safe_tender_id, result)
    
    return {
        "status": "approved",
        "tender_id": safe_tender_id,
        "approved_at": datetime.now().isoformat()
    }


@app.post("/api/v1/criteria/{tender_id}/update")
def update_criteria(tender_id: str, criteria: List[Dict]):
    """Update criteria (edit before approval)."""
    safe_tender_id = sanitize_tender_id(tender_id)
    result = storage.get_result(safe_tender_id)
    if not result:
        return {"error": "Tender not processed"}
    
    result["criteria"] = criteria
    result["criteria_approved"] = False
    storage.set_result(safe_tender_id, result)
    
    return {
        "status": "updated",
        "tender_id": safe_tender_id,
        "message": "Criteria updated. Please review and approve."
    }


@app.post("/api/v1/signoff/{tender_id}")
def sign_off_tender(
    tender_id: str,
    officer_id: str = Query(...),
    officer_name: str = Query(...),
    signature: str = Query(...),
    notes: str = Query("")
):
    """Sign off on a tender evaluation."""
    safe_tender_id = sanitize_tender_id(tender_id)
    result = storage.get_result(safe_tender_id)
    if not result:
        return {"error": "Tender not processed"}
    
    existing_sign_off = result.get("sign_off")
    if existing_sign_off:
        existing_sign_off["previous_sign_off_history"] = existing_sign_off.copy()
    
    sign_off_data = {
        "officer_id": officer_id,
        "officer_name": officer_name,
        "signature": signature,
        "notes": notes,
        "timestamp": datetime.now().isoformat(),
        "status": "approved",
        "previous_signed_off_at": existing_sign_off.get("timestamp") if existing_sign_off else None
    }
    
    result["sign_off"] = sign_off_data
    storage.set_result(safe_tender_id, result)
    
    return {
        "status": "signed_off",
        "tender_id": safe_tender_id,
        "sign_off": sign_off_data,
        "was_previously_signed_off": existing_sign_off is not None
    }


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
    updated_tender = None
    results = storage.get_all_results()
    for tender_id, result in results.items():
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
                    storage.set_result(tender_id, result)
                    break
            else:
                continue
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
    safe_tender_id = sanitize_tender_id(tender_id)
    result = storage.get_result(safe_tender_id)
    if result:
        return {
            "format": format,
            "tender_id": safe_tender_id,
            "data": result,
            "generated_at": datetime.now().isoformat()
        }

    return build_mock_report(safe_tender_id, format)


@app.get("/api/v1/report/download/{format}")
def download_report(format: str, tender_id: str = Query(...)):
    safe_tender_id = sanitize_tender_id(tender_id)
    result = storage.get_result(safe_tender_id)
    if not result:
        return {"error": "Tender not processed", "tender_id": safe_tender_id}
    
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)) + "/backend")
    from src.audit.exporters import exporters
    from src.audit.report_generator import report_generator
    
    report_filename = safe_tender_id.replace("/", "_").replace("\\", "_")
    
    if format == "json":
        output_path = str(output_dir / f"{report_filename}_report.json")
        success = exporters.export_json(result, output_path)
    elif format == "xlsx":
        output_path = str(output_dir / f"{report_filename}_report.xlsx")
        success = exporters.export_xlsx(result, output_path)
    elif format == "pdf":
        output_path = str(output_dir / f"{report_filename}_report.pdf")
        success = report_generator.generate_pdf(safe_tender_id, result.get("bidders", []), output_path)
    else:
        return {"error": f"Unsupported format: {format}"}
    
    if success and Path(output_path).exists():
        return {
            "format": format,
            "tender_id": safe_tender_id,
            "download_url": f"/api/v1/report/file/{report_filename}/{format}",
            "file_path": output_path
        }
    
    return {"error": f"Failed to generate {format} report"}


@app.get("/api/v1/report/file/{tender_id}/{format}")
def serve_report_file(tender_id: str, format: str):
    """Serve the generated report file."""
    safe_tender_id = sanitize_tender_id(tender_id)
    output_dir = Path("output")
    filename_map = {
        "json": f"{safe_tender_id}_report.json",
        "xlsx": f"{safe_tender_id}_report.xlsx",
        "pdf": f"{safe_tender_id}_report.pdf"
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