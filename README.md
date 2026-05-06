# CertiGuard Backend

Backend services for CertiGuard — an AI-powered document auditor for government procurement (CRPF).

This repository contains the verification, verdict, and audit modules.

## Features

- **Verification Engine** — Identity binding, temporal validity, anti-tampering, cross-document consistency
- **Verdict Engine** — Yellow flag protocol and verdict matrix
- **Audit Trail** — Immutable audit records with Merkle tree hashing
- **Pipeline Orchestration** — Async processing of multiple bidders

## Tech Stack

| Technology | Purpose |
|-----------|--------|
| Python 3.10+ | Core language |
| Pydantic | Data validation |
| PostgreSQL | Database |
| FastAPI | API framework |
| ReportLab | PDF generation |

## Installation

```bash
git clone https://github.com/your-org/certiguard-backend.git
cd certiguard-backend
pip install -e .
```

## Quick Start

```bash
# Run the API server
uvicorn src.pipeline.orchestrator:app --reload

# Or run the verification pipeline directly
python -c "from src.pipeline import orchestrator; orchestrator.run('tender.pdf', 'bidders/')"
```

## Project Structure

```
src/
├── verification/      # Phase 4: Deterministic checks
│   ├── rule_engine.py
│   ├── identity_binding.py
│   ├── temporal_validity.py
│   ├── authority_verifier.py
│   ├── tamper_detector.py
│   └── consistency_checker.py
├── verdict/        # Phase 5: Decision logic
│   ├── yellow_flag.py
│   └── verdict_engine.py
├── audit/         # Phase 6: Reporting
│   ├── record_generator.py
│   ├── merkle.py
│   ├── report_generator.py
│   └── exporters.py
└── pipeline/      # Orchestration
    ├── orchestrator.py
    └── parallel_runner.py
```

## API Endpoints

| Method | Endpoint | Description |
|--------|---------|------------|
| `POST` | `/verify/evaluate` | Run verification on bidder evidence |
| `POST` | `/override/apply` | Apply human override |
| `GET` | `/audit/records` | Get audit records |
| `GET` | `/report/generate` | Generate evaluation report |
