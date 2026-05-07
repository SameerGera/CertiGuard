# CertiGuard

An AI-powered document verification system for government procurement tenders. CertiGuard automatically evaluates bidder documents against tender eligibility criteria, flags ambiguous cases for human review, and generates audit-ready reports.

## Overview

CertiGuard is designed to streamline the verification of bidder eligibility in government procurement (specifically CRPF tenders). It processes tender documents and bidder evidence (GST certificates, PAN cards, experience letters, turnover documents) through a multi-phase pipeline that:

1. **Extracts** criteria from tender documents
2. **Harvests** entity data from bidder PDFs using OCR
3. **Verifies** each document against validation rules
4. **Flags** ambiguous cases with yellow flags for human review
5. **Generates** final verdicts with full audit trails

The system supports three verdict outcomes: **ELIGIBLE** (all criteria passed), **NOT_ELIGIBLE** (failed mandatory criterion), and **NEEDS_REVIEW** (yellow flag triggered, requires human decision).

## Prerequisites

Before you begin, ensure you have the following installed:

| Software | Minimum Version | Purpose |
|----------|-----------------|---------|
| **Python** | 3.10+ | Backend runtime |
| **Node.js** | 18+ | Frontend build tools |
| **npm** | 9+ | Frontend package manager |

### Optional (for production)

| Software | Purpose |
|----------|---------|
| **PostgreSQL 15+** | Persistent data storage |
| **Docker** | Containerized deployment |

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/your-org/CertiGuard.git
cd CertiGuard
```

### 2. Set Up Python Environment

```bash
# Create and activate virtual environment
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

### 3. Install Backend Dependencies

```bash
# Install from requirements
pip install -r requirements.txt

# Or install backend package with dev dependencies
cd backend
pip install -e ".[dev]"
cd ..
```

### 4. Set Up Environment Variables

```bash
# Copy example environment file
cp backend/.env.example backend/.env
```

Edit `backend/.env` with your configuration:

```env
# Database (optional - uses in-memory storage if not set)
DATABASE_URL=postgresql://user:pass@localhost:5432/certiguard

# App Config
LOG_LEVEL=INFO
MAX_FILE_SIZE_MB=100
VLM_TIMEOUT_SECONDS=60

# Optional: Cloud LLM API keys (for enhanced extraction)
# OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...
```

### 5. Set Up Frontend (if needed)

```bash
# Navigate to frontend directory
cd frontend

# Create package.json if missing
npm init -y

# Install dependencies
npm install react react-dom react-router-dom axios tailwindcss postcss autoprefixer

# Install dev dependencies
npm install -D vite @vitejs/plugin-react typescript @types/react @types/react-dom
```

## Running the Application

### Backend Only (API Server)

Start the FastAPI backend on port 8000:

```bash
# From project root
python main.py
```

Or with uvicorn directly:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`. API docs at `http://localhost:8000/docs`.

### Frontend Development Server

```bash
cd frontend
npm run dev
```

The frontend will start on `http://localhost:3000` with API requests proxied to the backend.

### Run Tests

```bash
# Backend tests
cd backend
pytest tests/ -v --cov=src

# Or from root
python -m pytest backend/tests/ -v
```

## Steps to Use

### 1. Upload a Tender Document

Use the upload endpoint or frontend to submit a tender PDF:

```bash
# Via API
curl -X POST "http://localhost:8000/api/v1/upload/tender" \
  -F "file=@tender.pdf" \
  -F "tender_id=T001" \
  -F "tender_name=CRPF Uniform Supply 2026"
```

### 2. Upload Bidder Documents

Upload supporting documents for each bidder:

```bash
curl -X POST "http://localhost:8000/api/v1/upload/bidders" \
  -F "files=@B001_gst.pdf" \
  -F "files=@B001_pan.pdf" \
  -F "files=@B001_experience.pdf" \
  -F "tender_id=T001"
```

### 3. Process and Evaluate

Run the pipeline to evaluate all bidders:

```bash
curl "http://localhost:8000/api/v1/upload/process?tender_id=T001&tender_name=CRPF%20Uniform%20Supply%2026"
```

### 4. Review Yellow Flags

View cases requiring human review:

```bash
curl "http://localhost:8000/api/v1/review/queue?tender_id=T001"
```

### 5. Apply Overrides (if needed)

Override AI verdicts with human decisions:

```bash
curl -X POST "http://localhost:8000/api/v1/override/apply" \
  -H "Content-Type: application/json" \
  -d '{
    "criterion_id": "C002",
    "bidder_id": "B001",
    "override_verdict": "ELIGIBLE",
    "officer_id": "OFF001",
    "officer_name": "John Smith",
    "rationale": "Experience certificate verified via phone call with employer.",
    "signature": "JSmith-2026"
  }'
```

### 6. Sign Off and Generate Report

Approve the evaluation and generate reports:

```bash
# Sign off
curl -X POST "http://localhost:8000/api/v1/signoff/T001?officer_id=OFF001&officer_name=John%20Smith&signature=JSmith"

# Generate PDF report
curl "http://localhost:8000/api/v1/report/download/pdf?tender_id=T001"
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Health check |
| `GET` | `/health` | Detailed health status |
| `GET` | `/api/v1/tenders` | List all tenders |
| `GET` | `/api/v1/tenders/{tender_id}` | Get tender details |
| `POST` | `/api/v1/upload/tender` | Upload tender document |
| `POST` | `/api/v1/upload/bidders` | Upload bidder documents |
| `POST` | `/api/v1/upload/process` | Process uploaded documents |
| `GET` | `/api/v1/review/queue` | Get review queue |
| `POST` | `/api/v1/override/apply` | Apply human override |
| `POST` | `/api/v1/signoff/{tender_id}` | Sign off tender |
| `GET` | `/api/v1/report/generate` | Generate report |
| `GET` | `/api/v1/report/download/{format}` | Download report (pdf/json/xlsx) |

## Project Structure

```
CertiGuard/
├── main.py                 # FastAPI entry point (API server)
├── requirements.txt        # Python dependencies
│
├── backend/
│   ├── src/
│   │   ├── pipeline/       # Pipeline orchestration
│   │   │   └── main.py     # CertiGuardPipeline class
│   │   ├── verification/   # Phase 4: Deterministic checks
│   │   │   ├── rule_engine.py       # GSTIN, PAN, amount validation
│   │   │   ├── identity_binding.py  # Name matching
│   │   │   ├── temporal_validity.py # Date/expiry checks
│   │   │   └── consistency_checker.py
│   │   ├── verdict/        # Phase 5: Decision logic
│   │   │   ├── yellow_flag.py        # Yellow flag triggers
│   │   │   └── verdict_engine.py     # Verdict matrix
│   │   ├── audit/          # Phase 6: Reporting
│   │   │   ├── record_generator.py
│   │   │   ├── merkle.py
│   │   │   ├── report_generator.py
│   │   │   └── exporters.py
│   │   ├── extraction/     # Phase 3: Entity extraction
│   │   │   └── entity_extractor.py
│   │   └── models/         # Pydantic data models
│   ├── pyproject.toml      # Backend project config
│   └── .env.example        # Environment variables
│
└── frontend/               # React TypeScript frontend
    ├── src/
    │   ├── pages/          # Dashboard, ReviewQueue, Upload, etc.
    │   ├── components/     # Reusable UI components
    │   ├── hooks/          # Custom React hooks
    │   └── App.tsx         # Main app with routing
    ├── vite.config.ts      # Vite configuration
    └── tailwind.config.js  # Tailwind CSS config
```

## Verdict System

CertiGuard uses a three-tier verdict system:

| Verdict | Meaning | Action Required |
|---------|---------|-----------------|
| **ELIGIBLE** | All criteria passed | None |
| **NOT_ELIGIBLE** | Failed mandatory criterion | Disqualify |
| **NEEDS_REVIEW** | Yellow flag triggered | Human decision needed |

### Yellow Flag Triggers

The system automatically flags cases requiring human review:

- Low extraction confidence (< 70%)
- High OCR error rate (> 15%)
- Missing mandatory fields
- Cross-document value conflicts
- Document tampering detected
- Qualitative claims instead of numeric values
- Handwritten content (confidence < 60%)
- Certificates expiring within 30 days
- Unknown issuing authorities
- Name mismatches (partial match score 0.5-0.8)

## Troubleshooting

### "Module not found" errors

```bash
# Ensure Python path is set
export PYTHONPATH="${PYTHONPATH}:$(pwd)/backend"
```

### Database connection errors

If using PostgreSQL, ensure the database exists:

```bash
createdb certiguard
```

If you don't need persistent storage, simply don't set `DATABASE_URL` in `.env` - the system defaults to in-memory storage.

### Port already in use

```bash
# Find and kill process on port 8000
# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# macOS/Linux
lsof -i :8000
kill -9 <PID>
```

