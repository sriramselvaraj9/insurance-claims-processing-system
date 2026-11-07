# System Architecture Specification: Insurance Claims Processing System

**Assessment Provider**: YottaFlex AI Recruitment Technical Assessment  
**System Architecture**: Clean Layered Decoupled Enterprise Architecture  
**Target Environment**: Python 3.12+, FastAPI, PostgreSQL 16, Redis 7, SQLAlchemy 2.x, Alembic, Docker, uv  
**Document Version**: 5.0.0 (Phase 5 Containerization, PostgreSQL Deployment & Final Baseline)  

---

## 1. High-Level Architectural Overview

The system is structured around the **Layered Repository-Service Architecture**, strictly enforcing unidirectional dependencies, clear separation of concerns, and isolated database access:

```
[ HTTP Requests / API Clients / CLI Scripts ]
                       │
                       ▼
┌──────────────────────────────────────────────────────────┐
│              API Layer (FastAPI Routers)                 │  <-- app/api/v1/
│  - 33 unique paths, 36 method+path operations            │
│  - Request validation & serialization (Pydantic v2)      │
│  - HTTP error translation (400, 404, 409, 422, 503)      │
│  - Dependency injection (Service & Session resolution)   │
└──────────────────────────┬───────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────┐
│             Service Orchestration Layer                  │  <-- app/services/
│  - Use-case coordination (Claims, Policies, Settlements) │
│  - Transaction boundaries & commit/rollback              │
│  - Audit event publishing & exception dispatch           │
│  - Redis ephemeral caching & graceful degradation        │
└──────────────┬───────────────────────────┬───────────────┘
               │                           │
       ┌───────┴───────────────────┐       │
       ▼                           ▼       │
┌─────────────────────────┐ ┌──────────────┴──────────────┐
│  Business Rules Engine  │ │   Workflow State Machine    │  <-- app/rules/ &
│  - Pure & stateless     │ │  - Finite state transitions │      app/workflows/
│  - 6 Negative scenarios │ │  - Validates legal states   │
│  - Financial arithmetic │ │  - Emits lifecycle events   │
└─────────────────────────┘ └─────────────────────────────┘
               │                           │
               └───────────┬───────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────┐
│             Repository Data Access Layer                 │  <-- app/repositories/
│  - Encapsulates all SQLAlchemy 2.x queries               │
│  - BaseRepository generic CRUD + specialized queries     │
│  - Pure data access: NO business rules inside repos      │
└──────────────┬───────────────────────────┬───────────────┘
               │                           │
               ▼                           ▼
┌──────────────────────────────┐ ┌─────────────────────────┐
│     PostgreSQL 16 Database   │ │      Redis 7 Cache      │
│  - 11 Core + 5 Audit Tables  │ │  - Ephemeral caching    │
│  - FKs, CheckConstraints     │ │  - Graceful degradation │
│  - Alembic migrations        │ │  - Rate-limit / session │
└──────────────────────────────┘ └─────────────────────────┘
```

---

## 2. Dependency Management: `uv` Standard

The project uses Astral's `uv` as its sole package and project manager. All dependencies, locking, tool invocation, and container builds depend exclusively on `pyproject.toml` and `uv.lock`.

- No `requirements.txt` or `pip` is used in development or container builds.
- Runtime command: `uv run uvicorn app.main:app --host 0.0.0.0 --port 8000`
- Test command: `uv run pytest`
- Data validation: `uv run python scripts/validate_data.py`
- Dataset loading: `uv run python scripts/load_dataset.py`

---

## 3. Database Architecture & Entity Schema

The database model is divided into 11 core domain entities and 5 supporting audit and history entities:

### 3.1 Eleven Core Domain Entities

1. **Customer**: Policyholder master record. Tracks personal details, KYC status (`PENDING`, `VERIFIED`, `REJECTED`, `FLAGGED`), and risk tier (`LOW`, `MEDIUM`, `HIGH`).
2. **Policy**: Insurance contract across Auto, Home, Health, Commercial, and Travel lines. Lifecycle: `DRAFT`, `ACTIVE`, `SUSPENDED`, `EXPIRED`, `CANCELLED`.
3. **Coverage**: Specific policy coverage clause with individual limits, deductibles, and coinsurance/copay percentage.
4. **Incident**: Loss casualty record tracking incident type, date, description, and street/city/state/zip location.
5. **Claim**: Primary claim record with claimed amounts, estimated losses, claim type, status, and policy linkage. Relational invariant: `claim.customer_id == policy.customer_id`.
6. **ClaimItem**: Line-item breakdown of loss components; references applicable coverage clause; stores quantity, unit amount, and total amount (`quantity * unit_amount == total_amount`).
7. **Document**: Evidentiary files attached to claims. Stores MIME type, file size, SHA-256 checksum, and verification status (`PENDING`, `VERIFIED`, `REJECTED`).
8. **Adjuster**: Adjuster profile with specialization domain, active claims count, maximum capacity, and availability status (`ACTIVE`, `ON_LEAVE`, `INACTIVE`).
9. **Assessment**: Complete eligibility decision capturing 6 discrete checks (`policy_active`, `incident_covered`, `timely_filing`, `exclusions`, `documents_complete`, `fraud`), rejection codes, and reasons. Supports append-only reassessment history.
10. **Reserve**: Financial reserve calculations: `indemnity = min(claimed_amount, limit) - deductible`, `expense = indemnity * 0.12`, `total = indemnity + expense`.
11. **Settlement**: Settlement adjudication with recommended, approved, deductible applied, copay applied, and net settlement amounts.

### 3.2 Five Supporting Audit & History Entities

1. **ClaimStatusHistory**: Append-only status transition log recording old status, new status, change reason, and timestamp.
2. **AuditEvent**: Enterprise immutable change-log tracking `entity_type`, `entity_id`, `action`, `state_before`, `state_after`, `actor_type`, and `actor_id`.
3. **AdjusterAssignment**: Historical record of adjuster assignments and reassignments with active flags.
4. **DocumentRequest**: Missing evidence request records generated when required documents are missing (NEG-04).
5. **SettlementPayment**: Disbursement transaction records enforcing unique payment references and duplicate payment prevention (blocking double payouts with HTTP 409).

---

## 4. Business Rules Engine (`app/rules/`)

Business rules are implemented as pure, stateless functions decoupled from database sessions and HTTP frameworks:

1. **Eligibility Rules** (`eligibility_rules.py`):
   - Policy status check: rejects `EXPIRED`, `CANCELLED`, `SUSPENDED` policies (NEG-01).
   - Occurrence date check: incident date must fall within `[policy.effective_date, policy.expiration_date]`.
   - Coverage verification: claim type must map to an active coverage clause without matching exclusion clauses (NEG-02).
   - Timely filing: claim report date must be within 30 days of incident date (NEG-03).
2. **Document Verification Rules** (`document_rules.py`):
   - Mandatory document completeness per claim type (NEG-04).
   - Generates `DocumentRequest` records for missing mandatory items.
3. **Financial & Reserve Rules** (`financial_rules.py`):
   - Reserve calculation: standard indemnity reserve and 12% expense ratio reserve.
   - Settlement calculation: applies deductible first, then copay percentage, and caps net settlement at coverage limit (NEG-05).
   - Auto-approval threshold ($2,500) vs. supervisor review requirement ($50,000).
4. **Fraud & Anomaly Rules** (`fraud_rules.py`):
   - Duplicate claim detection (same customer, incident, or claimed items within 90 days).
   - Filing lag velocity anomalies (filing on day 29/30).
   - Suspended customer policy filings (NEG-06).

---

## 5. Workflow State Machine (`app/workflows/`)

The claim lifecycle follows a strict finite state machine:

```
[SUBMITTED] ──► [UNDER_REVIEW] ──► [PENDING_DOCS] (if missing required docs)
                       │                 │
                       │ (all docs ok)   │ (docs submitted)
                       ▼                 ▼
                [UNDER_REVIEW] ──► [EVALUATING]
                                         │
                  ┌──────────────────────┼──────────────────────┐
                  ▼                      ▼                      ▼
             [APPROVED]             [REJECTED]             [FLAGGED]
                  │                      │                      │
                  ▼                      ▼                      ▼
             [SETTLED]              [CLOSED]               [INVESTIGATION]
                  │
                  ▼
              [CLOSED]
```

Invalid transitions (e.g. attempting to pay a `REJECTED` or `SUBMITTED` claim directly) raise `InvalidStateTransitionError` and are rejected with HTTP 400.

---

## 6. REST API Architecture (`app/api/v1/`)

Mounted under `/api/v1` with interactive OpenAPI documentation at `/api/v1/docs` and Redoc at `/api/v1/redoc`.

### 6.1 Route Reconciliation & Path Inventory

The API exposes **33 unique OpenAPI paths** and **36 HTTP method+path operations**:

- 3 paths support two HTTP methods:
  1. `/api/v1/claims` (`GET` list claims, `POST` intake claim)
  2. `/api/v1/claims/{claim_id}/documents` (`GET` list documents, `POST` attach document)
  3. `/api/v1/claims/{claim_id}/document-requests` (`GET` list requests, `POST` create request)
- Documented Aliases for developer convenience and RESTful compliance:
  1. `GET /api/v1/claims/{claim_id}/audit` -> alias for `GET /api/v1/claims/{claim_id}/audit-trail`
  2. `PATCH /api/v1/documents/{document_id}/verification` -> RESTful alias for `POST /api/v1/documents/{document_id}/verify`
  3. `POST /api/v1/settlements/{settlement_id}/pay` -> alias for `POST /api/v1/settlements/{settlement_id}/disburse`
  4. `GET /health` -> root-level probe alias for `GET /api/v1/health`

### 6.2 Complete Endpoints Matrix

| Method | Path | Summary | Success Status | Schema Input / Output |
|---|---|---|---|---|
| `GET` | `/health` | Global health & DB/Redis probe | `200 OK` / `503` | `HealthResponse` |
| `GET` | `/api/v1/health` | API v1 readiness & DB/Redis probe | `200 OK` / `503` | `HealthResponse` |
| `GET` | `/api/v1/customers` | List customers (paginated, search, KYC, risk) | `200 OK` | `PaginatedResponse[CustomerResponse]` |
| `GET` | `/api/v1/customers/{id}` | Customer detail profile | `200 OK` | `CustomerResponse` |
| `GET` | `/api/v1/policies` | List policies (paginated, type, status, customer) | `200 OK` | `PaginatedResponse[PolicyResponse]` |
| `GET` | `/api/v1/policies/{id}` | Policy detail with eager coverages | `200 OK` | `PolicyResponse` |
| `GET` | `/api/v1/policies/{id}/coverages` | List coverages attached to policy | `200 OK` | `list[CoverageResponse]` |
| `GET` | `/api/v1/claims` | List claims (paginated, status, type, customer, policy) | `200 OK` | `PaginatedResponse[ClaimResponse]` |
| `POST` | `/api/v1/claims` | Submit new claim (Intake) | `201 Created` | `ClaimIntakeRequest` -> `ClaimResponse` |
| `GET` | `/api/v1/claims/{id}` | Retrieve claim details | `200 OK` | `ClaimResponse` |
| `POST` | `/api/v1/claims/{id}/process` | Run end-to-end automated workflow | `200 OK` | `ClaimProcessingResultResponse` |
| `POST` | `/api/v1/claims/{id}/reassess` | Reassess claim preserving history | `200 OK` | `ClaimProcessingResultResponse` |
| `GET` | `/api/v1/claims/{id}/assessments` | Retrieve append-only assessment history | `200 OK` | `list[AssessmentResponse]` |
| `GET` | `/api/v1/claims/{id}/history` | Retrieve claim status progression history | `200 OK` | `list[ClaimStatusHistoryResponse]` |
| `GET` | `/api/v1/claims/{id}/audit-trail` & `/audit` | Retrieve full chronological audit log | `200 OK` | `list[AuditEventResponse]` |
| `POST` | `/api/v1/claims/{id}/documents` | Attach evidentiary document | `201 Created` | `DocumentCreateRequest` -> `DocumentResponse` |
| `GET` | `/api/v1/claims/{id}/documents` | List attached documents | `200 OK` | `list[DocumentResponse]` |
| `POST` | `/api/v1/documents/{id}/verify` & `PATCH .../verification` | Verify or reject document | `200 OK` | `DocumentVerifyRequest` -> `DocumentResponse` |
| `GET` | `/api/v1/claims/{id}/document-requests` | List missing evidence requests | `200 OK` | `list[DocumentRequestResponse]` |
| `POST` | `/api/v1/claims/{id}/document-requests` | Create manual document request | `201 Created` | `DocumentRequestCreate` -> `DocumentRequestResponse` |
| `GET` | `/api/v1/adjusters` | List adjusters (paginated, specialization, status) | `200 OK` | `PaginatedResponse[AdjusterResponse]` |
| `GET` | `/api/v1/adjusters/{id}` | Adjuster profile & capacity | `200 OK` | `AdjusterResponse` |
| `GET` | `/api/v1/claims/{id}/adjustments` | Adjuster assignment history for claim | `200 OK` | `list[AdjusterAssignmentResponse]` |
| `GET` | `/api/v1/assessments/{id}` | Eligibility assessment by ID | `200 OK` | `AssessmentResponse` |
| `GET` | `/api/v1/reserves/{id}` | Reserve calculation record by ID | `200 OK` | `ReserveResponse` |
| `GET` | `/api/v1/claims/{id}/reserves` | List reserve revisions for claim | `200 OK` | `list[ReserveResponse]` |
| `GET` | `/api/v1/settlements/{id}` | Settlement recommendation details by ID | `200 OK` | `SettlementResponse` |
| `GET` | `/api/v1/claims/{id}/settlements` | List settlement recommendations for claim | `200 OK` | `list[SettlementResponse]` |
| `POST` | `/api/v1/claims/{id}/settlements/recommend` | Generate settlement recommendation | `201 Created` | `SettlementResponse` |
| `POST` | `/api/v1/settlements/{id}/approve` | Supervisor approval of settlement | `200 OK` | `SettlementApproveRequest` -> `SettlementResponse` |
| `POST` | `/api/v1/settlements/{id}/disburse` & `/pay` | Disburse payment (Duplicate blocked) | `201 Created` / `409` | `SettlementDisburseRequest` -> `SettlementPaymentResponse` |
| `GET` | `/api/v1/audit-events` | System-wide audit log (paginated, filtered) | `200 OK` | `PaginatedResponse[AuditEventResponse]` |

---

## 7. Containerization & Deployment Architecture

The application is fully containerized using a multi-service Docker Compose topology:

### 7.1 Multi-Stage Dockerfile Architecture

```
[ Stage 1: Builder ]
  - Base Image: python:3.12-slim
  - Binary Copy: ghcr.io/astral-sh/uv:0.6.5 -> /bin/uv
  - Workdir: /app
  - Dependency Installation: uv sync --frozen --no-dev
  - Source Copy: app/, scripts/, alembic/, data/synthetic/

[ Stage 2: Final Runtime ]
  - Base Image: python:3.12-slim
  - System Dependencies: curl, libpq5
  - Non-root User: appuser:appuser (UID 1000, GID 1000)
  - Virtual Environment: Copied from /app/.venv
  - Application Code: Copied to /app owned by appuser
  - HEALTHCHECK: Probes http://localhost:8000/health (interval: 10s, timeout: 5s, retries: 3)
  - Execution CMD: uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 7.2 Docker Compose Multi-Service Topology

`docker-compose.yml` orchestrates three containerized services:

1. **`db`** (`postgres:16-alpine`):
   - Healthcheck: `pg_isready -U postgres -d claims_db` (interval: 5s, timeout: 5s, retries: 5)
   - Volume: `postgres_data:/var/lib/postgresql/data` (persistent database storage)
   - Network: `claims_network`
2. **`redis`** (`redis:7-alpine`):
   - Healthcheck: `redis-cli ping` (interval: 5s, timeout: 3s, retries: 5)
   - Volume: `redis_data:/data` (persistent cache and append-only file)
   - Network: `claims_network`
3. **`api`** (FastAPI backend):
   - Builds from `Dockerfile`
   - `depends_on`:
     - `db` (`condition: service_healthy`)
     - `redis` (`condition: service_healthy`)
   - Network: `claims_network`
   - Exposed Port: `8000:8000`

---

## 8. Redis Integration & Fail-Safe Graceful Degradation

Redis provides high-performance ephemeral caching and temporary session/rate-limiting state:

- **Connection Pool**: Singleton managed in `app/core/redis.py` with connect timeout of 1.0s.
- **Fail-Safe Design**: Insurance claim operations must never block or crash if caching infrastructure is unavailable.
- **Health Probing**: `check_redis_health() -> tuple[bool, str]` safely queries Redis. If Redis is down, it returns `(False, "disconnected")` without raising unhandled exceptions.
- **Cache Fallback**: `cache_get`, `cache_set`, and `cache_delete` catch all connection errors and fail open (returning `None` or `False`).
- **Health Probes**: The `/health` endpoint checks both PostgreSQL (`SELECT 1`) and Redis (`redis-cli ping`). If PostgreSQL is healthy, `/health` returns HTTP 200 OK with `database: "connected"` and `redis: "disconnected"`.

---

## 9. Synthetic Dataset Loader (`scripts/load_dataset.py`)

A high-performance relational database loader capable of populating PostgreSQL or SQLite databases:

- **Strict Foreign-Key Dependency Order**:
  - Level 1: `customers`, `adjusters`, `incidents`
  - Level 2: `policies`
  - Level 3: `coverages`, `claims`
  - Level 4: `claim_items`, `documents`, `document_requests`, `assessments`, `reserves`, `settlements`, `adjuster_assignments`, `audit_events`, `claim_status_history`
  - Level 5: `settlement_payments`
- **Idempotency**: Queries existing primary keys prior to batch insertion; duplicate records are safely skipped.
- **Conflict Handling**: Implements chunked batch insertion (500 rows/batch) with automated fallback to row-by-row isolation on conflict.
- **Truncation Mode**: `--truncate` cleans all 16 tables in reverse foreign key order before reloading.
- **Dry-Run Mode**: `--dry-run` parses and validates datasets without committing database transactions.
- **Performance**: Loads all 22,933 records across 16 tables in ~1.1 seconds.
