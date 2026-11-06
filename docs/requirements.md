# Comprehensive Requirements Specification: Insurance Claims Processing System

**Assessment Provider**: YottaFlex AI Recruitment Technical Assessment  
**Project**: Enterprise-Grade Insurance Claims Processing, Rules Engine, and Evaluation System  
**Version**: 1.0.0  
**Status**: Baseline Draft Approved  

---

## 1. Executive Summary & Business Objective

The goal of this system is to provide a complete, deterministic, traceable, and production-ready insurance claims processing platform. The platform handles the full lifecycle of property, casualty, health, and auto claims—from policyholder onboarding and coverage validation to claim intake, automated document verification, deterministic eligibility assessment, capacity-aware adjuster assignment, preliminary reserve calculation, settlement adjudication, exception detection, and immutable audit logging.

Additionally, the system provides a synthetic data generation and evaluation harness to benchmark business rule accuracy and automated decision-making against ground truth.

---

## 2. Domain Entities & Data Model Requirements (11 Core Entities)

The data model encompasses 11 core domain entities with strict referential integrity, typed enums, and comprehensive auditability.

```
+----------------+       1:N       +----------------+       1:N       +----------------+
|    Customer    | --------------< |     Policy     | --------------< |    Coverage    |
+----------------+                 +----------------+                 +----------------+
        |                                  |
        | 1:N                              | 1:N
        v                                  v
+---------------------------------------------------+
|                       Claim                       |
+---------------------------------------------------+
   |           |               |              |
   | 1:N       | 1:1           | N:1          | 1:N
   v           v               v              v
+----------+ +---------------+ +----------+ +--------------------+
|  Claim-  | |  Eligibility  | | Adjuster | | ReserveCalculation |
| Document | |  Assessment   | +----------+ +--------------------+
+----------+ +---------------+                       |
   |                                                  | 1:N
   | N:1                                              v
+----------+                                +--------------------+
| Document |                                |     Settlement     |
+----------+                                +--------------------+
        |
        +---------------------------------------------+
        |                                             |
        v                                             v
+--------------------+                      +--------------------+
|     AuditEvent     |                      |    ExceptionLog    |
+--------------------+                      +--------------------+
```

### 2.1 Customer
- **Description**: The policyholder or insured entity.
- **Attributes**:
  - `id` (UUID / Integer PK, Auto-increment or UUID)
  - `customer_number` (Unique string identifier, e.g., `CUST-100293`)
  - `first_name`, `last_name` (String, max 100)
  - `email` (Unique valid email address)
  - `phone` (String, international E.164 format)
  - `date_of_birth` (Date)
  - `kyc_status` (Enum: `PENDING`, `VERIFIED`, `REJECTED`, `FLAGGED`)
  - `risk_profile` (Enum: `LOW`, `MEDIUM`, `HIGH`)
  - `created_at`, `updated_at` (Timestamps with timezone)

### 2.2 Policy
- **Description**: The legal contract between the insurer and customer governing coverage terms.
- **Attributes**:
  - `id` (PK)
  - `policy_number` (Unique string, e.g., `POL-AUTO-2026-001`)
  - `customer_id` (FK -> `customers.id`, indexed)
  - `policy_type` (Enum: `AUTO`, `HOME`, `HEALTH`, `COMMERCIAL`)
  - `status` (Enum: `DRAFT`, `ACTIVE`, `SUSPENDED`, `EXPIRED`, `CANCELLED`)
  - `effective_date` (Date)
  - `expiration_date` (Date, constraint: `expiration_date > effective_date`)
  - `total_premium` (Numeric(12, 2) >= 0)
  - `deductible` (Numeric(10, 2) >= 0)
  - `created_at`, `updated_at`

### 2.3 Coverage
- **Description**: Specific protection clauses attached to a policy.
- **Attributes**:
  - `id` (PK)
  - `policy_id` (FK -> `policies.id`, indexed)
  - `coverage_type` (Enum: `COLLISION`, `COMPREHENSIVE`, `LIABILITY`, `DWELLING`, `PERSONAL_PROPERTY`, `MEDICAL_PAYMENTS`, `BODILY_INJURY`)
  - `coverage_limit` (Numeric(12, 2) > 0)
  - `deductible` (Numeric(10, 2) >= 0)
  - `copay_percentage` (Numeric(5, 2), 0.00 to 100.00, default 0.00)
  - `is_active` (Boolean, default True)
  - `created_at`, `updated_at`

### 2.4 Claim
- **Description**: Request for indemnification filed by or on behalf of an insured.
- **Attributes**:
  - `id` (PK)
  - `claim_number` (Unique string, e.g., `CLM-2026-00491`)
  - `policy_id` (FK -> `policies.id`, indexed)
  - `customer_id` (FK -> `customers.id`, indexed)
  - `incident_date` (Date / Timestamp)
  - `reported_date` (Date / Timestamp, constraint: `reported_date >= incident_date`)
  - `claim_type` (Enum: matches `CoverageType` or subcategory)
  - `status` (Enum: `SUBMITTED`, `UNDER_REVIEW`, `INFO_REQUESTED`, `ELIGIBLE`, `INELIGIBLE`, `ADJUSTER_ASSIGNED`, `RESERVE_CALCULATED`, `SETTLEMENT_RECOMMENDED`, `APPROVED`, `SETTLED`, `REJECTED`, `CLOSED`, `FLAGGED`)
  - `claimed_amount` (Numeric(12, 2) > 0)
  - `estimated_loss` (Numeric(12, 2) >= 0)
  - `description` (Text, minimum 10 characters)
  - `incident_location` (String / JSON structure: street, city, state, zip)
  - `assigned_adjuster_id` (FK -> `adjusters.id`, optional)
  - `created_at`, `updated_at`

### 2.5 Document
- **Description**: Physical or electronic file asset stored within the repository or storage layer.
- **Attributes**:
  - `id` (PK)
  - `file_name` (String)
  - `file_type` (String, MIME type: `application/pdf`, `image/jpeg`, `image/png`)
  - `file_path` (String, absolute or relative storage URI)
  - `file_size_bytes` (BigInteger > 0)
  - `checksum_sha256` (Char(64), cryptographic digest for integrity)
  - `uploaded_at` (Timestamp)

### 2.6 ClaimDocument
- **Description**: Association between a claim and an evidentiary document, tracking document type and verification state.
- **Attributes**:
  - `id` (PK)
  - `claim_id` (FK -> `claims.id`, indexed)
  - `document_id` (FK -> `documents.id`, indexed)
  - `document_type` (Enum: `POLICE_REPORT`, `MEDICAL_BILL`, `REPAIR_ESTIMATE`, `PROOF_OF_LOSS`, `DAMAGE_PHOTO`, `OTHER`)
  - `verification_status` (Enum: `PENDING`, `VERIFIED`, `REJECTED`)
  - `verified_at` (Timestamp, nullable)
  - `verified_by` (String, nullable)
  - `rejection_reason` (Text, nullable)
  - `created_at`

### 2.7 EligibilityAssessment
- **Description**: Automated or manual evaluation outcome certifying whether a claim meets policy and statutory criteria.
- **Attributes**:
  - `id` (PK)
  - `claim_id` (FK -> `claims.id`, unique index)
  - `is_eligible` (Boolean)
  - `policy_active_check` (Boolean)
  - `incident_covered_check` (Boolean)
  - `timely_filing_check` (Boolean)
  - `exclusions_check` (Boolean)
  - `documentation_complete_check` (Boolean)
  - `reasons` (JSON array of rule evaluation result strings)
  - `assessed_at` (Timestamp)
  - `assessed_by` (String, e.g., `RULE_ENGINE_V1` or adjuster ID)

### 2.8 Adjuster
- **Description**: Insurance professional responsible for investigating, inspecting, and managing claims.
- **Attributes**:
  - `id` (PK)
  - `employee_id` (Unique string, e.g., `ADJ-4401`)
  - `name` (String)
  - `email` (Unique string)
  - `specialization` (Enum: `AUTO`, `PROPERTY`, `HEALTH`, `COMMERCIAL`, `GENERAL`)
  - `active_claims_count` (Integer >= 0, default 0)
  - `max_capacity` (Integer > 0, default 20)
  - `status` (Enum: `ACTIVE`, `ON_LEAVE`, `INACTIVE`)
  - `created_at`, `updated_at`

### 2.9 ReserveCalculation
- **Description**: Financial liability calculation reserving funds for indemnity and loss adjustment expenses.
- **Attributes**:
  - `id` (PK)
  - `claim_id` (FK -> `claims.id`, indexed)
  - `estimated_indemnity_reserve` (Numeric(12, 2) >= 0)
  - `estimated_expense_reserve` (Numeric(12, 2) >= 0)
  - `total_reserve` (Numeric(12, 2) >= 0, constraint: `total_reserve = indemnity + expense`)
  - `calculation_method` (Enum: `FORMULAIC_STANDARD`, `ACTUARIAL_WEIGHTED`, `EXPERT_OVERRIDE`)
  - `expense_ratio` (Numeric(5, 4), e.g., 0.1200)
  - `calculated_at` (Timestamp)
  - `calculated_by` (String)

### 2.10 Settlement
- **Description**: Final or recommended financial resolution of a claim.
- **Attributes**:
  - `id` (PK)
  - `claim_id` (FK -> `claims.id`, indexed)
  - `recommended_amount` (Numeric(12, 2) >= 0)
  - `approved_amount` (Numeric(12, 2) >= 0, nullable)
  - `deductible_applied` (Numeric(10, 2) >= 0)
  - `copay_applied` (Numeric(10, 2) >= 0)
  - `net_settlement_amount` (Numeric(12, 2) >= 0)
  - `status` (Enum: `PROPOSED`, `SUPERVISOR_REVIEW`, `APPROVED`, `REJECTED`, `DISBURSED`)
  - `settled_at` (Timestamp, nullable)
  - `settled_by` (String, nullable)
  - `payment_reference` (String, nullable)

### 2.11 AuditEvent & ExceptionLog
- **Description**: Immutable append-only audit trail and exception queue for anomalous or rejected workflows.
- **AuditEvent Attributes**:
  - `id` (PK)
  - `entity_type` (String, e.g., `Claim`, `Settlement`, `Policy`)
  - `entity_id` (String / Integer)
  - `action` (Enum: `CREATE`, `UPDATE`, `STATE_TRANSITION`, `DELETE`, `OVERRIDE`)
  - `state_before` (JSON nullable)
  - `state_after` (JSON nullable)
  - `actor_type` (Enum: `SYSTEM_RULE`, `USER_ADJUSTER`, `USER_ADMIN`, `API_SERVICE`)
  - `actor_id` (String)
  - `timestamp` (Timestamp with timezone)
  - `metadata` (JSON nullable)
- **ExceptionLog Attributes**:
  - `id` (PK)
  - `claim_id` (FK -> `claims.id`, nullable)
  - `exception_code` (Enum: `SUSPECTED_FRAUD`, `UNTIMELY_FILING`, `EXPIRED_POLICY`, `DOCUMENT_DEFICIENCY`, `EXCEEDS_LIMIT`, `DUPLICATE_CLAIM`, `CAPACITY_EXCEEDED`)
  - `severity` (Enum: `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`)
  - `details` (JSON / Text)
  - `status` (Enum: `OPEN`, `TRIAGED`, `RESOLVED`, `DISMISSED`)
  - `created_at`, `resolved_at`

---

## 3. Six Mandatory Negative Scenarios

To prove the robustness of the business rules engine and domain validation, the system implements and tests six distinct negative failure modes:

| Scenario ID | Scenario Name | Business Trigger Condition | Expected Engine Behavior | State Transition |
| :--- | :--- | :--- | :--- | :--- |
| **NEG-01** | **Expired Policy Filing** | `incident_date > policy.expiration_date` OR `incident_date < policy.effective_date` | Rejection during eligibility assessment (`policy_active_check = False`). Detailed rationale recorded. | `SUBMITTED` -> `INELIGIBLE` -> `REJECTED` |
| **NEG-02** | **Uncovered Loss / Policy Exclusion** | `claim.claim_type` not present in active policy coverages OR incident specifically matches policy exclusion clause (e.g., intentional act, flood in standard auto). | Eligibility failed (`incident_covered_check = False`). Specific unmapped coverage code logged. | `SUBMITTED` -> `INELIGIBLE` -> `REJECTED` |
| **NEG-03** | **Untimely Filing / Late Notice** | `reported_date - incident_date > TIMELY_FILING_DAYS_LIMIT` (default: 30 calendar days). | Flagged as late notice (`timely_filing_check = False`). Exception logged (`UNTIMELY_FILING`). Requires explicit supervisor waiver or auto-rejected. | `SUBMITTED` -> `INFO_REQUESTED` or `INELIGIBLE` |
| **NEG-04** | **Missing Mandatory Documents** | Claim lacks required documents for its claim type (e.g., Auto Collision requires `POLICE_REPORT` or `REPAIR_ESTIMATE`; Health requires `MEDICAL_BILL`), or document verification status is `REJECTED`. | Intake pauses; state set to `INFO_REQUESTED`. Document request notification event emitted. Cannot progress to Adjuster Assignment or Reserve. | `SUBMITTED` -> `INFO_REQUESTED` |
| **NEG-05** | **Excessive Claim Exceeding Limit** | `claimed_amount > coverage.coverage_limit`. | Preliminary calculation caps allowable payout at `coverage_limit`. High-severity warning/exception logged. If `claimed_amount > 2x limit`, flagged for manual SIU (Special Investigation Unit) review. | Settlement capped at `coverage_limit - deductible`. |
| **NEG-06** | **Suspended Policy / Suspected Fraud** | Policy has status `SUSPENDED` (e.g. non-payment) OR claim flagged for duplicate submission (same policy, incident date, and similar amount within 7 days) OR fraudulent metadata. | Claim quarantined. Exception logged with `CRITICAL` severity (`SUSPECTED_FRAUD` / `DUPLICATE_CLAIM`). Immediate adjuster hold. | `SUBMITTED` -> `FLAGGED` |

---

## 4. Derived Financial Calculations & Formulas

All financial computations are strictly deterministic and executed using fixed-point `Decimal` arithmetic to avoid floating-point inaccuracies.

### 4.1 Indemnity Reserve Formula
$$\text{Allowable Loss} = \min(\text{Estimated Loss}, \text{Coverage Limit})$$
$$\text{Indemnity Reserve} = \max(0, \text{Allowable Loss} - \text{Deductible})$$

### 4.2 Expense Reserve Formula
$$\text{Expense Reserve} = \text{Indemnity Reserve} \times \text{Expense Ratio}$$
*(Default Expense Ratio = 12% = 0.1200)*

### 4.3 Total Preliminary Reserve Formula
$$\text{Total Reserve} = \text{Indemnity Reserve} + \text{Expense Reserve}$$

### 4.4 Net Settlement Formula
$$\text{Base Loss} = \min(\text{Claimed/Assessed Amount}, \text{Coverage Limit})$$
$$\text{Amount Subject to Copay} = \max(0, \text{Base Loss} - \text{Deductible})$$
$$\text{Copay Reduction} = \text{Amount Subject to Copay} \times \frac{\text{Copay Percentage}}{100}$$
$$\text{Net Settlement} = \max(0, \text{Amount Subject to Copay} - \text{Copay Reduction})$$

---

## 5. Synthetic Data Generation & Evaluation Requirements

1. **Deterministic Reproducibility**:
   - Seeded via `SYNTHETIC_DATA_RANDOM_SEED` (default: `42`).
   - Ensures identical dataset generation across test runs, CI pipelines, and benchmarking harnesses.
2. **Realistic Distributions**:
   - Claim amounts follow a log-normal distribution parameterized by claim type (Auto median ~$3,500; Home median ~$12,000; Commercial median ~$45,000).
   - Realistic incident date ranges spanning past 12 months.
   - Inject controlled percentage of negative scenarios:
     - ~5% Expired policies (NEG-01)
     - ~5% Uncovered perils (NEG-02)
     - ~8% Untimely filings (NEG-03)
     - ~7% Missing documents (NEG-04)
     - ~5% Over-limit claims (NEG-05)
     - ~3% Suspended policies / Duplicates (NEG-06)
3. **Ground-Truth Labeling**:
   - Synthetic records must generate explicit sidecar ground-truth columns:
     - `gt_is_eligible`: Boolean
     - `gt_rejection_code`: Optional String
     - `gt_expected_indemnity_reserve`: Decimal
     - `gt_expected_net_settlement`: Decimal
4. **Evaluation Metrics**:
   - **Classification Metrics (Rules Engine vs. Ground Truth)**:
     - Precision, Recall, F1-Score for Eligibility (overall and per negative scenario).
     - False Positive Rate (FPR) and False Negative Rate (FNR).
   - **Financial Estimation Metrics**:
     - Mean Absolute Error (MAE) for Reserve Calculation.
     - Root Mean Squared Error (RMSE) for Reserve Calculation.
   - **System Performance & Auditability**:
     - Straight-Through Processing (STP) Rate: Percentage of clean claims resolved without human intervention.
     - Audit Trace Coverage: 100% of state transitions must possess corresponding `AuditEvent` records.

---

## 6. Architectural Constraints & Non-Functional Requirements

- **Layered Decoupling**: Direct DB queries are prohibited in routes and services. All DB interactions occur through Repositories.
- **Stateless Rules Engine**: The rules engine must accept pure data objects (Pydantic / Dataclasses) and return immutable decision objects without side effects.
- **Transactional Integrity**: Claim state transitions, reserve calculations, and settlement approvals must run inside atomic database transactions with rollback on failure.
- **No Secrets in Code**: All credentials, keys, and environment-specific configs load strictly from `.env` via `pydantic-settings`.
- **Zero Real PII**: Synthetic data generator uses Faker and mathematical generators; no proprietary or real personal data is ever introduced.
