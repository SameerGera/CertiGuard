# CertiGuard

AI-powered document verification system for government procurement tenders. CertiGuard automates bidder eligibility checks by processing tender documents and evidence PDFs through an intelligent pipeline, flagging uncertain cases for human review, and generating audit-ready reports.

---

## What It Does

CertiGuard evaluates bidder eligibility in three stages:

1. Upload tender and bidder documents
2. AI pipeline extracts entities and verifies criteria
3. Review flagged cases, override verdicts, sign off, and export reports

---

## Prerequisites

- Python 3.10 or higher
- Node.js 18 or higher
- npm 9 or higher

Optional:
- PostgreSQL 15+ (for persistent storage)
- OpenAI API key (for enhanced LLM extraction)

---

## Setup

Clone the repository:

```
git clone https://github.com/SameerGera/CertiGuard.git
cd CertiGuard
```

Install backend dependencies:

```
pip install -r requirements.txt
```

Install frontend dependencies:

```
cd frontend
npm install
cd ..
```

Create environment file:

```
cp backend/.env.example backend/.env
```

Edit `backend/.env` if needed:

```
DATABASE_URL=postgresql://user:pass@localhost:5432/certiguard
LOG_LEVEL=INFO
MAX_FILE_SIZE_MB=100
```

---

## How to Run

Start backend:

```
python main.py
```

Backend runs at: http://localhost:8000

API documentation at: http://localhost:8000/docs

Start frontend (in a new terminal):

```
cd frontend
npm run dev
```

Frontend runs at: http://localhost:3000

---

## How to Use

### 1. View Tenders

Open http://localhost:3000 to see the dashboard with sample tenders T001, T002, T003.

### 2. Upload Documents

Navigate to "Upload New Tender" to upload:
- Tender PDF document
- Bidder evidence PDFs (GST, PAN, experience letters, turnover)

### 3. Process and Review

Click "Review" on any tender to see bidder verdicts:
- Green: ELIGIBLE
- Red: NOT_ELIGIBLE
- Amber: NEEDS_REVIEW (flagged for human check)

### 4. Override (if needed)

Click on a flagged bidder, then "Override Verdict" to:
- Enter officer credentials
- Provide rationale
- Submit human decision

### 5. Sign Off and Export

Once all cases are resolved:
- Click "Sign Off" with officer details
- Generate PDF, JSON, or Excel report

---

## Project Structure

```
CertiGuard/
├── main.py                 API server entry point
├── requirements.txt         Python dependencies
├── backend/
│   └── src/
│       ├── pipeline/       ML processing pipeline
│       ├── verification/   Entity validation rules
│       ├── verdict/        Yellow flag triggers
│       └── audit/          Report generation
└── frontend/
    └── src/
        ├── pages/          Dashboard, ReviewQueue, Upload
        ├── components/     UI components
        └── hooks/          API integration
```

---

## Test Tenders

| ID | Name |
|----|------|
| T001 | CRPF Uniform Supply 2026 |
| T002 | CRPF Security Services 2026 |
| T003 | CRPF IT Equipment 2026 |

Sample data in: `backend/test_data/`

---

## Troubleshooting

Module not found:

```
export PYTHONPATH="${PYTHONPATH}:$(pwd)/backend"
```

Port already in use (8000):

```
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

Frontend API errors: Ensure backend is running before starting frontend.

---

