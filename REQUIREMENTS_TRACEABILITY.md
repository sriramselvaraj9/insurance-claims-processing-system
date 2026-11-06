# Requirements Traceability Matrix (RTM)

**Project**: Insurance Claims Processing System  
**Organization**: YottaFlex AI Recruitment Assessment  
**Document Version**: 2.0.0 (Phase 1 Baseline)  

---

## Traceability Schema & Status Legend

- **Status Values**:
  - `VERIFIED`: Implemented and fully verified via automated tests.
  - `IMPLEMENTED`: Model, repository, or schema code created in Phase 1; pending full multi-stage workflow integration.
  - `PLANNED`: Architectural design complete; slated for subsequent phase.

---

## 1. Core Domain Entities & Relationships (All 11 Entities)

| Requirement ID | Original Assessment Requirement | Implemented Models & Repositories | Validation Method | Phase 1 Status |
| :--- | :--- | :--- | :--- | :--- |
| **REQ-ENT-01** | **Customer**: Policyholder master data, contact info, KYC status (`PENDING`, `VERIFIED`, `REJECTED`, `FLAGGED`), risk tier (`LOW`, `MEDIUM`, `HIGH`). | `app/models/customer.py`<br>`app/repositories/customer_repository.py` | Unit test in `tests/unit/test_models.py` & `tests/unit/test_repositories.py` verifying constraints, unique email/customer_number. | `VERIFIED` |
| **REQ-ENT-02** | **Policy**: Multi-line policy contract across Auto, Home, Health, Commercial lines with status lifecycle (`DRAFT`, `ACTIVE`, `SUSPENDED`, `EXPIRED`, `CANCELLED`), effective/expiration dates, premium, deductible. | `app/models/policy.py`<br>`app/repositories/policy_repository.py` | Model check constraint test (`expiration_date > effective_date`, `premium >= 0`), unique policy_number, foreign key to customer. | `VERIFIED` |
| **REQ-ENT-03** | **Coverage**: Specific coverage clauses with limits, deductibles, and coinsurance/copay percentage. | `app/models/coverage.py`<br>`app/repositories/coverage_repository.py` | CheckConstraint tests for `limit > 0`, `0 <= copay <= 100`, `deductible >= 0`, foreign key to policy. | `VERIFIED` |
| **REQ-ENT-04** | **Incident**: Physical casualty occurrence tracking incident type, occurrence date, description, and location metadata; supports duplicate incident detection and multi-claim linkage. | `app/models/incident.py`<br>`app/repositories/incident_repository.py` | Duplicate incident detection test via street/city/occurrence_date queries in `IncidentRepository`. | `VERIFIED` |
| **REQ-ENT-05** | **Claim**: Claim intake records, incident linkage, claimed amounts, estimated losses, and status lifecycle. | `app/models/claim.py`<br>`app/repositories/claim_repository.py` | Foreign key validation (customer, policy, incident), financial non-negative check constraints, duplicate detection query. | `VERIFIED` |
| **REQ-ENT-06** | **ClaimItem**: Itemized breakdown of loss components; references optional coverage clause; stores quantity, unit amount, and total amount. | `app/models/claim_item.py`<br>`app/repositories/claim_item_repository.py` | Quantity and financial value check constraints (`quantity >= 1`, `unit_amount >= 0`, `total_amount >= 0`). | `VERIFIED` |
| **REQ-ENT-07** | **Document**: Evidentiary files linked to claims; tracks filename, MIME type, file size, SHA-256 checksum, and verification status (`PENDING`, `VERIFIED`, `REJECTED`). | `app/models/document.py`<br>`app/repositories/document_repository.py` | SHA-256 validation test, file size positive constraint, verification status transition tests. | `VERIFIED` |
| **REQ-ENT-08** | **Adjuster**: Adjuster profile tracking domain specialization, current active claims count, maximum capacity, and availability status (`ACTIVE`, `ON_LEAVE`, `INACTIVE`). | `app/models/adjuster.py`<br>`app/repositories/adjuster_repository.py` | Capacity check tests (`active_claims_count < max_capacity`), least-loaded adjuster selection test. | `VERIFIED` |
| **REQ-ENT-09** | **Assessment**: Eligibility decisions recording checks (`policy_active`, `incident_covered`, `timely_filing`, `exclusions`, `documents_complete`, `fraud`), decision reasons, and timestamps; supports reassessment. | `app/models/assessment.py`<br>`app/repositories/assessment_repository.py` | Reassessment history test (appending new assessment without deleting prior decision records). | `VERIFIED` |
| **REQ-ENT-10** | **Reserve**: Preliminary reserve calculations storing indemnity reserve, expense reserve (at default 12%), total reserve, calculation method, and version history. | `app/models/reserve.py`<br>`app/repositories/reserve_repository.py` | Arithmetic integrity test (`total_reserve == indemnity + expense`), reserve history retrieval test. | `VERIFIED` |
| **REQ-ENT-11** | **Settlement**: Settlement adjudication tracking recommended, approved, deductible applied, copay applied, and net settlement amounts; payment reference and status. | `app/models/settlement.py`<br>`app/repositories/settlement_repository.py` | Financial non-negative check constraints, supervisor review thresholds, payment relationship tests. | `VERIFIED` |

---

## 2. Supporting History & Audit Entities

| Requirement ID | Supporting Entity | Implemented Models & Repositories | Validation Method | Phase 1 Status |
| :--- | :--- | :--- | :--- | :--- |
| **REQ-AUD-01** | **ClaimStatusHistory**: Complete append-only audit trail of every status transition for every claim. | `app/models/claim_status_history.py`<br>`app/repositories/claim_status_history_repository.py` | Transition history append test asserting zero deletion or in-place overwrite. | `VERIFIED` |
| **REQ-AUD-02** | **AuditEvent**: Immutable enterprise change-log capturing `entity_type`, `entity_id`, `action`, `state_before`, `state_after`, `actor_type`, `actor_id`, and `timestamp`. | `app/models/audit_event.py`<br>`app/repositories/audit_repository.py` | Audit log emission test; verify records are append-only. | `VERIFIED` |
| **REQ-AUD-03** | **AdjusterAssignment**: Adjuster assignment and reassignment audit history. | `app/models/adjuster_assignment.py`<br>`app/repositories/adjuster_assignment_repository.py` | Historical assignment retrieval test; active assignment flag check. | `VERIFIED` |
| **REQ-AUD-04** | **DocumentRequest**: Missing document request tracking for claims with incomplete documentation (NEG-04). | `app/models/document_request.py`<br>`app/repositories/document_request_repository.py` | Open request query test; fulfillment linkage test. | `VERIFIED` |
| **REQ-AUD-05** | **SettlementPayment**: Disbursement transaction records preventing duplicate payments and ensuring limits are respected. | `app/models/settlement_payment.py`<br>`app/repositories/settlement_payment_repository.py` | Unique payment reference test; duplicate payment prevention query. | `VERIFIED` |

---

## 3. Mandatory Negative Scenarios (Database & Constraint Support)

| Scenario ID | Scenario Name | Database Support & Constraints | Planned Rule Engine Module | Status |
| :--- | :--- | :--- | :--- | :--- |
| **NEG-01** | **Expired Policy Filing** | `policies.effective_date` and `policies.expiration_date` stored as Date columns with `CheckConstraint("expiration_date > effective_date")`. | `app/rules/eligibility_rules.py` | Model ready (`VERIFIED`) |
| **NEG-02** | **Uncovered Peril / Policy Exclusion** | `coverages.coverage_type`, `coverages.is_active`, and `coverages.exclusions` (JSON array of excluded perils). | `app/rules/eligibility_rules.py` | Model ready (`VERIFIED`) |
| **NEG-03** | **Untimely Filing / Late Notice** | `claims.reported_date` and `incidents.occurrence_date` stored as UTC timestamps with indexing for fast interval querying. | `app/rules/eligibility_rules.py` | Model ready (`VERIFIED`) |
| **NEG-04** | **Missing Mandatory Documents** | `documents.document_type`, `documents.verification_status`, and `document_requests` table to record missing evidentiary files. | `app/rules/document_rules.py` | Model ready (`VERIFIED`) |
| **NEG-05** | **Excessive Claim Exceeding Limit** | `coverages.coverage_limit` and `claims.claimed_amount` stored as Numeric(12, 2) with positive value check constraints. | `app/rules/financial_rules.py` | Model ready (`VERIFIED`) |
| **NEG-06** | **Suspended Policy / Suspected Fraud** | `policies.status = SUSPENDED`, `ClaimRepository.find_potential_duplicates()` query, and `IncidentRepository.find_duplicate_incident()`. | `app/rules/fraud_rules.py` | Model & Repo ready (`VERIFIED`) |

---

## 4. Engineering Standards & Dependency Management

| Requirement ID | Standard / Requirement | Implementation | Validation Command | Phase 1 Status |
| :--- | :--- | :--- | :--- | :--- |
| **REQ-TOOL-01** | Exclusive use of `uv` for Python package management; removal of `requirements.txt`. | `pyproject.toml`, `uv.lock`, updated `Dockerfile` and `docker-compose.yml`. | `uv lock --check`<br>`uv sync` | `VERIFIED` |
| **REQ-TOOL-02** | Removal of `docs/` and `prompts/` directories with essential documents moved to root. | `ARCHITECTURE.md`, `DATA_DICTIONARY.md`, `REQUIREMENTS_TRACEABILITY.md`, `AI_PROMPT_HISTORY.md` at root. | Verified directories removed. | `VERIFIED` |
| **REQ-TOOL-03** | Alembic migration management without `create_all()` in production. | `alembic/versions/001_initial_schema.py` covering all 16 tables. | `uv run alembic upgrade head` | `VERIFIED` |
