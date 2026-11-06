# Phase-by-Phase Implementation Plan

**Project**: Insurance Claims Processing System  
**Organization**: YottaFlex AI Recruitment Technical Assessment  
**Document Version**: 1.0.0  
**Status**: Active  

---

## Roadmap Overview

The assessment is structured into six discrete, verifiable phases designed to deliver an end-to-end, tested, and auditable solution without skipping requirements or relying on unverified placeholders.

```
Phase 0: Environment Inspection & Project Foundation (Current Phase)
   │
   ▼
Phase 1: Database Architecture, Models & Repositories (11 Core Entities)
   │
   ▼
Phase 2: Business Rules Engine, Financial Formulas & Negative Scenarios
   │
   ▼
Phase 3: Service Orchestration, Workflow State Machines & REST APIs
   │
   ▼
Phase 4: Synthetic Data Generator, Ground Truth & Evaluation Harness
   │
   ▼
Phase 5: Comprehensive QA, Integration Testing, Docker & Final Documentation
```

---

## Phase 0: Environment Inspection & Project Foundation (Current)
- **Objective**: Establish the repository foundation, inspect existing environment, document complete assessment scope, and configure packaging/tooling.
- **Key Deliverables**:
  - Environment inspection results.
  - Project directory hierarchy (`app/`, `tests/`, `docs/`, `scripts/`, `prompts/`, `alembic/`).
  - Packaging files: `pyproject.toml`, `requirements.txt`, `.env.example`, `.gitignore`, `Dockerfile`, `docker-compose.yml`, `alembic.ini`.
  - Core app scaffolding: `app/core/config.py`, `app/core/database.py`, `app/main.py`.
  - Documentation: `docs/requirements.md`, `docs/architecture.md`, `docs/requirements_traceability.md`, `docs/implementation_plan.md`, `prompts/ai_prompt_history.md`.
  - Foundational unit tests (`tests/unit/test_foundation.py`) passing with 100% success.
- **Verification Criteria**:
  - `pytest tests/unit/test_foundation.py` passes without errors.
  - Directory hierarchy is cleanly established.
  - Zero accidental file overwrites.

---

## Phase 1: Database Architecture, Models & Repositories
- **Objective**: Implement SQLAlchemy 2.x Declarative models for all 11 domain entities, generate Alembic migrations, and establish the Repository data access layer.
- **Key Deliverables**:
  - `app/models/`:
    - `customer.py`: Customer entity with KYC and risk profiles.
    - `policy.py`: Policy entity with types and status lifecycles.
    - `coverage.py`: Coverage clauses, limits, deductibles, copays.
    - `claim.py`: Claim entity with full status enums, amounts, incident metadata.
    - `document.py`: Document storage metadata with SHA-256 digests.
    - `claim_document.py`: Evidentiary link table with verification status.
    - `eligibility.py`: Eligibility assessment results and checks.
    - `adjuster.py`: Adjuster entity with capacity and specialization.
    - `reserve.py`: Preliminary reserve calculations (indemnity + expense).
    - `settlement.py`: Settlement proposals and disbursements.
    - `audit.py` & `exception_log.py`: Append-only audit events and exception tracking.
  - Initial Alembic migration script generating complete database DDL.
  - `app/repositories/`:
    - `base_repository.py`: Generic CRUD operations with type hints.
    - `customer_repository.py`, `policy_repository.py`, `claim_repository.py`, `adjuster_repository.py`, `settlement_repository.py`, `audit_repository.py`.
- **Verification Criteria**:
  - Models instantiate cleanly with SQLAlchemy metadata.
  - Schema constraints (foreign keys, uniques, check constraints) verified via unit tests.
  - CRUD operations across repositories verified with SQLite/Postgres.

---

## Phase 2: Business Rules Engine, Financial Formulas & Negative Scenarios
- **Objective**: Implement the pure, deterministic business rules engine supporting all standard evaluations, six mandatory negative scenarios, and financial calculations.
- **Key Deliverables**:
  - `app/rules/`:
    - `eligibility_rules.py`:
      - Evaluates policy active window (NEG-01 Expired Policy).
      - Evaluates covered perils and policy exclusions (NEG-02 Uncovered Peril).
      - Evaluates timely filing notice period (NEG-03 Untimely Filing).
    - `document_rules.py`:
      - Evaluates mandatory document requirements per claim type (NEG-04 Missing Documents).
    - `financial_rules.py`:
      - Computes allowable loss capped at policy limit (NEG-05 Over Limit).
      - Computes indemnity reserve: `max(0, min(loss, limit) - deductible)`.
      - Computes expense reserve: `indemnity_reserve * expense_ratio`.
      - Computes net settlement: `max(0, (min(loss, limit) - deductible) * (1 - copay))`.
    - `fraud_rules.py`:
      - Detects suspended policies and duplicate submissions within 7-day windows (NEG-06 Fraud / Suspended Policy).
  - Comprehensive unit test suite (`tests/unit/test_rules.py`) covering all six negative scenarios and financial edge cases.
- **Verification Criteria**:
  - 100% of negative scenarios fail with appropriate descriptive rationale.
  - Financial calculations match exact hand-computed test fixtures.

---

## Phase 3: Service Orchestration, Workflow State Machines & REST APIs
- **Objective**: Build the application service orchestration layer, finite state machine lifecycles, and FastAPI REST endpoints.
- **Key Deliverables**:
  - `app/workflows/`:
    - `claim_lifecycle.py`: State machine enforcing legal claim state transitions.
    - `policy_lifecycle.py`: Policy state machine (`DRAFT` -> `ACTIVE` -> `EXPIRED`, etc.).
  - `app/services/`:
    - `claims_service.py`: Intake pipeline coordinating eligibility, reserve, adjuster assignment.
    - `adjuster_service.py`: Capacity-aware assignment by specialization.
    - `settlement_service.py`: Proposal, supervisor approval, and disbursement.
    - `exception_service.py`: Logging and triaging of business rule exceptions.
    - `audit_service.py`: Automatic recording of state transitions and actor actions.
  - `app/api/v1/`:
    - `claims.py`: Endpoints for claim intake, status tracking, document upload.
    - `policies.py`: Endpoints for customer and policy onboarding.
    - `adjusters.py`: Endpoints for adjuster management and capacity views.
    - `settlements.py`: Endpoints for settlement proposal and approval.
    - `audit.py`: Endpoints for viewing audit trails and exceptions.
- **Verification Criteria**:
  - Integration tests verifying end-to-end claim intake and state transitions.
  - Invalid state transitions raise `400/409` errors.
  - Every mutation produces an `AuditEvent`.

---

## Phase 4: Synthetic Data Generator, Ground Truth & Evaluation Harness
- **Objective**: Develop a statistically sound synthetic claims data generator with ground truth labeling and an evaluation benchmarking suite.
- **Key Deliverables**:
  - `app/services/synthetic_data_generator.py` & `scripts/generate_synthetic_data.py`:
    - Faker and NumPy/Pandas generator creating realistic distributions.
    - Deterministic random seed control (`Seed=42`).
    - Configurable batch size (100 to 1,000+ records).
    - Injects controlled ratios of the six negative scenarios.
    - Emits ground-truth columns (`gt_is_eligible`, `gt_expected_reserve`, `gt_expected_settlement`, `gt_rejection_code`).
  - `app/services/evaluation_service.py` & `scripts/evaluate_rules_engine.py`:
    - Evaluates rules engine decisions against ground truth.
    - Computes Precision, Recall, F1-Score, and Confusion Matrix.
    - Computes MAE and RMSE for reserve estimations.
    - Exports formatted markdown evaluation report to `docs/evaluation_report.md`.
- **Verification Criteria**:
  - Running `python scripts/generate_synthetic_data.py` outputs valid CSV dataset.
  - Running `python scripts/evaluate_rules_engine.py` generates full evaluation metrics.
  - Reproducibility verified: identical dataset generated across repeated runs with seed 42.

---

## Phase 5: Comprehensive QA, Integration Testing, Docker & Final Documentation
- **Objective**: End-to-end verification, Docker Compose containerization test, and final documentation polish.
- **Key Deliverables**:
  - Full automated test suite (`pytest --cov=app tests/`).
  - Docker Compose verification (`docker-compose up --build`).
  - Final documentation review:
    - Complete API usage examples in `README.md`.
    - Final Requirements Traceability Matrix status update (`docs/requirements_traceability.md`).
    - Final prompt log verification (`prompts/ai_prompt_history.md`).
- **Verification Criteria**:
  - `pytest` passes with high test coverage (>90%).
  - Zero critical linting or type-checking errors (`ruff check`, `mypy`).
  - Container boots cleanly and passes health check.

---

## Risk Analysis & Mitigation Matrix

| Identified Risk | Potential Impact | Severity | Mitigation Strategy |
| :--- | :--- | :--- | :--- |
| **Windows Sandbox Async IO Blocking** | Event loop / AnyIO worker thread freeze during synchronous test runs. | High | Use synchronous route functions and direct test execution for unit tests; use standard ASGI clients in production. |
| **Financial Rounding Drift** | Inaccurate reserve and settlement numbers causing accounting discrepancies. | Medium | Enforce `Decimal` arithmetic with explicit rounding modes (`ROUND_HALF_UP`) throughout financial rules. |
| **Illegal Claim State Skipping** | Claims bypassing eligibility or reserve calculations before settlement. | High | Enforce Finite State Machine in `app/workflows/claim_lifecycle.py` with strict transition validators. |
| **Synthetic Data Leakage of Real PII** | Confidential data exposure. | Critical | Exclusively utilize synthetic generation via `Faker` and mathematical pseudo-random distributions. Never import external raw data. |
| **Missing Audit Coverage** | Statutory non-compliance during regulatory audit. | High | Integrate audit logging inside service transaction wrappers so uncommitted or unlogged state transitions fail atomically. |
