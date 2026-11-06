# Requirements Traceability Matrix (RTM)

**Project**: Insurance Claims Processing System  
**Organization**: YottaFlex AI Recruitment Assessment  
**Document Version**: 3.0.0 (Phase 2 Baseline)  

---

## Traceability Schema & Status Legend

- **Status Values**:
  - `VERIFIED`: Implemented and fully verified via automated tests and data validation.
  - `IMPLEMENTED`: Code created and verified in sandbox; integrated with synthetic generator.
  - `PLANNED`: Slated for Phase 3 (FastAPI service workflows, routes, API endpoints).

---

## 1. Core Domain Entities & Relationships (All 11 Entities)

| Requirement ID | Original Assessment Requirement | Implemented Models & Repositories | Validation Method | Phase 2 Status |
| :--- | :--- | :--- | :--- | :--- |
| **REQ-ENT-01** | **Customer**: Policyholder master data, contact info, KYC status (`PENDING`, `VERIFIED`, `REJECTED`, `FLAGGED`), risk tier (`LOW`, `MEDIUM`, `HIGH`). | `app/models/customer.py`<br>`app/repositories/customer_repository.py` | Unit test in `tests/unit/test_models.py` & `test_generators.py`, PK/FK uniqueness in `scripts/validate_data.py`. | `VERIFIED` |
| **REQ-ENT-02** | **Policy**: Multi-line policy contract across Auto, Home, Health, Commercial, Travel lines with status lifecycle (`DRAFT`, `ACTIVE`, `SUSPENDED`, `EXPIRED`, `CANCELLED`), effective/expiration dates, premium, deductible. | `app/models/policy.py`<br>`app/repositories/policy_repository.py` | Model check constraint test (`expiration_date > effective_date`, `premium >= 0`), unique policy id, foreign key to customer. | `VERIFIED` |
| **REQ-ENT-03** | **Coverage**: Specific coverage clauses with limits, deductibles, and coinsurance/copay percentage. | `app/models/coverage.py`<br>`app/repositories/coverage_repository.py` | CheckConstraint tests for `limit > 0`, `0 <= copay <= 100`, `deductible >= 0`, foreign key to policy. | `VERIFIED` |
| **REQ-ENT-04** | **Incident**: Physical casualty occurrence tracking incident type, occurrence date, description, and location metadata; supports duplicate incident detection and multi-claim linkage. | `app/models/incident.py`<br>`app/repositories/incident_repository.py` | Duplicate incident detection test via street/city/occurrence_date queries in `IncidentRepository` and `validate_data.py`. | `VERIFIED` |
| **REQ-ENT-05** | **Claim**: Claim intake records, incident linkage, claimed amounts, estimated losses, and status lifecycle. | `app/models/claim.py`<br>`app/repositories/claim_repository.py` | Foreign key validation (customer, policy, incident), financial non-negative check constraints, duplicate detection query. Relational invariant: `claim.customer_id == policy.customer_id`. | `VERIFIED` |
| **REQ-ENT-06** | **ClaimItem**: Itemized breakdown of loss components; references optional coverage clause; stores quantity, unit amount, and total amount. | `app/models/claim_item.py`<br>`app/repositories/claim_item_repository.py` | Quantity and financial value check constraints (`quantity >= 1`, `unit_amount >= 0`, `total_amount >= 0`). Strict sum matching verified. | `VERIFIED` |
| **REQ-ENT-07** | **Document**: Evidentiary files linked to claims; tracks filename, MIME type, file size, SHA-256 checksum, and verification status (`PENDING`, `VERIFIED`, `REJECTED`). | `app/models/document.py`<br>`app/repositories/document_repository.py` | SHA-256 validation test, file size positive constraint, verification status transition tests. | `VERIFIED` |
| **REQ-ENT-08** | **Adjuster**: Adjuster profile tracking domain specialization, current active claims count, maximum capacity, and availability status (`ACTIVE`, `ON_LEAVE`, `INACTIVE`). | `app/models/adjuster.py`<br>`app/repositories/adjuster_repository.py` | Capacity check tests (`active_claims_count < max_capacity`), least-loaded adjuster selection test, specialization mapping. | `VERIFIED` |
| **REQ-ENT-09** | **Assessment**: Eligibility decisions recording checks (`policy_active`, `incident_covered`, `timely_filing`, `exclusions`, `documents_complete`, `fraud`), decision reasons, and timestamps; supports reassessment. | `app/models/assessment.py`<br>`app/repositories/assessment_repository.py` | Reassessment history test, pure rule evaluation via `app/rules/eligibility_rules.py`. | `VERIFIED` |
| **REQ-ENT-10** | **Reserve**: Preliminary reserve calculations storing indemnity reserve, expense reserve (at default 12%), total reserve, calculation method, and version history. | `app/models/reserve.py`<br>`app/repositories/reserve_repository.py` | Arithmetic integrity test (`total_reserve == indemnity + expense`), reserve history retrieval test, `app/rules/financial_rules.py`. | `VERIFIED` |
| **REQ-ENT-11** | **Settlement**: Settlement adjudication tracking recommended, approved, deductible applied, copay applied, and net settlement amounts; payment reference and status. | `app/models/settlement.py`<br>`app/repositories/settlement_repository.py` | Financial non-negative check constraints, supervisor review thresholds, payment relationship tests, `app/rules/financial_rules.py`. | `VERIFIED` |

---

## 2. Supporting History & Audit Entities

| Requirement ID | Supporting Entity | Implemented Models & Repositories | Validation Method | Phase 2 Status |
| :--- | :--- | :--- | :--- | :--- |
| **REQ-AUD-01** | **ClaimStatusHistory**: Complete append-only audit trail of every status transition for every claim. | `app/models/claim_status_history.py`<br>`app/repositories/claim_status_history_repository.py` | Transition history append test asserting zero deletion or in-place overwrite. | `VERIFIED` |
| **REQ-AUD-02** | **AuditEvent**: Immutable enterprise change-log capturing `entity_type`, `entity_id`, `action`, `state_before`, `state_after`, `actor_type`, `actor_id`, and `timestamp`. | `app/models/audit_event.py`<br>`app/repositories/audit_repository.py` | Audit log emission test; verify records are append-only. | `VERIFIED` |
| **REQ-AUD-03** | **AdjusterAssignment**: Adjuster assignment and reassignment audit history. | `app/models/adjuster_assignment.py`<br>`app/repositories/adjuster_assignment_repository.py` | Historical assignment retrieval test; active assignment flag check. | `VERIFIED` |
| **REQ-AUD-04** | **DocumentRequest**: Missing document request tracking for claims with incomplete documentation (NEG-04). | `app/models/document_request.py`<br>`app/repositories/document_request_repository.py` | Open request query test; fulfillment linkage test. | `VERIFIED` |
| **REQ-AUD-05** | **SettlementPayment**: Disbursement transaction records preventing duplicate payments and ensuring limits are respected. | `app/models/settlement_payment.py`<br>`app/repositories/settlement_payment_repository.py` | Unique payment reference test; duplicate payment prevention query. | `VERIFIED` |

---

## 3. Mandatory Negative Scenarios & Business Rules Engine

| Scenario ID | Scenario Name | Implemented Rule & Injector Module | Validation Test | Phase 2 Status |
| :--- | :--- | :--- | :--- | :--- |
| **NEG-01** | **Expired Policy Filing** | `app/rules/eligibility_rules.py`<br>`scripts/generators/anomaly_injector.py` | `tests/unit/test_rules.py::TestEligibilityRules::test_neg_01_incident_before_policy_start` & `test_neg_01_incident_after_policy_cancellation` | `VERIFIED` |
| **NEG-02** | **Uncovered Peril / Policy Exclusion** | `app/rules/eligibility_rules.py`<br>`scripts/generators/anomaly_injector.py` | `tests/unit/test_rules.py::TestEligibilityRules::test_neg_02_uncovered_peril` & `test_neg_02_policy_exclusion` | `VERIFIED` |
| **NEG-03** | **Untimely Filing / Late Notice** | `app/rules/eligibility_rules.py`<br>`scripts/generators/anomaly_injector.py` | `tests/unit/test_rules.py::TestEligibilityRules::test_neg_03_untimely_filing` (30 days statutory window) | `VERIFIED` |
| **NEG-04** | **Missing Mandatory Documents** | `app/rules/document_rules.py`<br>`scripts/generators/document_generator.py` | `tests/unit/test_rules.py::TestDocumentRules::test_check_document_completeness_missing_doc` (emits `DocumentRequest`) | `VERIFIED` |
| **NEG-05** | **Excessive Claim Exceeding Limit** | `app/rules/financial_rules.py`<br>`scripts/generators/settlement_generator.py` | `tests/unit/test_rules.py::TestFinancialRules::test_compute_settlement_with_copay_and_limit_cap` (uncapped settlement flagged) | `VERIFIED` |
| **NEG-06** | **Suspended Policy / Suspected Fraud** | `app/rules/fraud_rules.py`<br>`scripts/generators/anomaly_injector.py` | `tests/unit/test_rules.py::TestFraudRules` & duplicate claims/incidents/double payments | `VERIFIED` |

---

## 4. Synthetic Data Generation & Isolated Ground Truth

| Requirement ID | Generator / Exporter Component | Implementation Path | Verification & Reproducibility | Phase 2 Status |
| :--- | :--- | :--- | :--- | :--- |
| **REQ-GEN-01** | **Deterministic CLI Generator** | `scripts/generate_data.py` | `--scale full` produces **exactly 2,000 policies and 1,000 claims**. | `VERIFIED` |
| **REQ-GEN-02** | **5 Balanced Claim Types** | `scripts/generators/claim_generator.py` | Collision, Property Damage, Medical, Travel Loss, Liability. | `VERIFIED` |
| **REQ-GEN-03** | **Strict Item Financial Matching** | `scripts/generators/claim_item_generator.py` | `sum(claim_items.total_amount) == claim.claimed_amount` verified for 1,000 claims. | `VERIFIED` |
| **REQ-GEN-04** | **Isolated Ground Truth** | `data/synthetic/ground_truth/ground_truth.csv` & `.json` | Zero ground truth leakage into domain tables; full referential linkage. | `VERIFIED` |
| **REQ-GEN-05** | **PostgreSQL Seed Script** | `data/synthetic/sql/seed_data.sql` | Strict foreign key order (16 tables, 22,933 INSERT statements). | `VERIFIED` |
| **REQ-GEN-06** | **Deterministic Reproducibility** | `scripts/generation_config.py` (Seed: 20261022) | 100% bit-for-bit identical SHA-256 hashes across all 35 files. | `VERIFIED` |
| **REQ-GEN-07** | **Automated Data Quality Validator** | `scripts/validate_data.py` | Validates PK uniqueness, FK referential integrity, financial math, document requests, manifest hashes. 0 errors. | `VERIFIED` |
