# System Architecture Specification: Insurance Claims Processing System

**Assessment Provider**: YottaFlex AI Recruitment Technical Assessment  
**System Architecture**: Clean Layered Decoupled Enterprise Architecture  
**Target Environment**: Python 3.12+, FastAPI, PostgreSQL 16, SQLAlchemy 2.x, Alembic, Docker, uv  
**Document Version**: 3.0.0 (Phase 3 Core Processing Engine Baseline)  

---

## 1. High-Level Architectural Overview

The system is structured around the **Layered Repository-Service Architecture**, strictly enforcing unidirectional dependencies, clear separation of concerns, and isolated database access:

```
[ HTTP Requests / API Clients / CLI Scripts ]
                       │
                       ▼
┌──────────────────────────────────────────────────────────┐
│              API Layer (FastAPI Routers)                 │  <-- app/api/v1/
│  - Request validation & serialization (Pydantic v2)      │
│  - HTTP error translation (400, 404, 409, 422)           │
│  - Dependency injection (Service resolution)             │
└──────────────────────────┬───────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────┐
│             Service Orchestration Layer                  │  <-- app/services/
│  - Use-case coordination (Claims, Policies, Settlements) │
│  - Transaction boundaries & commit/rollback              │
│  - Audit event publishing & exception dispatch           │
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
└──────────────────────────┬───────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────┐
│            PostgreSQL 16 Database / Storage              │  <-- app/models/ & PostgreSQL
│  - 11 Core Entities + 5 Supporting Audit/History Tables  │
│  - Strict FKs, CheckConstraints, and Indexes             │
│  - Versioned Alembic migrations                          │
└──────────────────────────────────────────────────────────┘
```

---

## 2. Responsibilities by Architectural Layer

### 2.1 API Layer (`app/api/`)
- Accept and deserialize HTTP payloads into validated Pydantic v2 schemas (`app/schemas/`).
- Enforce OpenAPI documentation specifications.
- Delegate use-case logic to services.
- **Strict Constraint**: Zero direct database queries (`db.query`, `select()`, or raw SQL) in routers.

### 2.2 Service Orchestration Layer (`app/services/`)
- Coordinate domain workflows across multiple repositories (e.g., Claim intake -> Incident linking -> Coverage check -> Reserve calculation -> Adjuster assignment).
- Manage database transaction boundaries (`commit()`, `rollback()`).
- Append immutable audit logs via `AuditRepository` upon state mutations.
- Triage business exceptions into `ExceptionLog`.
- **Strict Constraint**: Services delegate pure business rule calculations to `app/rules/` and all persistence to `app/repositories/`.

### 2.3 Business Rules Engine (`app/rules/`)
- Stateless, pure mathematical and logical evaluators without database or network I/O.
- Implements:
  - Six mandatory negative scenarios (`NEG-01` to `NEG-06`).
  - Reserve calculations (Indemnity + Expense reserve).
  - Settlement net amounts (Deductibles and Copays).
- Reusable across both online API flows and offline batch evaluation scripts.

### 2.4 Workflow & State Machine Layer (`app/workflows/`)
- Finite State Machine (FSM) enforcing legal state progressions:
  - `ClaimLifecycle`: `SUBMITTED` -> `UNDER_REVIEW` -> `ELIGIBLE` / `INELIGIBLE` -> `ADJUSTER_ASSIGNED` -> `RESERVE_CALCULATED` -> `SETTLEMENT_RECOMMENDED` -> `APPROVED` -> `SETTLED` -> `CLOSED`.
  - Rejects illegal transitions (e.g. `SUBMITTED` -> `SETTLED`) by raising `InvalidStateTransitionError`.

### 2.5 Repository Data Access Layer (`app/repositories/`)
- Encapsulates all SQLAlchemy 2.0 query construction (`select()`, `insert()`, `update()`, `join()`).
- Provides clean Python interfaces: `create()`, `get_by_id()`, `list()`, `update()`, `delete()`, `count()`.
- Specialized repository methods (e.g., `ClaimRepository.find_potential_duplicates()`, `AdjusterRepository.find_least_loaded_adjuster()`, `IncidentRepository.find_duplicate_incident()`).
- **Strict Constraint**: Repositories contain data access logic only. No eligibility, fraud, or settlement decisions are made within repositories.

### 2.6 Persistence Layer (`app/models/` & PostgreSQL 16)
- Strongly typed SQLAlchemy 2.0 Declarative models (`Mapped[...]`, `mapped_column(...)`).
- Database constraints: Foreign keys, uniqueness constraints, index definitions, and check constraints for non-negative financials and valid date ranges.
- Managed by versioned Alembic migrations.

---

## 3. Database Architecture & Entity Relationships

The schema consists of **11 core business entities** and **5 supporting history/audit tables**:

```
+------------------+       1:N       +------------------+       1:N       +------------------+
|     Customer     | --------------< |      Policy      | --------------< |     Coverage     |
+------------------+                 +------------------+                 +------------------+
         |                                    |                                     |
         | 1:N                                | 1:N                                 | 1:N (optional)
         v                                    v                                     v
+--------------------------------------------------------------------------------------------+
|                                           Claim                                            |
+--------------------------------------------------------------------------------------------+
   |          |              |              |                 |               |
   | 1:N      | 1:N          | 1:N          | 1:N             | 1:N           | N:1
   v          v              v              v                 v               v
+----------++----------+   +----------+   +----------+   +----------------+ +----------+
|ClaimItem || Document |   |Assessment|   | Reserve  |   |   Settlement   | | Incident |
+----------++----------+   +----------+   +----------+   +----------------+ +----------+
                  |                                               |
                  | 1:N                                           | 1:N
                  v                                               v
            +---------------+                              +---------------+
            |DocumentRequest|                              |SettlementPaym.|
            +---------------+                              +---------------+

Supporting Global Audit Tables:
+--------------------+   +--------------------+   +--------------------+
|     AuditEvent     |   | ClaimStatusHistory |   | AdjusterAssignment |
+--------------------+   +--------------------+   +--------------------+
```

### Detailed Relationship Specifications
1. **Customer**:
   - `1:N Policy`: One customer holds multiple policies.
   - `1:N Claim`: One customer can submit multiple claims across policies.
2. **Policy**:
   - `N:1 Customer`: Every policy references a valid customer.
   - `1:N Coverage`: A policy contains multiple coverage clauses (e.g. Collision, Comprehensive, Bodily Injury).
   - `1:N Claim`: A policy can experience multiple claims over its active tenure.
3. **Coverage**:
   - `N:1 Policy`: Every coverage belongs to one policy.
   - Specifies coverage type, limit, deductible, copay percentage, exclusions, and active period.
4. **Incident**:
   - `1:N Claim`: Multiple claims may reference the same physical incident (e.g. multi-vehicle accident or catastrophe event).
   - Encapsulates occurrence date, incident type, location, and duplicate incident detection attributes.
5. **Claim**:
   - `N:1 Customer` and `N:1 Policy`.
   - `N:1 Incident`: Every claim references an incident.
   - `1:N ClaimItem`: Itemized breakdown of loss components.
   - `1:N Document`: Evidentiary files linked to the claim.
   - `1:N Assessment`: Historical audit of all eligibility evaluations.
   - `1:N Reserve`: Preliminary reserve calculations and revisions.
   - `1:N Settlement`: Settlement proposals and resolutions.
   - `1:N ClaimStatusHistory`: Full audit trail of status transitions.
6. **ClaimItem**:
   - `N:1 Claim`: Belongs to a claim. Contains description, quantity, unit amount, and total amount.
   - `N:1 Coverage` (Optional): Links the item to a specific policy coverage clause.
7. **Document & DocumentRequest**:
   - `Document`: Belongs to a claim. Tracks filename, MIME type, file size, SHA-256 checksum, and verification status.
   - `DocumentRequest`: Missing document notices generated when mandatory evidentiary files are absent.
8. **Adjuster & AdjusterAssignment**:
   - `Adjuster`: Independent entity with specialization, active claims count, capacity limits, and availability.
   - `AdjusterAssignment`: Historical assignment record tracking when adjusters are assigned or reassigned to claims.
9. **Assessment**:
   - `N:1 Claim`: Stores eligibility assessment results, rule breakdown, reasons, and timestamps. Supports reassessment without deleting prior records.
10. **Reserve**:
    - `N:1 Claim`: Stores indemnity reserve, expense reserve, total reserve, calculation method, and version history.
11. **Settlement & SettlementPayment**:
    - `Settlement`: Tracks recommended, approved, and net settlement amounts.
    - `SettlementPayment`: Payment disbursement audit tracking payment reference, disbursement date, amount, and payment status, preventing duplicate disbursements.

---

## 4. Deterministic String-Based ID Conventions

All entities utilize immutable, string-based deterministic identifiers:

| Entity | ID Format | Example |
| :--- | :--- | :--- |
| **Customer** | `CUST-YYYY-NNNNNN` | `CUST-2026-000001` |
| **Policy** | `POL-<PRODUCT>-YYYY-NNNNNN` | `POL-AUTO-2026-000001` |
| **Coverage** | `COV-<POLICY_ID>-NNN` | `COV-POL-AUTO-2026-000001-001` |
| **Incident** | `INC-YYYY-NNNNNN` | `INC-2026-000001` |
| **Claim** | `CLM-YYYY-NNNNNN` | `CLM-2026-000001` |
| **ClaimItem** | `ITM-<CLAIM_ID>-NNN` | `ITM-CLM-2026-000001-001` |
| **Document** | `DOC-<CLAIM_ID>-NNN` | `DOC-CLM-2026-000001-001` |
| **DocumentRequest** | `REQ-<CLAIM_ID>-NNN` | `REQ-CLM-2026-000001-001` |
| **Adjuster** | `ADJ-YYYY-NNNNNN` | `ADJ-2026-000001` |
| **AdjusterAssignment**| `ASN-<CLAIM_ID>-NNN` | `ASN-CLM-2026-000001-001` |
| **Assessment** | `ASM-<CLAIM_ID>-NNN` | `ASM-CLM-2026-000001-001` |
| **Reserve** | `RES-<CLAIM_ID>-NNN` | `RES-CLM-2026-000001-001` |
| **Settlement** | `SET-<CLAIM_ID>-NNN` | `SET-CLM-2026-000001-001` |
| **SettlementPayment** | `PAY-<SETTLEMENT_ID>-NNN` | `PAY-SET-CLM-2026-000001-001-001` |
| **AuditEvent** | `AUD-YYYY-NNNNNN` | `AUD-2026-000001` |
| **ClaimStatusHistory** | `CSH-<CLAIM_ID>-NNN` | `CSH-CLM-2026-000001-001` |

---

## 5. Transaction & Audit History Strategy

1. **Explicit Session & Transaction Boundaries**:
   - Repositories accept an active SQLAlchemy `Session` instance.
   - Services control transaction commits and rollbacks to guarantee atomic multi-table writes.
2. **Immutable Audit Trails**:
   - The system never mutates historical assessment, reserve, assignment, or payment records.
   - When a claim is reassessed, a new `Assessment` record is appended with an incremented sequence.
   - Status changes append to `ClaimStatusHistory` and emit a structured `AuditEvent`.
3. **Non-Cascading Deletes**:
   - Core operational entities (Claims, Assessments, Reserves, Settlements, Audit logs) reject cascade deletion. Deleting an active claim is blocked to preserve statutory compliance.

---

## 6. Migration Strategy

- Schema changes are managed exclusively via **Alembic**.
- `Base.metadata.create_all()` is restricted to isolated in-memory unit tests.
- Initial migration revision `001_initial_schema.py` defines all tables, columns, constraints, foreign keys, and indexes, with fully tested `upgrade()` and `downgrade()` routines.

---

## 7. Pure Business Rules Engine Specification (`app/rules/`)

The rules engine is implemented as pure, stateless Python functions decoupled from ORM and database dependencies:

1. **Policy Rules (`policy_rules.py`)**:
   - `POLICY_001`: Active Policy Status (must be `ACTIVE`).
   - `POLICY_002`: Policy Inception / Expiration Validity (`effective_date <= incident_date <= expiration_date`).
   - `POLICY_003`: Cancellation Date check (incident cannot occur post-cancellation).
   - `POLICY_004`: Suspension Window check (loss cannot fall within temporary suspension interval).
   - `POLICY_005`: Policy Existence check.
   - `POLICY_006`: Customer Ownership check (`claim.customer_id == policy.customer_id`).

2. **Coverage Rules (`coverage_rules.py`)**:
   - `COVERAGE_001`: Peril Coverage Existence (claim type maps to active coverage type).
   - `COVERAGE_002`: Coverage Clause Active Status (`is_active == True`).
   - `COVERAGE_003`: Policy Exclusion Clauses (rejects claims matching excluded peril strings).
   - `COVERAGE_004`: Limit and Deductible Resolution.

3. **Document Rules (`document_rules.py`)**:
   - `DOCUMENT_001`: Mandatory Evidence Matrix per claim type (e.g. `POLICE_REPORT` + `REPAIR_ESTIMATE` for auto collision).
   - `DOCUMENT_002`: Document Verification Status check (`VERIFIED`).
   - `DOCUMENT_003`: Missing Document Request Emission.

4. **Duplicate & Anomaly Rules (`duplicate_rules.py`)**:
   - `DUPLICATE_001`: Identical Claim Check (same policy, incident, and claimed amount within $1.00).
   - `DUPLICATE_002`: Duplicate Incident Check (suspected duplicate casualty at same time/location).
   - `DUPLICATE_003`: Rapid Multiple Filings (claims under same policy within 7 days).

5. **Fraud Rules (`fraud_rules.py`)**:
   - `FRAUD_001`: Suspicious Claim Amount (> 200% of coverage limit or > $100k without prior history).
   - `FRAUD_002`: Filing Lag (> 30 days between incident occurrence and reporting).
   - `FRAUD_003`: Statutory Notice Window (> 30 days statutory late notice cutoff).
   - `FRAUD_004`: Policy Age / Filing Near Inception.
   - `FRAUD_005`: Suspended Policy Filing.
   - *Architecture Note*: Fraud flags route claims to `MANUAL_REVIEW`, not auto-rejection.

6. **Deterministic Decision Precedence (`eligibility_rules.py`)**:
   - **Step 1**: Customer Ownership Mismatch -> `INELIGIBLE` (`POLICY_OWNERSHIP_MISMATCH`).
   - **Step 2**: Policy Inception, Expiration, Cancellation, Suspension -> `INELIGIBLE` (`EXPIRED_POLICY` / `SUSPENDED_POLICY`).
   - **Step 3**: Uncovered Peril -> `INELIGIBLE` (`UNCOVERED_PERIL`).
   - **Step 4**: Explicit Exclusion Clause -> `INELIGIBLE` (`POLICY_EXCLUSION`).
   - **Step 5**: Statutory Notice Window Exceeded -> `INELIGIBLE` (`UNTIMELY_FILING`).
   - **Step 6**: Duplicate Claim or Incident / High Fraud Flags -> `MANUAL_REVIEW` (`DUPLICATE_CLAIM` / `SUSPECTED_FRAUD`).
   - **Step 7**: Missing or Unverified Mandatory Documents -> `PENDING_DOCUMENTS` (`MISSING_MANDATORY_DOCUMENTS`).
   - **Step 8**: All Validations Passed -> `ELIGIBLE`.

---

## 8. Service Orchestration Layer (`app/services/`)

The service layer coordinates domain use-cases, applies transaction control, and manages cross-cutting audit records:

- `ClaimIntakeService`: Entry point for new claims. Validates customer, policy, incident, line item summation, and duplicate prevention.
- `PolicyValidationService`: Evaluates policy validity against incident occurrence timestamps.
- `CoverageService`: Resolves applicable coverage, limit, deductible, and copay percentage.
- `DocumentService`: Verifies document completeness, emits missing evidence requests, and records verification approvals.
- `DuplicateDetectionService`: Queries database for identical submissions and flags potential fraud duplicates.
- `FraudService`: Calculates filing lag, query historical frequency, and evaluates deterministic fraud indicators.
- `EligibilityService`: Executes deterministic eligibility precedence, appends immutable `Assessment` records, and emits audit logs.
- `AdjusterService`: Matches claim type to adjuster specialization and selects the qualified adjuster with lowest caseload.
- `ReserveService`: Computes formulaic reserves: `indemnity = min(claimed_amount, limit) - deductible`, `expense = indemnity * 0.12`, `total = indemnity + expense`.
- `SettlementService`: Recommends net settlements capped at coverage limits: `(min(loss, limit) - deductible) * (1 - copay)`. Supports supervisor approval and executes disbursement payments with strict duplicate payment prevention (blocking double payouts with HTTP 409).
- `ClaimsProcessingService`: Master workflow orchestrator driving both initial automated processing and subsequent reassessments.

---

## 9. REST API Layer (`app/api/v1/`)

Mounted under `/api/v1` with OpenAPI documentation at `/api/v1/docs`:

| Method | Path | Summary | Success Status |
|---|---|---|---|
| `POST` | `/api/v1/claims` | Submit new claim (Intake) | `201 Created` |
| `GET` | `/api/v1/claims/{claim_id}` | Retrieve claim details | `200 OK` |
| `POST` | `/api/v1/claims/{claim_id}/process` | Run end-to-end automated workflow | `200 OK` |
| `POST` | `/api/v1/claims/{claim_id}/reassess` | Reassess claim preserving history | `200 OK` |
| `GET` | `/api/v1/claims/{claim_id}/assessments` | Retrieve append-only assessment history | `200 OK` |
| `GET` | `/api/v1/claims/{claim_id}/history` | Retrieve claim status progression history | `200 OK` |
| `GET` | `/api/v1/claims/{claim_id}/audit-trail` | Retrieve full chronological audit log | `200 OK` |
| `POST` | `/api/v1/claims/{claim_id}/documents` | Attach evidentiary document | `201 Created` |
| `GET` | `/api/v1/claims/{claim_id}/documents` | List attached documents | `200 OK` |
| `POST` | `/api/v1/documents/{document_id}/verify` | Verify or reject document | `200 OK` |
| `GET` | `/api/v1/claims/{claim_id}/document-requests` | List missing evidence requests | `200 OK` |
| `GET` | `/api/v1/claims/{claim_id}/settlements` | List settlement recommendations | `200 OK` |
| `POST` | `/api/v1/settlements/{settlement_id}/approve` | Supervisor approval of settlement | `200 OK` |
| `POST` | `/api/v1/settlements/{settlement_id}/disburse` | Disburse payment (Duplicate blocked) | `200 OK` / `409 Conflict` |


