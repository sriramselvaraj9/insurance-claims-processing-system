# Synthetic Data Quality Validation Report

- **Status**: `PASSED`
- **Validated At**: `2026-11-07T04:59:13.019410+00:00`
- **Total Tables Checked**: `16`
- **Total Records Checked**: `22,933`
- **Error Count**: `0`

## Table Record Counts

| Table Name | Record Count |
| :--- | :--- |
| `customers` | 1,200 |
| `policies` | 2,000 |
| `coverages` | 5,103 |
| `incidents` | 1,000 |
| `adjusters` | 25 |
| `claims` | 1,000 |
| `claim_items` | 1,963 |
| `documents` | 2,375 |
| `assessments` | 1,000 |
| `reserves` | 1,000 |
| `settlements` | 373 |
| `adjuster_assignments` | 1,000 |
| `document_requests` | 25 |
| `settlement_payments` | 368 |
| `claim_status_history` | 2,501 |
| `audit_events` | 2,000 |

## Ground Truth Anomaly Breakdown

| Anomaly Issue Type | Count |
| :--- | :--- |
| `MISSING_MANDATORY_DOCUMENT` | 25 |
| `DATE_BEFORE_POLICY_START` | 20 |
| `POLICY_CANCELLED_BEFORE_INCIDENT` | 15 |
| `UNCOVERED_PERIL` | 15 |
| `UNTIMELY_FILING` | 15 |
| `EXCESSIVE_CLAIM_AMOUNT` | 15 |
| `SETTLEMENT_EXCEEDS_COVERAGE_LIMIT` | 15 |
| `DUPLICATE_CLAIM` | 15 |
| `DUPLICATE_INCIDENT` | 15 |
| `CLAIM_PAID_TWICE` | 15 |
