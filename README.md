# Insurance Claims Processing System

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com)
[![SQLAlchemy 2.x](https://img.shields.io/badge/SQLAlchemy-2.0+-red.svg)](https://www.sqlalchemy.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791.svg)](https://www.postgresql.org/)
[![Docker Compose](https://img.shields.io/badge/Docker-Compose-2496ED.svg)](https://www.docker.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An end-to-end, enterprise-grade insurance claims intake, verification, eligibility assessment, adjuster assignment, reserve calculation, settlement, and evaluation system engineered for the **YottaFlex AI Technical Recruitment Assessment**.

---

## 1. Executive Summary

This project implements a complete insurance claims processing platform designed with strict separation of concerns, high traceability, deterministic business rules, fixed-point financial arithmetic, and an evaluation framework with synthetic data generation.

### Supported Core Capabilities
1. **Customer & Policy Management**: Multi-line policy lifecycle management (Auto, Home, Health, Commercial).
2. **Coverage Validation**: Per-peril limit, deductible, and copay enforcement.
3. **Claim Intake**: Automated ingestion with document checklists and incident metadata.
4. **Document Verification**: SHA-256 verified evidentiary document linking and status workflows.
5. **Eligibility Assessment**: Multi-point automated checks covering policy status, covered perils, timely notice, and exclusions.
6. **Six Mandatory Negative Scenarios**:
   - `NEG-01`: Expired Policy Filing
   - `NEG-02`: Uncovered Peril / Policy Exclusion
   - `NEG-03`: Untimely Filing / Late Notice Violation
   - `NEG-04`: Missing Mandatory Evidentiary Documents
   - `NEG-05`: Claim Amount Exceeding Coverage Limit
   - `NEG-06`: Suspended Policy / Suspected Duplicate Claim Fraud
7. **Capacity-Aware Adjuster Assignment**: Workload balancing and domain specialization matching.
8. **Preliminary Reserve Calculations**: Deterministic indemnity and loss adjustment expense reserves.
9. **Settlement Processing**: Net payment computation with deductible and copay deductions.
10. **Exception Management & Quarantine**: Triaging of failed business rules and anomalies.
11. **Immutable Audit Trails**: Complete state-transition history capturing `state_before`, `state_after`, and actor attribution.
12. **Synthetic Data & Evaluation**: Reproducible benchmark data generation (`Seed=42`) with ground-truth labeling and precision/recall/F1/MAE/RMSE evaluation metrics.

---

## 2. Technology Stack

- **Runtime**: Python 3.12+ (tested on Python 3.13)
- **Web Framework**: FastAPI (v0.115+)
- **ORM & Data Layer**: SQLAlchemy 2.x (Mapped syntax) & Alembic (v1.13+)
- **Database**: PostgreSQL 16 (production/Docker) & SQLite (testing)
- **Data Validation & Schemas**: Pydantic v2 & Pydantic-Settings
- **Synthetic Data & Analysis**: Pandas & Faker
- **Testing & Quality Assurance**: Pytest, Pytest-Cov, Ruff, Mypy
- **Containerization**: Docker & Docker Compose

---

## 3. Architecture Overview

The system strictly adheres to the **Layered Service-Repository Architecture**:

```
Routes (app/api/) 
   └── Services (app/services/)
         ├── Rules Engine (app/rules/) [Stateless & Pure]
         ├── State Machine (app/workflows/) [FSM Lifecycle]
         └── Repositories (app/repositories/) [Data Access]
               └── PostgreSQL Database (app/models/)
```

### Architectural Principles:
- **Zero Database Logic in Endpoints**: Routers only handle HTTP deserialization, validation, and status mapping.
- **Pure Rules Engine**: Business rule modules in `app/rules/` are stateless, pure functions without database or external dependencies.
- **Fixed-Point Financials**: All monetary math uses `decimal.Decimal` to eliminate floating-point rounding errors.
- **Append-Only Auditing**: Every state transition generates an immutable `AuditEvent`.

---

## 4. Repository Structure

```
.
├── app/
│   ├── api/             # FastAPI routing and route controllers
│   │   └── v1/          # Versioned API routes (claims, policies, adjusters, etc.)
│   ├── core/            # Configuration (BaseSettings), DB connection, logging
│   ├── models/          # SQLAlchemy 2.x declarative models (11 core entities)
│   ├── schemas/         # Pydantic v2 schemas for requests and responses
│   ├── services/        # Orchestration and business service use cases
│   ├── repositories/    # Encapsulated data access and query layer
│   ├── rules/           # Deterministic business rules engine & 6 negative scenarios
│   ├── workflows/       # Finite State Machines and entity lifecycle transitions
│   └── main.py          # FastAPI application entrypoint
├── alembic/             # Alembic database schema migrations
├── scripts/             # Data generation and evaluation scripts
├── tests/               # Pytest test suite (unit and integration)
│   ├── unit/            # Isolated unit tests for rules, schemas, and models
│   └── integration/     # End-to-end workflow and API tests
├── docs/                # Comprehensive technical and architecture documentation
│   ├── requirements.md               # Complete business and domain requirements
│   ├── architecture.md               # Architectural specification & decisions
│   ├── implementation_plan.md        # Phase-by-phase delivery roadmap
│   └── requirements_traceability.md  # Requirements Traceability Matrix (RTM)
├── data/                # Data storage for synthetic benchmarks
│   └── synthetic/       # Generated benchmark datasets and ground truth
├── prompts/             # Audit log of implementation prompts
│   └── ai_prompt_history.md
├── Dockerfile           # Production container build
├── docker-compose.yml   # Multi-container orchestration (API + PostgreSQL)
├── pyproject.toml       # Python packaging, dependencies, and QA tools config
├── requirements.txt     # Standard pip dependency requirements
├── .env.example         # Environment variables template
└── README.md            # Project overview and runbook
```

---

## 5. Quickstart & Verification

### 5.1 Local Environment Setup

1. **Clone and enter the repository**:
   ```powershell
   cd "c:\insurance claims processing system"
   ```

2. **Create and activate a virtual environment**:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

3. **Install dependencies**:
   ```powershell
   pip install -r requirements.txt
   ```

4. **Configure environment variables**:
   ```powershell
   Copy-Item .env.example .env
   ```

5. **Run the test suite**:
   ```powershell
   pytest tests/unit/test_foundation.py -v
   ```

6. **Start the development server**:
   ```powershell
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```
   Interactive OpenAPI documentation is accessible at `http://localhost:8000/api/v1/docs`.

### 5.2 Docker Compose Setup

Run the full stack (FastAPI + PostgreSQL 16) with a single command:
```powershell
docker-compose up --build
```
The database health check ensures the database is fully initialized before the API starts.

---

## 6. Implementation Status

| Phase | Description | Status |
| :--- | :--- | :--- |
| **Phase 0** | Repository Inspection, Architecture Documentation, and Foundation Scaffolding | **COMPLETED** |
| **Phase 1** | Database Architecture, 11 Domain Models, Alembic Migrations, and Repositories | *Awaiting Review* |
| **Phase 2** | Business Rules Engine, Financial Formulas, and Six Negative Scenarios | *Pending* |
| **Phase 3** | Service Orchestration, Workflow State Machines, and REST API Endpoints | *Pending* |
| **Phase 4** | Synthetic Data Generator, Ground Truth Annotation, and Evaluation Harness | *Pending* |
| **Phase 5** | End-to-End QA, Integration Verification, Docker Testing, and Final Review | *Pending* |
