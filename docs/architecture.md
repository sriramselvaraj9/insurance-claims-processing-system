# System Architecture Specification: Insurance Claims Processing System

**Assessment Provider**: YottaFlex AI Recruitment Technical Assessment  
**System Architecture**: Clean Layered Decoupled Enterprise Architecture  
**Target Environment**: Python 3.12+, FastAPI, PostgreSQL, SQLAlchemy 2.x, Alembic, Docker  
**Document Version**: 1.0.0  

---

## 1. High-Level Architectural Overview

The system is structured around the classic **Layered Repository-Service Architecture**, strictly enforcing unidirectional dependencies and clear separation of concerns:

```
[ HTTP Requests / API Clients ]
               │
               ▼
┌──────────────────────────────────────────────┐
│       API Layer (FastAPI Routers)            │  <-- app/api/v1/
│  - Endpoint routing                          │
│  - Request validation (Pydantic v2)          │
│  - Response formatting & HTTP error mapping  │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│       Service Orchestration Layer            │  <-- app/services/
│  - Business use case coordination           │
│  - Transaction boundaries                    │
│  - Audit event publishing                    │
│  - Exception logging & dispatch              │
└──────────────┬───────────────────────────────┘
               │
       ┌───────┴───────────────────────┐
       ▼                               ▼
┌───────────────────────────┐   ┌───────────────────────────┐
│   Business Rules Engine   │   │   Workflow State Machine  │  <-- app/rules/ &
│  - Stateless & pure       │   │  - Validates transitions  │      app/workflows/
│  - Deterministic checks   │   │  - Rejects illegal flows  │
│  - Financial arithmetic   │   │  - Emits lifecycle events │
└───────────────────────────┘   └───────────────────────────┘
               │                               │
               └───────────────┬───────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────┐
│       Repository Data Access Layer           │  <-- app/repositories/
│  - Encapsulates all SQLAlchemy 2.x queries   │
│  - No business logic inside repositories     │
│  - Provides clean CRUD and domain filters    │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│       PostgreSQL Database / Storage          │  <-- app/models/ & PostgreSQL
│  - Strongly typed schema & constraints       │
│  - Foreign key referential integrity         │
│  - Alembic versioned migrations              │
└──────────────────────────────────────────────┘
```

---

## 2. Responsibilities by Architectural Layer

### 2.1 API Layer (`app/api/`)
- **Responsibilities**:
  - Accept and decode incoming HTTP requests.
  - Deserialize and validate request bodies using Pydantic v2 schemas (`app/schemas/`).
  - Resolve dependency injection parameters (e.g., database session `db: Session = Depends(get_db)`).
  - Invoke the appropriate business service method.
  - Catch domain exceptions and map them to standard HTTP status codes (`400 Bad Request`, `404 Not Found`, `409 Conflict`, `422 Unprocessable Entity`).
  - Return typed responses with serialized output models.
- **Strict Boundary Rules**:
  - **Zero direct database queries** in routers. No `db.query()`, `select()`, or raw SQL inside endpoints.
  - Routers only interact with Services.

### 2.2 Service Orchestration Layer (`app/services/`)
- **Responsibilities**:
  - Encapsulate application use cases (e.g., `ClaimsService`, `PolicyService`, `AdjusterService`, `ReserveService`, `SettlementService`, `AuditService`, `ExceptionService`).
  - Coordinate multi-step operations (e.g., intake claim -> verify policy -> trigger eligibility -> compute reserve -> assign adjuster).
  - Manage database transaction boundaries (`commit()`, `rollback()`).
  - Trigger audit trail recordings via `AuditService` upon state mutations.
  - Register exceptions in `ExceptionLog` when business rules fail.
- **Strict Boundary Rules**:
  - Business rules themselves are delegated to pure functions in `app/rules/`.
  - Database persistence is delegated strictly to `app/repositories/`.

### 2.3 Business Rules Engine (`app/rules/`)
- **Responsibilities**:
  - Pure, deterministic, side-effect-free evaluation of business logic.
  - Submodules:
    - `eligibility_rules.py`: Evaluates policy active window (NEG-01), covered perils (NEG-02), timely notice (NEG-03), and exclusion criteria.
    - `document_rules.py`: Evaluates mandatory document completeness matrix per claim type (NEG-04).
    - `financial_rules.py`: Computes indemnity reserve, expense reserve, total reserve, deductibles, copays, and caps at policy limits (NEG-05).
    - `fraud_rules.py`: Flags duplicate claim submissions within 7 days, suspended policies, and high-risk anomalies (NEG-06).
- **Strict Boundary Rules**:
  - Functions in `app/rules/` **do not access the database or external APIs**.
  - All input data is passed in as pure domain models or Pydantic schemas, and outputs are structured evaluation results.

### 2.4 Workflow & State Machine Layer (`app/workflows/`)
- **Responsibilities**:
  - Enforce explicit state graphs for entity lifecycles:
    - `ClaimLifecycle`: `SUBMITTED` -> `UNDER_REVIEW` / `INFO_REQUESTED` -> `ELIGIBLE` / `INELIGIBLE` -> `ADJUSTER_ASSIGNED` -> `RESERVE_CALCULATED` -> `SETTLEMENT_RECOMMENDED` -> `APPROVED` / `REJECTED` -> `SETTLED` -> `CLOSED`.
    - `PolicyLifecycle`: `DRAFT` -> `ACTIVE` -> `SUSPENDED` / `EXPIRED` / `CANCELLED`.
    - `DocumentVerification`: `PENDING` -> `VERIFIED` / `REJECTED`.
    - `SettlementLifecycle`: `PROPOSED` -> `SUPERVISOR_REVIEW` -> `APPROVED` / `REJECTED` -> `DISBURSED`.
  - Throw explicit `InvalidStateTransitionException` if an illegal transition is attempted.

### 2.5 Repository Layer (`app/repositories/`)
- **Responsibilities**:
  - Encapsulate all SQLAlchemy 2.0 query construction (`select()`, `update()`, `delete()`, join filters).
  - Abstract database access behind a clean Python interface.
  - Base class `BaseRepository[ModelType]` provides standard operations: `get()`, `get_by_id()`, `list()`, `create()`, `update()`, `delete()`.
  - Specialized repositories provide domain queries (e.g., `ClaimRepository.find_potential_duplicates()`, `AdjusterRepository.find_least_loaded_adjuster()`).
- **Strict Boundary Rules**:
  - No business decision logic inside repositories. Repositories only fetch, persist, and delete.

### 2.6 Persistence Layer (`app/models/` & PostgreSQL)
- **Responsibilities**:
  - SQLAlchemy 2.0 Declarative ORM models representing the 11 core domain tables.
  - Strict database-level constraints: foreign keys, cascading rules, unique indexes, and non-null constraints.
  - Alembic migrations provide version-controlled, auditable DDL changes.

---

## 3. Key Design Decisions & Trade-Offs

1. **SQLAlchemy 2.0 Mapped Syntax**:
   - *Decision*: Use SQLAlchemy 2.0 `Mapped[...]` and `mapped_column(...)` typing annotations.
   - *Rationale*: Guarantees complete static type checking with Mypy and IDE autocomplete, eliminating runtime schema mismatch bugs.
2. **Fixed-Point Decimal Arithmetic for Financials**:
   - *Decision*: Use Python's built-in `decimal.Decimal` and SQL `Numeric(12, 2)` / `Numeric(10, 2)` for all monetary values.
   - *Rationale*: Floating-point representations (`float`) introduce precision drift (e.g. `0.1 + 0.2 != 0.3`), which is unacceptable in insurance reserve and settlement calculations.
3. **Stateless Rules Engine with Immutable Result Objects**:
   - *Decision*: Decouple rule evaluation from database state.
   - *Rationale*: Allows the exact same rules to be executed both within the FastAPI web application and inside the offline evaluation/synthetic data benchmarking script (`scripts/evaluate_rules_engine.py`) without mocking a database.
4. **Comprehensive Append-Only Audit Trail**:
   - *Decision*: Record an `AuditEvent` on every entity state transition with `state_before`, `state_after`, `actor_type`, and `timestamp`.
   - *Rationale*: Insurance claims processing requires strict statutory auditability and non-repudiation for reinsurance and regulatory compliance.
5. **Deterministic Synthetic Data Harness**:
   - *Decision*: Generator uses deterministic random seeds (`Seed=42`) with parameterized log-normal loss distributions and controlled fault injection.
   - *Rationale*: Enables reproducible benchmark runs, CI testing, and evaluation metrics without reliance on real-world confidential customer PII.

---

## 4. Architectural Assumptions & Operational Constraints

1. **Database Deployment**: Production and local development assume PostgreSQL 16 via Docker Compose. Unit test execution uses in-memory SQLite for instant, zero-dependency CI verification.
2. **Single-Currency Processing**: All monetary calculations assume a single default currency (USD). Multi-currency conversion is out of scope for the current assessment baseline.
3. **Document File Storage**: Document payloads are represented by metadata (filename, path, MIME type, SHA-256 hash). Binary file storage is mocked as file URIs rather than requiring an active AWS S3 / MinIO cluster.
4. **Synchronous Core Processing with Async Extensibility**: Business rules and database operations are executed synchronously within request transactions to guarantee immediate atomic consistency for claim intake and adjudication.
