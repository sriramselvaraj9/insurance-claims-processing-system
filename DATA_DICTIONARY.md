# Data Dictionary: Insurance Claims Processing System

**Assessment Provider**: YottaFlex AI Recruitment Technical Assessment  
**System**: Insurance Claims Processing, Rules Engine, and Evaluation Platform  
**Document Version**: 3.0.0 (Phase 3 Core Processing Engine Baseline)  

---

## 1. Overview & Type Standards

- **Identifiers**: Immutable string identifiers (e.g. `CLM-2026-000001`, `POL-AUTO-2026-000001`).
- **Monetary Values**: Stored as SQL `Numeric(12, 2)` or `Numeric(10, 2)` representing USD fixed-point currency. Floating-point types are strictly forbidden.
- **Timestamps**: Timezone-aware UTC timestamps (`DateTime(timezone=True)`).
- **Dates**: Calendar dates (`Date` format `YYYY-MM-DD`).
- **Enums**: Strongly-typed string-backed enums (`StrEnum`) ensuring cross-database compatibility.

---

## 2. Core Entity Dictionaries

### 2.1 Customer (`customers`)
Represents the insured individual or corporate entity holding insurance policies.

| Field Name | DB Type | Nullable | Allowed Values / Format | Units | Uniqueness | Constraints / Validation | Key Type | Cardinality |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `id` | `String(50)` | No | `CUST-YYYY-NNNNNN` | String | Unique | Must match ID format | PK | - |
| `first_name` | `String(100)` | No | Letters, hyphens, spaces | - | No | Length 1-100 | - | - |
| `last_name` | `String(100)` | No | Letters, hyphens, spaces | - | No | Length 1-100 | - | - |
| `email` | `String(255)` | No | Valid email address | - | Unique | Valid RFC-5322 email | - | - |
| `phone` | `String(30)` | No | E.164 phone format | - | No | e.g. `+1-555-0199` | - | - |
| `date_of_birth` | `Date` | No | `YYYY-MM-DD` | Date | No | Age >= 18 | - | - |
| `kyc_status` | `String(30)` | No | `PENDING`, `VERIFIED`, `REJECTED`, `FLAGGED` | Enum | No | Default `PENDING` | - | - |
| `risk_profile` | `String(20)` | No | `LOW`, `MEDIUM`, `HIGH` | Enum | No | Default `MEDIUM` | - | - |
| `created_at` | `DateTime(tz)` | No | UTC timestamp | Time | No | `server_default=now()` | - | - |
| `updated_at` | `DateTime(tz)` | No | UTC timestamp | Time | No | `onupdate=now()` | - | - |

- **Relationships**:
  - `policies`: 1:N with `Policy`
  - `claims`: 1:N with `Claim`

---

### 2.2 Policy (`policies`)
The legal insurance contract issued to a customer governing coverage terms.

| Field Name | DB Type | Nullable | Allowed Values / Format | Units | Uniqueness | Constraints / Validation | Key Type | Cardinality |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `id` | `String(60)` | No | `POL-<PRODUCT>-YYYY-NNNNNN` | String | Unique | Product: AUTO/HOME/HEALTH/COMMERCIAL | PK | - |
| `customer_id` | `String(50)` | No | References `customers.id` | String | No | Valid customer foreign key | FK | N:1 Customer |
| `policy_type` | `String(30)` | No | `AUTO`, `HOME`, `HEALTH`, `COMMERCIAL` | Enum | No | Non-null | - | - |
| `status` | `String(30)` | No | `DRAFT`, `ACTIVE`, `SUSPENDED`, `EXPIRED`, `CANCELLED` | Enum | No | Default `DRAFT` | - | - |
| `effective_date`| `Date` | No | `YYYY-MM-DD` | Date | No | Start date | - | - |
| `expiration_date`| `Date`| No | `YYYY-MM-DD` | Date | No | `expiration_date > effective_date` | - | - |
| `cancellation_date`|`Date`| Yes | `YYYY-MM-DD` | Date | No | Null if active | - | - |
| `total_premium` | `Numeric(12, 2)`| No | Value >= 0.00 | USD | No | CheckConstraint `>= 0` | - | - |
| `deductible` | `Numeric(10, 2)`| No | Value >= 0.00 | USD | No | Base policy deductible | - | - |
| `created_at` | `DateTime(tz)` | No | UTC timestamp | Time | No | `server_default=now()` | - | - |
| `updated_at` | `DateTime(tz)` | No | UTC timestamp | Time | No | `onupdate=now()` | - | - |

- **Relationships**:
  - `customer`: N:1 with `Customer`
  - `coverages`: 1:N with `Coverage`
  - `claims`: 1:N with `Claim`

---

### 2.3 Coverage (`coverages`)
Specific protection clauses attached to a policy defining limits, deductibles, and exclusions.

| Field Name | DB Type | Nullable | Allowed Values / Format | Units | Uniqueness | Constraints / Validation | Key Type | Cardinality |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `id` | `String(80)` | No | `COV-<POLICY_ID>-NNN` | String | Unique | Sequential index per policy | PK | - |
| `policy_id` | `String(60)` | No | References `policies.id` | String | No | Valid policy foreign key | FK | N:1 Policy |
| `coverage_type` | `String(50)` | No | `COLLISION`, `COMPREHENSIVE`, `LIABILITY`, `DWELLING`, `PERSONAL_PROPERTY`, `MEDICAL_PAYMENTS`, `BODILY_INJURY` | Enum | No | Non-null | - | - |
| `coverage_limit`| `Numeric(12, 2)`| No | Value > 0.00 | USD | No | CheckConstraint `limit > 0` | - | - |
| `deductible` | `Numeric(10, 2)`| No | Value >= 0.00 | USD | No | CheckConstraint `deductible >= 0` | - | - |
| `copay_percentage`| `Numeric(5, 2)`| No | 0.00 to 100.00 | % | No | CheckConstraint `0 <= copay <= 100` | - | - |
| `exclusions` | `JSON` | Yes | List of exclusion strings | JSON | No | Optional exclusion clauses | - | - |
| `effective_date`| `Date` | No | `YYYY-MM-DD` | Date | No | Defaults to policy effective date | - | - |
| `expiration_date`| `Date`| No | `YYYY-MM-DD` | Date | No | Defaults to policy expiration date | - | - |
| `is_active` | `Boolean` | No | `True`, `False` | Bool | No | Default `True` | - | - |
| `created_at` | `DateTime(tz)` | No | UTC timestamp | Time | No | `server_default=now()` | - | - |
| `updated_at` | `DateTime(tz)` | No | UTC timestamp | Time | No | `onupdate=now()` | - | - |

- **Relationships**:
  - `policy`: N:1 with `Policy`
  - `claim_items`: 1:N with `ClaimItem`

---

### 2.4 Incident (`incidents`)
Physical occurrence or casualty event resulting in potential insurance losses. Multiple claims can reference a single shared incident.

| Field Name | DB Type | Nullable | Allowed Values / Format | Units | Uniqueness | Constraints / Validation | Key Type | Cardinality |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `id` | `String(50)` | No | `INC-YYYY-NNNNNN` | String | Unique | Format compliance | PK | - |
| `incident_type` | `String(50)` | No | `VEHICLE_COLLISION`, `THEFT`, `FIRE`, `WATER_LEAK`, `HAIL_STORM`, `BODILY_INJURY`, `SLIP_AND_FALL`, `OTHER` | Enum | No | Non-null | - | - |
| `occurrence_date`|`DateTime(tz)`| No | UTC timestamp | Time | No | Cannot be in future | - | - |
| `description` | `Text` | No | Minimum 10 characters | Text | No | Detailed description | - | - |
| `location_street`| `String(255)` | No | Street address | Text | No | Location details | - | - |
| `location_city` | `String(100)` | No | City name | Text | No | City | - | - |
| `location_state`| `String(50)` | No | State/Province code | Text | No | e.g. `CA`, `NY`, `TX` | - | - |
| `location_zip` | `String(20)` | No | Postal code | Text | No | Valid postal code | - | - |
| `police_report_filed`|`Boolean`| No | `True`, `False` | Bool | No | Default `False` | - | - |
| `police_report_number`|`String(100)`| Yes | Alphanumeric | Text | No | Required if report filed | - | - |
| `created_at` | `DateTime(tz)` | No | UTC timestamp | Time | No | `server_default=now()` | - | - |
| `updated_at` | `DateTime(tz)` | No | UTC timestamp | Time | No | `onupdate=now()` | - | - |

- **Relationships**:
  - `claims`: 1:N with `Claim`

---

### 2.5 Claim (`claims`)
Formal request for coverage and indemnification filed by an insured customer.

| Field Name | DB Type | Nullable | Allowed Values / Format | Units | Uniqueness | Constraints / Validation | Key Type | Cardinality |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `id` | `String(50)` | No | `CLM-YYYY-NNNNNN` | String | Unique | Format compliance | PK | - |
| `customer_id` | `String(50)` | No | References `customers.id` | String | No | Valid customer FK | FK | N:1 Customer |
| `policy_id` | `String(60)` | No | References `policies.id` | String | No | Valid policy FK | FK | N:1 Policy |
| `incident_id` | `String(50)` | No | References `incidents.id` | String | No | Valid incident FK | FK | N:1 Incident |
| `claim_type` | `String(50)` | No | Matches Coverage / Peril | Enum | No | Non-null | - | - |
| `status` | `String(30)` | No | `SUBMITTED`, `UNDER_REVIEW`, `INFO_REQUESTED`, `ELIGIBLE`, `INELIGIBLE`, `ADJUSTER_ASSIGNED`, `RESERVE_CALCULATED`, `SETTLEMENT_RECOMMENDED`, `APPROVED`, `SETTLED`, `REJECTED`, `CLOSED`, `FLAGGED` | Enum | No | Default `SUBMITTED` | - | - |
| `reported_date` | `DateTime(tz)` | No | UTC timestamp | Time | No | `reported_date >= incident.occurrence_date` | - | - |
| `claimed_amount`| `Numeric(12, 2)`| No | Value >= 0.00 | USD | No | CheckConstraint `>= 0` | - | - |
| `estimated_loss`| `Numeric(12, 2)`| No | Value >= 0.00 | USD | No | CheckConstraint `>= 0` | - | - |
| `description` | `Text` | No | Free text | Text | No | Minimum 10 characters | - | - |
| `assigned_adjuster_id`|`String(50)`| Yes | References `adjusters.id` | String | No | Nullable until assignment | FK | N:1 Adjuster |
| `created_at` | `DateTime(tz)` | No | UTC timestamp | Time | No | `server_default=now()` | - | - |
| `updated_at` | `DateTime(tz)` | No | UTC timestamp | Time | No | `onupdate=now()` | - | - |

- **Relationships**:
  - `customer`: N:1 with `Customer`
  - `policy`: N:1 with `Policy`
  - `incident`: N:1 with `Incident`
  - `claim_items`: 1:N with `ClaimItem`
  - `documents`: 1:N with `Document`
  - `assessments`: 1:N with `Assessment`
  - `reserves`: 1:N with `Reserve`
  - `settlements`: 1:N with `Settlement`
  - `status_history`: 1:N with `ClaimStatusHistory`
  - `adjuster_assignments`: 1:N with `AdjusterAssignment`

---

### 2.6 ClaimItem (`claim_items`)
Itemized line-item losses or damages comprising a claim.

| Field Name | DB Type | Nullable | Allowed Values / Format | Units | Uniqueness | Constraints / Validation | Key Type | Cardinality |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `id` | `String(70)` | No | `ITM-<CLAIM_ID>-NNN` | String | Unique | Format compliance | PK | - |
| `claim_id` | `String(50)` | No | References `claims.id` | String | No | Valid claim FK | FK | N:1 Claim |
| `coverage_id` | `String(80)` | Yes | References `coverages.id` | String | No | Optional coverage link | FK | N:1 Coverage |
| `item_description`|`String(255)`| No | Description of damaged item | Text | No | Non-null | - | - |
| `quantity` | `Integer` | No | Value >= 1 | Int | No | CheckConstraint `quantity >= 1` | - | - |
| `unit_amount` | `Numeric(12, 2)`| No | Value >= 0.00 | USD | No | CheckConstraint `unit_amount >= 0` | - | - |
| `total_amount` | `Numeric(12, 2)`| No | `quantity * unit_amount` | USD | No | CheckConstraint `total_amount >= 0` | - | - |
| `created_at` | `DateTime(tz)` | No | UTC timestamp | Time | No | `server_default=now()` | - | - |

---

### 2.7 Document (`documents`)
Evidentiary files supporting a claim.

| Field Name | DB Type | Nullable | Allowed Values / Format | Units | Uniqueness | Constraints / Validation | Key Type | Cardinality |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `id` | `String(70)` | No | `DOC-<CLAIM_ID>-NNN` | String | Unique | Format compliance | PK | - |
| `claim_id` | `String(50)` | No | References `claims.id` | String | No | Valid claim FK | FK | N:1 Claim |
| `document_type` | `String(50)` | No | `POLICE_REPORT`, `MEDICAL_BILL`, `REPAIR_ESTIMATE`, `PROOF_OF_LOSS`, `DAMAGE_PHOTO`, `OTHER` | Enum | No | Non-null | - | - |
| `file_name` | `String(255)` | No | Valid filename | Text | No | e.g. `police_report.pdf` | - | - |
| `file_type` | `String(100)` | No | MIME type | Text | No | e.g. `application/pdf` | - | - |
| `file_path` | `String(500)` | No | Storage URI / path | Text | No | Non-null | - | - |
| `file_size_bytes`|`BigInteger` | No | Value > 0 | Bytes | No | CheckConstraint `file_size > 0` | - | - |
| `checksum_sha256`|`String(64)` | No | 64-character hex hash | Hash | No | Valid SHA-256 digest | - | - |
| `submission_date`|`DateTime(tz)` | No | UTC timestamp | Time | No | `server_default=now()` | - | - |
| `verification_status`|`String(30)`| No | `PENDING`, `VERIFIED`, `REJECTED` | Enum | No | Default `PENDING` | - | - |
| `verified_at` | `DateTime(tz)` | Yes | UTC timestamp | Time | No | Null until verified | - | - |
| `verified_by` | `String(100)` | Yes | Assessor/Adjuster ID | Text | No | Null until verified | - | - |
| `rejection_reason`|`Text` | Yes | Explanation | Text | No | Populated if rejected | - | - |
| `created_at` | `DateTime(tz)` | No | UTC timestamp | Time | No | `server_default=now()` | - | - |

- **Relationships**:
  - `document_requests`: 1:N with `DocumentRequest`

---

### 2.8 Adjuster (`adjusters`)
Insurance claims professional handling investigation and settlement reviews.

| Field Name | DB Type | Nullable | Allowed Values / Format | Units | Uniqueness | Constraints / Validation | Key Type | Cardinality |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `id` | `String(50)` | No | `ADJ-YYYY-NNNNNN` | String | Unique | Format compliance | PK | - |
| `employee_id` | `String(50)` | No | Alphanumeric | String | Unique | Internal employee ID | - | - |
| `name` | `String(150)` | No | Full name | Text | No | Non-null | - | - |
| `email` | `String(255)` | No | Valid email | Text | Unique | Unique work email | - | - |
| `phone` | `String(30)` | No | E.164 phone | Text | No | Phone number | - | - |
| `specialization`| `String(50)` | No | `AUTO`, `PROPERTY`, `HEALTH`, `COMMERCIAL`, `GENERAL` | Enum | No | Domain specialization | - | - |
| `active_claims_count`|`Integer` | No | Value >= 0 | Int | No | Default 0; CheckConstraint `>= 0` | - | - |
| `max_capacity` | `Integer` | No | Value > 0 | Int | No | Default 20; CheckConstraint `> 0` | - | - |
| `status` | `String(30)` | No | `ACTIVE`, `ON_LEAVE`, `INACTIVE` | Enum | No | Default `ACTIVE` | - | - |
| `created_at` | `DateTime(tz)` | No | UTC timestamp | Time | No | `server_default=now()` | - | - |
| `updated_at` | `DateTime(tz)` | No | UTC timestamp | Time | No | `onupdate=now()` | - | - |

- **Relationships**:
  - `claims`: 1:N with `Claim`
  - `assignments`: 1:N with `AdjusterAssignment`

---

### 2.9 Assessment (`assessments`)
Eligibility evaluation record assessing policy status, coverage eligibility, timely notice, and exclusions. Reassessments append new records.

| Field Name | DB Type | Nullable | Allowed Values / Format | Units | Uniqueness | Constraints / Validation | Key Type | Cardinality |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `id` | `String(70)` | No | `ASM-<CLAIM_ID>-NNN` | String | Unique | Format compliance | PK | - |
| `claim_id` | `String(50)` | No | References `claims.id` | String | No | Valid claim FK | FK | N:1 Claim |
| `is_eligible` | `Boolean` | No | `True`, `False` | Bool | No | Overall eligibility outcome | - | - |
| `policy_active_check`|`Boolean`| No | `True`, `False` | Bool | No | Evaluates NEG-01 | - | - |
| `incident_covered_check`|`Boolean`| No | `True`, `False` | Bool | No | Evaluates NEG-02 | - | - |
| `timely_filing_check`|`Boolean`| No | `True`, `False` | Bool | No | Evaluates NEG-03 | - | - |
| `exclusions_check`|`Boolean` | No | `True`, `False` | Bool | No | True if no exclusions apply | - | - |
| `documentation_complete_check`|`Boolean`| No | `True`, `False` | Bool | No | Evaluates NEG-04 | - | - |
| `fraud_check_passed`|`Boolean`| No | `True`, `False` | Bool | No | Evaluates NEG-06 | - | - |
| `decision_reasons`| `JSON` | No | List of rationale strings | JSON | No | JSON array of reasons | - | - |
| `rejection_code`| `String(50)` | Yes | Rejection code enum | Enum | No | Null if eligible | - | - |
| `assessed_at` | `DateTime(tz)` | No | UTC timestamp | Time | No | Timestamp of evaluation | - | - |
| `assessed_by` | `String(100)` | No | System rule or User ID | Text | No | e.g. `RULE_ENGINE_V1` | - | - |
| `created_at` | `DateTime(tz)` | No | UTC timestamp | Time | No | `server_default=now()` | - | - |

---

### 2.10 Reserve (`reserves`)
Financial liability allocation for indemnity and loss adjustment expenses.

| Field Name | DB Type | Nullable | Allowed Values / Format | Units | Uniqueness | Constraints / Validation | Key Type | Cardinality |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `id` | `String(70)` | No | `RES-<CLAIM_ID>-NNN` | String | Unique | Format compliance | PK | - |
| `claim_id` | `String(50)` | No | References `claims.id` | String | No | Valid claim FK | FK | N:1 Claim |
| `estimated_indemnity_reserve`|`Numeric(12, 2)`| No | Value >= 0.00 | USD | No | CheckConstraint `>= 0` | - | - |
| `estimated_expense_reserve`|`Numeric(12, 2)`| No | Value >= 0.00 | USD | No | CheckConstraint `>= 0` | - | - |
| `total_reserve` | `Numeric(12, 2)`| No | `indemnity + expense` | USD | No | Total sum check | - | - |
| `expense_ratio` | `Numeric(5, 4)` | No | Default 0.1200 | Ratio | No | Actuarial ratio (12%) | - | - |
| `calculation_method`|`String(50)`| No | `FORMULAIC_STANDARD`, `ACTUARIAL_WEIGHTED`, `EXPERT_OVERRIDE` | Enum | No | Non-null | - | - |
| `calculated_at` | `DateTime(tz)` | No | UTC timestamp | Time | No | Evaluation time | - | - |
| `calculated_by` | `String(100)` | No | User/Rule identifier | Text | No | Non-null | - | - |
| `created_at` | `DateTime(tz)` | No | UTC timestamp | Time | No | `server_default=now()` | - | - |

---

### 2.11 Settlement (`settlements`)
Resolution proposal and disbursement adjudication for a claim.

| Field Name | DB Type | Nullable | Allowed Values / Format | Units | Uniqueness | Constraints / Validation | Key Type | Cardinality |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `id` | `String(70)` | No | `SET-<CLAIM_ID>-NNN` | String | Unique | Format compliance | PK | - |
| `claim_id` | `String(50)` | No | References `claims.id` | String | No | Valid claim FK | FK | N:1 Claim |
| `recommended_amount`|`Numeric(12, 2)`| No | Value >= 0.00 | USD | No | CheckConstraint `>= 0` | - | - |
| `approved_amount`|`Numeric(12, 2)`| Yes | Value >= 0.00 | USD | No | Approved by supervisor | - | - |
| `deductible_applied`|`Numeric(10, 2)`| No | Value >= 0.00 | USD | No | Applied deductible | - | - |
| `copay_applied` | `Numeric(10, 2)`| No | Value >= 0.00 | USD | No | Applied copay | - | - |
| `net_settlement_amount`|`Numeric(12, 2)`| No | Value >= 0.00 | USD | No | CheckConstraint `>= 0` | - | - |
| `status` | `String(30)` | No | `PROPOSED`, `SUPERVISOR_REVIEW`, `APPROVED`, `REJECTED`, `DISBURSED` | Enum | No | Default `PROPOSED` | - | - |
| `settled_at` | `DateTime(tz)` | Yes | UTC timestamp | Time | No | Null until final approval | - | - |
| `settled_by` | `String(100)` | Yes | User/Supervisor ID | Text | No | Reviewer identity | - | - |
| `payment_reference`|`String(100)`| Yes | e.g. `EFT-88491` | Text | No | Generated on payout | - | - |
| `created_at` | `DateTime(tz)` | No | UTC timestamp | Time | No | `server_default=now()` | - | - |
| `updated_at` | `DateTime(tz)` | No | UTC timestamp | Time | No | `onupdate=now()` | - | - |

- **Relationships**:
  - `payments`: 1:N with `SettlementPayment`

---

## 3. Supporting Audit & History Tables

### 3.1 AdjusterAssignment (`adjuster_assignments`)
Tracks the lifecycle of claim assignments to adjusters without overwriting history.

| Field Name | DB Type | Nullable | Allowed Values | Key Type | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `id` | `String(70)` | No | `ASN-<CLAIM_ID>-NNN` | PK | Unique assignment identifier |
| `claim_id` | `String(50)` | No | References `claims.id` | FK | Associated claim |
| `adjuster_id` | `String(50)` | No | References `adjusters.id` | FK | Assigned adjuster |
| `assigned_at` | `DateTime(tz)` | No | UTC timestamp | - | Timestamp when assignment occurred |
| `unassigned_at` | `DateTime(tz)` | Yes | UTC timestamp | - | Null if currently active assignment |
| `assignment_reason`|`String(255)` | No | Initial assignment / Reassignment / Escalation | - | Context for assignment |
| `is_active` | `Boolean` | No | `True`, `False` | - | True for current active assignment |

---

### 3.2 DocumentRequest (`document_requests`)
Tracks requests for missing or defective documents triggered by `NEG-04`.

| Field Name | DB Type | Nullable | Allowed Values | Key Type | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `id` | `String(70)` | No | `REQ-<CLAIM_ID>-NNN` | PK | Unique request identifier |
| `claim_id` | `String(50)` | No | References `claims.id` | FK | Associated claim |
| `document_type` | `String(50)` | No | Required document type | - | Missing document type |
| `requested_at` | `DateTime(tz)` | No | UTC timestamp | - | When request was emitted |
| `status` | `String(30)` | No | `OPEN`, `FULFILLED`, `WAIVED` | - | Default `OPEN` |
| `fulfilled_document_id`|`String(70)`| Yes | References `documents.id` | FK | Document that fulfilled request |

---

### 3.3 SettlementPayment (`settlement_payments`)
Disbursement history preventing duplicate payouts and tracking transaction references.

| Field Name | DB Type | Nullable | Allowed Values | Key Type | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `id` | `String(80)` | No | `PAY-<SETTLEMENT_ID>-NNN` | PK | Unique payment record |
| `settlement_id` | `String(70)` | No | References `settlements.id` | FK | Associated settlement |
| `payment_amount`| `Numeric(12, 2)`| No | Value > 0.00 | - | Disbursed amount |
| `payment_method`| `String(50)` | No | `ACH`, `WIRE`, `CHECK` | - | Disbursement method |
| `payment_reference`|`String(100)`| No | Unique transaction reference | - | Bank or processor reference |
| `payment_date` | `DateTime(tz)` | No | UTC timestamp | - | Disbursement timestamp |
| `status` | `String(30)` | No | `PENDING`, `COMPLETED`, `FAILED` | - | Default `PENDING` |

---

### 3.4 ClaimStatusHistory (`claim_status_history`)
Append-only history of every lifecycle status transition for a claim.

| Field Name | DB Type | Nullable | Allowed Values | Key Type | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `id` | `String(70)` | No | `CSH-<CLAIM_ID>-NNN` | PK | Unique history record ID |
| `claim_id` | `String(50)` | No | References `claims.id` | FK | Associated claim |
| `previous_status`|`String(30)`| Yes | ClaimStatus enum value | - | Null on initial creation |
| `new_status` | `String(30)` | No | ClaimStatus enum value | - | Current state entered |
| `transition_reason`|`Text` | Yes | Rationale or trigger event | - | Reason for status change |
| `changed_by` | `String(100)` | No | User ID or System Actor | - | Initiating actor |
| `timestamp` | `DateTime(tz)` | No | UTC timestamp | - | `server_default=now()` |

---

### 3.5 AuditEvent (`audit_events`)
Global, immutable enterprise change-log recording all system mutations.

| Field Name | DB Type | Nullable | Allowed Values | Key Type | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `id` | `String(50)` | No | `AUD-YYYY-NNNNNN` | PK | Unique audit event ID |
| `entity_type` | `String(50)` | No | e.g. `Claim`, `Settlement`, `Policy` | - | Entity class name |
| `entity_id` | `String(80)` | No | Target entity ID | - | Entity instance identifier |
| `action` | `String(30)` | No | `CREATE`, `UPDATE`, `STATE_TRANSITION`, `DELETE`, `OVERRIDE` | - | Action performed |
| `state_before` | `JSON` | Yes | Prior entity snapshot | - | JSON serialized state |
| `state_after` | `JSON` | Yes | Updated entity snapshot | - | JSON serialized state |
| `actor_type` | `String(30)` | No | `SYSTEM_RULE`, `USER_ADJUSTER`, `USER_ADMIN`, `API_SERVICE` | - | Type of actor |
| `actor_id` | `String(100)` | No | Actor identifier | - | ID of user or subsystem |
| `timestamp` | `DateTime(tz)` | No | UTC timestamp | - | Occurrence timestamp |
| `metadata_` | `JSON` | Yes | Additional contextual metadata | - | Contextual payload |

---

## 4. Enumerations & Domain Codes

### 4.1 Assessment Outcomes (`AssessmentOutcome`)
| Value | Description |
|---|---|
| `ELIGIBLE` | Passed all policy, coverage, statutory, and document validations. Ready for reserve calculation & settlement recommendation. |
| `INELIGIBLE` | Hard rejection due to expired policy, uncovered peril, exclusion clause, late notice (>30 days), or ownership mismatch. |
| `PENDING_DOCUMENTS` | Valid policy and covered peril, but mandatory evidence documents are missing or unverified. Triggers `DocumentRequest`. |
| `MANUAL_REVIEW` | Quarantined for Special Investigation Unit (SIU) or human adjuster review due to fraud indicator or duplicate detection. |

### 4.2 Rejection Codes (`RejectionCode`)
| Code | Reason |
|---|---|
| `EXPIRED_POLICY` | Incident date occurred outside policy inception or after policy cancellation/expiration (NEG-01). |
| `UNCOVERED_PERIL` | Claim type/peril is not covered under active policy coverages (NEG-02). |
| `POLICY_EXCLUSION` | Peril is explicitly excluded under policy coverage terms (NEG-02). |
| `UNTIMELY_FILING` | Notice of claim filed > 30 days post-casualty, violating statutory notice limit (NEG-03). |
| `MISSING_MANDATORY_DOCUMENTS` | Mandatory evidentiary documents not provided or unverified (NEG-04). |
| `DUPLICATE_CLAIM` | Identical claim already filed for same policy, incident, and amount (NEG-06). |
| `SUSPECTED_FRAUD` | High-risk indicators (filing near inception, excessive claimed amount, duplicate incident) (NEG-06). |
| `SUSPENDED_POLICY` | Casualty occurred while policy coverage was temporarily suspended. |
| `POLICY_OWNERSHIP_MISMATCH` | Claim submitted by customer who does not hold legal ownership of the policy. |

### 4.3 Audit Actions (`AuditAction`)
Includes `CREATE`, `UPDATE`, `STATE_TRANSITION`, `DELETE`, `OVERRIDE`, `CLAIM_CREATED`, `POLICY_VALIDATED`, `COVERAGE_VALIDATED`, `DOCUMENT_VERIFIED`, `DOCUMENT_REQUESTED`, `ASSESSMENT_COMPLETED`, `MANUAL_REVIEW_REQUIRED`, `ADJUSTER_ASSIGNED`, `RESERVE_CALCULATED`, `SETTLEMENT_RECOMMENDED`, `SETTLEMENT_APPROVED`, `SETTLEMENT_BLOCKED`, `PAYMENT_DISBURSED`.


