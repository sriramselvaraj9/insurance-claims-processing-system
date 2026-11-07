# Insurance Claims Processing System

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![uv](https://img.shields.io/badge/dependency%20manager-uv-blueviolet)](https://github.com/astral-sh/uv)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com)
[![SQLAlchemy 2.x](https://img.shields.io/badge/SQLAlchemy-2.0+-red.svg)](https://www.sqlalchemy.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791.svg)](https://www.postgresql.org/)
[![Redis](https://img.shields.io/badge/Redis-7-DC382D.svg)](https://redis.io/)
[![Docker Compose](https://img.shields.io/badge/Docker-Compose-2496ED.svg)](https://www.docker.com/)
[![Tests Passing](https://img.shields.io/badge/tests-140%20passed-brightgreen.svg)](tests/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An end-to-end, enterprise-grade insurance claims intake, verification, eligibility assessment, adjuster assignment, reserve calculation, settlement adjudication, and evaluation system engineered for the **YottaFlex AI Technical Recruitment Assessment**.

---

## 1. Executive Summary

This project implements a complete insurance claims processing platform designed with strict separation of concerns, high traceability, deterministic business rules, fixed-point financial arithmetic, containerized microservice topology, and an evaluation framework with synthetic data generation.

### Supported Core Capabilities
1. **Customer & Policy Management**: Multi-line policy lifecycle management (Auto, Home, Health, Commercial, Travel).
2. **Coverage Validation**: Per-peril limit, deductible, copay enforcement, and exclusion clause resolution.
3. **Claim Intake**: Automated ingestion with document checklists and incident metadata.
4. **Document Verification**: SHA-256 verified evidentiary document linking and status workflows.
5. **Eligibility Assessment**: Multi-point automated checks covering policy status, covered perils, timely notice, and exclusions.
6. **Six Mandatory Negative Scenarios**:
   - `NEG-01`: Expired Policy Filing
   - `NEG-02`: Uncovered Peril / Policy Exclusion
   - `NEG-03`: Untimely Filing / Late Notice Violation (>30 days)
   - `NEG-04`: Missing Mandatory Evidentiary Documents
   - `NEG-05`: Claim Amount Exceeding Coverage Limit
   - `NEG-06`: Suspended Policy / Suspected Duplicate Claim Fraud
7. **Capacity-Aware Adjuster Assignment**: Workload balancing, capacity checks, and domain specialization matching.
8. **Preliminary Reserve Calculations**: Deterministic indemnity and loss adjustment expense reserves (12% standard expense ratio).
9. **Settlement Processing**: Net payment computation with deductible and copay deductions, supervisor approval gates, and duplicate disbursement prevention (HTTP 409).
10. **Exception Management & Quarantine**: Triaging of failed business rules and anomalies.
11. **Immutable Audit Trails**: Complete state-transition history capturing `state_before`, `state_after`, and actor attribution.
12. **Synthetic Data & Evaluation**: Reproducible benchmark data generation (2,000 policies, 1,000 claims, 22,933 records) with isolated ground-truth labeling.
13. **Containerized Multi-Service Deployment**: Docker Compose with FastAPI, PostgreSQL 16, and Redis 7 with fail-safe graceful degradation.

---

## 2. Technology Stack & Tooling

- **Runtime**: Python 3.12+ (tested on Python 3.13)
- **Dependency Manager**: **`uv` exclusively** (`uv lock`, `uv sync`, `uv run`, `uv add`)
- **Web Framework**: FastAPI (v0.115+)
- **ORM & Data Layer**: SQLAlchemy 2.x (Mapped column syntax) & Alembic (v1.13+)
- **Database**: PostgreSQL 16 (production/Docker) & SQLite (testing)
- **Caching & Ephemeral State**: Redis 7 (with connection pooling and fail-safe graceful degradation)
- **Data Validation & Schemas**: Pydantic v2 & Pydantic-Settings
- **Synthetic Data & Analysis**: Pandas & Faker
- **Testing & Quality Assurance**: Pytest (140 tests passing 100%)
- **Containerization**: Multi-stage Dockerfile & Docker Compose

---

## 3. Architecture Overview

The system strictly adheres to the **Layered Service-Repository Architecture**:

```
Routes (app/api/v1/) [33 Paths, 36 Operations]
   └── Services (app/services/)
         ├── Rules Engine (app/rules/) [Stateless & Pure]
         ├── State Machine (app/workflows/) [FSM Lifecycle]
         ├── Ephemeral Cache (app/core/redis.py) [Fail-Safe]
         └── Repositories (app/repositories/) [Data Access]
               ├── PostgreSQL 16 Database (app/models/)
               └── Redis 7 Cache Engine
```

### Architectural Principles:
- **Zero Database Logic in Endpoints**: Routers only handle HTTP deserialization, validation, and status mapping.
- **Pure Rules Engine**: Business rule modules in `app/rules/` are stateless, pure functions without database or external dependencies.
- **Fixed-Point Financials**: All monetary math uses `decimal.Decimal` to eliminate floating-point rounding errors.
- **Append-Only Auditing**: Every state transition generates an immutable `AuditEvent`.
- **Fail-Safe Cache Degradation**: Claim processing operations and health probes never fail if Redis is unavailable.

---

## 4. Repository Structure

```
.
├── app/
│   ├── api/             # FastAPI routing and route controllers
│   │   ├── deps.py      # Dependency injection providers (DB session, services)
│   │   └── v1/          # 10 Domain routers (claims, policies, adjusters, etc.)
│   ├── core/            # Config (BaseSettings), DB connection, Redis manager
│   ├── models/          # SQLAlchemy 2.x declarative models (11 core entities + 5 audit)
│   ├── schemas/         # Pydantic v2 schemas for requests, responses, pagination
│   ├── services/        # Orchestration and business service use cases
│   ├── repositories/    # Encapsulated data access and query layer
│   ├── rules/           # Deterministic business rules engine & 6 negative scenarios
│   ├── workflows/       # Finite State Machines and entity lifecycle transitions
│   └── main.py          # FastAPI application entrypoint with health & root probes
├── alembic/             # Alembic database schema migrations (001_initial_schema.py)
├── scripts/             # Data generation, evaluation, and loading scripts
│   ├── generate_data.py # Synthetic data generation CLI
│   ├── load_dataset.py  # High-performance relational DB loader (FK ordered)
│   ├── validate_data.py # Automated data quality and referential integrity validator
│   └── export_data.py   # Data exporter for CSV, JSON, SQL seed, and manifests
├── tests/               # Pytest test suite (140 tests passing)
│   ├── unit/            # Foundation, model, rule, service, and generator tests
│   └── integration/     # REST API, full dataset verification, deployment tests
├── data/                # Data storage for synthetic benchmarks
│   └── synthetic/       # Generated benchmark datasets (csv, json, sql, ground_truth)
├── ARCHITECTURE.md      # Architectural specification, layers, and design decisions
├── DATA_DICTIONARY.md   # Comprehensive database data dictionary for all entities
├── REQUIREMENTS_TRACEABILITY.md # Traceability matrix for all assessment requirements
├── AI_PROMPT_HISTORY.md # Assessment engineering prompt history
├── Dockerfile           # Multi-stage production container build powered by uv
├── .dockerignore        # Optimized context exclusion rules
├── docker-compose.yml   # Multi-service orchestration (API + PostgreSQL + Redis)
├── pyproject.toml       # Python packaging, dependencies, and QA tools config
├── uv.lock              # Deterministic uv dependency lockfile
├── .env.example         # Environment variables template
└── README.md            # Project overview and runbook
```

---

## 5. Quickstart & Verification (using `uv`)

### 5.1 Local Environment Setup

1. **Synchronize dependencies using uv**:
   ```powershell
   uv sync
   ```

2. **Configure environment variables**:
   ```powershell
   Copy-Item .env.example .env
   ```

3. **Run database migrations with Alembic**:
   ```powershell
   uv run alembic upgrade head
   ```

4. **Load synthetic dataset into database**:
   ```powershell
   uv run python scripts/load_dataset.py
   ```

5. **Run the full test suite**:
   ```powershell
   uv run pytest
   ```

6. **Validate synthetic data quality**:
   ```powershell
   uv run python scripts/validate_data.py
   ```

7. **Start the development server**:
   ```powershell
   uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```
   Interactive OpenAPI documentation is accessible at `http://localhost:8000/api/v1/docs`.

---

## 6. Docker & Containerized Deployment

### 6.1 Multi-Service Docker Compose

Run the entire platform (FastAPI backend + PostgreSQL 16 + Redis 7) with a single command:

```powershell
docker-compose up --build -d
```

### 6.2 Service Topology

| Service | Container Name | Image | Port | Health Check | Role |
|---|---|---|---|---|---|
| `db` | `claims_postgres` | `postgres:16-alpine` | `5432:5432` | `pg_isready -U postgres -d claims_db` | Relational database (16 tables) |
| `redis` | `claims_redis` | `redis:7-alpine` | `6379:6379` | `redis-cli ping` | Ephemeral caching & session state |
| `api` | `claims_api` | Custom (Dockerfile) | `8000:8000` | `curl -f http://localhost:8000/health` | FastAPI REST backend |

### 6.3 Loading Dataset in Containerized Database

Once Docker Compose is running, populate the PostgreSQL container database:

```powershell
docker-compose exec api uv run python scripts/load_dataset.py
```

### 6.4 Verifying Container Health

```powershell
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "database": "connected",
  "redis": "connected",
  "service": "Insurance Claims Processing System",
  "version": "0.1.0",
  "environment": "development"
}
```

---

## 7. Synthetic Dataset & Evaluation Framework

The project includes a deterministic, relationally consistent synthetic dataset generator producing **2,000 policies and 1,000 claims** across 5 balanced claim types (22,933 total relational records).

- **Re-generate dataset**:
  ```powershell
  uv run python scripts/generate_data.py --scale full --seed 20261022
  ```
- **Validate dataset**:
  ```powershell
  uv run python scripts/validate_data.py
  ```
- **Dataset Loader Modes**:
  ```powershell
  # Standard idempotent load
  uv run python scripts/load_dataset.py

  # Truncate and reload
  uv run python scripts/load_dataset.py --truncate

  # Dry-run validation without committing
  uv run python scripts/load_dataset.py --dry-run
  ```

---

## 8. Implementation Status Summary

| Phase | Description | Status | Verification Summary |
| :--- | :--- | :--- | :--- |
| **Phase 0** | Repository Inspection, Architecture Documentation, and Foundation Scaffolding | **COMPLETED** | Verified clean repository, Python 3.13, Docker, Git. |
| **Phase 1** | Database Architecture, 11 Domain Models, Alembic Migrations, and Repositories | **COMPLETED** | 16 tables, check constraints, FK relations, Alembic roundtrip. |
| **Phase 2** | Synthetic Data Generator, 6 Negative Scenarios, Isolated Ground Truth | **COMPLETED** | 2,000 policies, 1,000 claims, 22,933 records, 0 validation errors. |
| **Phase 3** | Pure Business Rules Engine, Domain Services, Workflow Orchestrator | **COMPLETED** | 26 service tests, 6 negative scenarios, finite state machine. |
| **Phase 4** | Complete REST API Layer, Pagination, 35 Integration Tests, Full Dataset API Verification | **COMPLETED** | 33 paths, 36 operations, 128 tests passing, < 100ms latency SLAs. |
| **Phase 5** | Containerization, PostgreSQL/Redis Multi-Service Compose, Dataset Loader & Final Verification | **COMPLETED** | Multi-stage Dockerfile, Compose, Redis degradation, 140 tests passing (100%). |
