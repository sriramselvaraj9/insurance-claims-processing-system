# Requirements Traceability Matrix (RTM)

**Project**: Insurance Claims Processing System  
**Organization**: YottaFlex AI Recruitment Assessment  
**Document Version**: 1.0.0  
**Phase**: Phase 0 — Foundation & Discovery  

---

## Traceability Schema & Status Legend

- **Status Values**:
  - `PLANNED`: Architectural design complete; awaiting implementation in subsequent phases.
  - `IN_PROGRESS`: Currently under active development.
  - `VERIFIED`: Implemented and verified via automated test suite.

---

## 1. Domain Entities & Life Cycle Requirements

| Requirement ID | Original Assessment Requirement | Planned Implementation Module | Validation Method | Current Status |
| :--- | :--- | :--- | :--- | :--- |
| **REQ-ENT-01** | Data model for **Customer** entity with contact info, risk profile, and KYC status. | `app/models/customer.py`, `app/schemas/customer.py` | Unit tests for constraints, foreign keys, and Pydantic schema validation. | `PLANNED` |
| **REQ-ENT-02** | Data model for **Policy** entity across Auto, Home, Health, and Commercial lines with lifecycle states (`DRAFT`, `ACTIVE`, `SUSPENDED`, `EXPIRED`, `CANCELLED`). | `app/models/policy.py`, `app/schemas/policy.py`, `app/workflows/policy_lifecycle.py` | State transition unit tests; schema boundary verification. | `PLANNED` |
| **REQ-ENT-03** | Data model for **Coverage** entity supporting specific coverage types, limits, deductibles, and coinsurance/copay. | `app/models/coverage.py`, `app/schemas/coverage.py` | Database foreign key and uniqueness constraint tests. | `PLANNED` |
| **REQ-ENT-04** | Data model for **Claim** entity supporting full lifecycle states (`SUBMITTED`, `UNDER_REVIEW`, `INFO_REQUESTED`, `ELIGIBLE`, `INELIGIBLE`, `ADJUSTER_ASSIGNED`, `RESERVE_CALCULATED`, `SETTLEMENT_RECOMMENDED`, `APPROVED`, `SETTLED`, `REJECTED`, `CLOSED`, `FLAGGED`). | `app/models/claim.py`, `app/schemas/claim.py`, `app/workflows/claim_lifecycle.py` | Finite State Machine (FSM) validation tests covering all allowed and disallowed transitions. | `PLANNED` |
| **REQ-ENT-05** | Data model for physical/electronic **Document** storage metadata (SHA-256 checksum, MIME types, file size). | `app/models/document.py`, `app/schemas/document.py` | Checksum verification and payload parsing unit tests. | `PLANNED` |
| **REQ-ENT-06** | Data model for **ClaimDocument** link entity managing document types and verification states (`PENDING`, `VERIFIED`, `REJECTED`). | `app/models/claim_document.py`, `app/schemas/claim_document.py` | Verification status mutation tests and database join tests. | `PLANNED` |
| **REQ-ENT-07** | Data model for **EligibilityAssessment** recording sub-check outcomes (`policy_active`, `incident_covered`, `timely_filing`, `exclusions`) and reasons. | `app/models/eligibility.py`, `app/schemas/eligibility.py` | Assessment serialization tests and DB persistence tests. | `PLANNED` |
| **REQ-ENT-08** | Data model for **Adjuster** entity tracking domain specialization, current active claims count, and maximum workload capacity. | `app/models/adjuster.py`, `app/schemas/adjuster.py` | Capacity check unit tests and round-robin assignment tests. | `PLANNED` |
| **REQ-ENT-09** | Data model for **ReserveCalculation** tracking estimated indemnity reserve, expense reserve, total reserve, and formula methodology. | `app/models/reserve.py`, `app/schemas/reserve.py` | Financial calculation arithmetic verification tests. | `PLANNED` |
| **REQ-ENT-10** | Data model for **Settlement** entity tracking recommended amount, supervisor approval, applied deductible, copay, net settlement amount, and payment references. | `app/models/settlement.py`, `app/schemas/settlement.py` | Pydantic financial decimal validation and settlement state flow tests. | `PLANNED` |
| **REQ-ENT-11** | Data model for **AuditEvent** & **ExceptionLog** capturing immutable change logs, previous/new states, actor attribution, and exception queues. | `app/models/audit.py`, `app/models/exception_log.py`, `app/services/audit_service.py` | Audit immutability verification tests and event emission tests. | `PLANNED` |

---

## 2. Business Logic & Six Mandatory Negative Scenarios

| Requirement ID | Original Assessment Requirement | Planned Implementation Module | Validation Method | Current Status |
| :--- | :--- | :--- | :--- | :--- |
| **REQ-NEG-01** | **Expired Policy Filing**: Claims with `incident_date` outside `effective_date` to `expiration_date` must fail eligibility and transition to `INELIGIBLE` -> `REJECTED`. | `app/rules/eligibility_rules.py` | Unit test with explicit dates before effective and after expiration. | `PLANNED` |
| **REQ-NEG-02** | **Uncovered Loss / Exclusion**: Claims where `claim_type` is not an active coverage or falls under an exclusion clause must be rejected. | `app/rules/eligibility_rules.py`, `app/rules/coverage_rules.py` | Unit test matching claims with missing coverage or explicitly excluded perils. | `PLANNED` |
| **REQ-NEG-03** | **Untimely Filing / Late Notice**: Claims reported after the statutory window (default: 30 days post incident) must trigger `UNTIMELY_FILING` exception. | `app/rules/eligibility_rules.py` | Unit test evaluating `reported_date - incident_date > 30` days. | `PLANNED` |
| **REQ-NEG-04** | **Missing Mandatory Documents**: Claims lacking required evidentiary documents (e.g., police report for theft) must pause intake and move to `INFO_REQUESTED`. | `app/rules/document_rules.py` | Unit test verifying document completeness matrix per claim type. | `PLANNED` |
| **REQ-NEG-05** | **Excessive Claim Exceeding Limit**: Claims exceeding coverage limits must cap allowable payout at limit and log severity alerts for SIU review. | `app/rules/financial_rules.py` | Unit test verifying capped reserve and settlement calculations when `claimed_amount > limit`. | `PLANNED` |
| **REQ-NEG-06** | **Suspended Policy / Suspected Fraud**: Suspended policy filings or duplicate claim submissions within 7 days must be quarantined with status `FLAGGED`. | `app/rules/fraud_rules.py`, `app/rules/eligibility_rules.py` | Unit test injecting duplicate claims and non-active policies. | `PLANNED` |

---

## 3. Financial Calculations

| Requirement ID | Original Assessment Requirement | Planned Implementation Module | Validation Method | Current Status |
| :--- | :--- | :--- | :--- | :--- |
| **REQ-FIN-01** | **Indemnity Reserve Calculation**: Compute indemnity reserve as `max(0, min(loss, limit) - deductible)` using exact Decimal arithmetic. | `app/rules/financial_rules.py` | Parameterized unit tests with varying loss, limit, and deductible combinations. | `PLANNED` |
| **REQ-FIN-02** | **Expense Reserve Calculation**: Compute loss adjustment expense reserve as `indemnity_reserve * expense_ratio` (default: 12%). | `app/rules/financial_rules.py` | Parameterized unit tests verifying expense ratio application. | `PLANNED` |
| **REQ-FIN-03** | **Net Settlement Calculation**: Compute net payout applying deductible and copay percentage reductions: `max(0, (min(loss, limit) - deductible) * (1 - copay))`. | `app/rules/financial_rules.py` | Parameterized unit tests against ground truth settlement calculations. | `PLANNED` |

---

## 4. Workflows & Orchestration

| Requirement ID | Original Assessment Requirement | Planned Implementation Module | Validation Method | Current Status |
| :--- | :--- | :--- | :--- | :--- |
| **REQ-WRK-01** | **Adjuster Assignment Engine**: Assign eligible claims to active adjusters based on domain specialization and lowest current workload under maximum capacity. | `app/services/adjuster_service.py` | Unit and integration tests verifying capacity limits and specialization matching. | `PLANNED` |
| **REQ-WRK-02** | **Claims Intake & Evaluation Pipeline**: End-to-end orchestration coordinating intake, document check, eligibility, reserve, adjuster assignment, and settlement. | `app/services/claims_service.py`, `app/workflows/claim_workflow.py` | Integration pipeline test simulating end-to-end claims flow. | `PLANNED` |
| **REQ-WRK-03** | **Exception Management & Triaging**: Capture business rule exceptions in `ExceptionLog` with severity rankings and resolution workflows. | `app/services/exception_service.py` | Integration test verifying exception log creation and resolution transitions. | `PLANNED` |
| **REQ-WRK-04** | **Audit Trail Management**: Emit immutable `AuditEvent` logs on every state transition and critical financial calculation. | `app/services/audit_service.py` | Unit test asserting 100% audit log coverage across all state transitions. | `PLANNED` |

---

## 5. Synthetic Data Generation & Evaluation Framework

| Requirement ID | Original Assessment Requirement | Planned Implementation Module | Validation Method | Current Status |
| :--- | :--- | :--- | :--- | :--- |
| **REQ-SYN-01** | **Synthetic Data Generator**: Deterministic, seed-controlled generator generating customers, policies, coverages, claims, and documents using Faker & Pandas. | `scripts/generate_synthetic_data.py`, `app/services/synthetic_data_generator.py` | Script execution test verifying record count, distributions, and schema conformity. | `PLANNED` |
| **REQ-SYN-02** | **Ground Truth Annotation**: Synthetic dataset must embed ground truth columns (`gt_is_eligible`, `gt_expected_reserve`, `gt_expected_settlement`, `gt_rejection_code`). | `scripts/generate_synthetic_data.py` | Automated schema validation ensuring ground-truth columns are populated. | `PLANNED` |
| **REQ-EVAL-01** | **Evaluation & Benchmarking Engine**: Compute precision, recall, F1-score, and confusion matrix for eligibility assessment vs. ground truth. | `scripts/evaluate_rules_engine.py`, `app/services/evaluation_service.py` | Benchmark test verifying evaluation metric computation and reporting. | `PLANNED` |
| **REQ-EVAL-02** | **Financial Reserve Evaluation**: Compute MAE and RMSE comparing calculated reserves against ground truth estimated loss. | `scripts/evaluate_rules_engine.py` | Statistical calculation unit tests. | `PLANNED` |

---

## 6. Architecture, Packaging & Operational Infrastructure

| Requirement ID | Original Assessment Requirement | Planned Implementation Module | Validation Method | Current Status |
| :--- | :--- | :--- | :--- | :--- |
| **REQ-OPS-01** | Clean layered architecture: Routes -> Services -> Repositories -> PostgreSQL. Strict separation of concerns. | `app/api/`, `app/services/`, `app/repositories/`, `app/models/` | Code structure review, dependency linting, repository isolation tests. | `VERIFIED` (Phase 0) |
| **REQ-OPS-02** | Packaging and environment setup using `pyproject.toml`, `.env.example`, `.gitignore`, `alembic/`, `Dockerfile`, and `docker-compose.yml`. | Root configuration files | Configuration parsing and test suite run. | `VERIFIED` (Phase 0) |
| **REQ-OPS-03** | Comprehensive documentation including `docs/architecture.md`, `docs/requirements.md`, `docs/implementation_plan.md`, `docs/requirements_traceability.md`, and `README.md`. | `docs/` | Documentation completeness inspection. | `VERIFIED` (Phase 0) |
