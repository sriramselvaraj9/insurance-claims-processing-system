"""Deterministic ID generator for domain entities.

Follows strict immutable string-based naming conventions:
- Policy: POL-<product>-2026-000001
- Claim: CLM-2026-000001
- Document: DOC-<claim-id>-001
- Adjuster assignment: ASN-<claim-id>-001
- Settlement: SET-<claim-id>-001
- Customer: CUST-2026-000001
- Incident: INC-2026-000001
- Adjuster: ADJ-2026-000001
- Assessment: ASM-<claim-id>-001
- Reserve: RES-<claim-id>-001
- ClaimItem: ITM-<claim-id>-001
- DocumentRequest: REQ-<claim-id>-001
- SettlementPayment: PAY-<settlement-id>-001
- AuditEvent: AUD-2026-000001
- ClaimStatusHistory: CSH-<claim-id>-001
"""


class IdGenerator:
    DEFAULT_YEAR: int = 2026
    GLOBAL_WIDTH: int = 6
    CHILD_WIDTH: int = 3

    @classmethod
    def customer_id(cls, sequence: int, year: int = DEFAULT_YEAR) -> str:
        return f"CUST-{year}-{sequence:0{cls.GLOBAL_WIDTH}d}"

    @classmethod
    def policy_id(cls, product: str, sequence: int, year: int = DEFAULT_YEAR) -> str:
        clean_product = product.upper().strip()
        return f"POL-{clean_product}-{year}-{sequence:0{cls.GLOBAL_WIDTH}d}"

    @classmethod
    def coverage_id(cls, policy_id: str, sequence: int) -> str:
        return f"COV-{policy_id}-{sequence:0{cls.CHILD_WIDTH}d}"

    @classmethod
    def incident_id(cls, sequence: int, year: int = DEFAULT_YEAR) -> str:
        return f"INC-{year}-{sequence:0{cls.GLOBAL_WIDTH}d}"

    @classmethod
    def claim_id(cls, sequence: int, year: int = DEFAULT_YEAR) -> str:
        return f"CLM-{year}-{sequence:0{cls.GLOBAL_WIDTH}d}"

    @classmethod
    def claim_item_id(cls, claim_id: str, sequence: int) -> str:
        return f"ITM-{claim_id}-{sequence:0{cls.CHILD_WIDTH}d}"

    @classmethod
    def document_id(cls, claim_id: str, sequence: int) -> str:
        return f"DOC-{claim_id}-{sequence:0{cls.CHILD_WIDTH}d}"

    @classmethod
    def document_request_id(cls, claim_id: str, sequence: int) -> str:
        return f"REQ-{claim_id}-{sequence:0{cls.CHILD_WIDTH}d}"

    @classmethod
    def adjuster_id(cls, sequence: int, year: int = DEFAULT_YEAR) -> str:
        return f"ADJ-{year}-{sequence:0{cls.GLOBAL_WIDTH}d}"

    @classmethod
    def adjuster_assignment_id(cls, claim_id: str, sequence: int) -> str:
        return f"ASN-{claim_id}-{sequence:0{cls.CHILD_WIDTH}d}"

    @classmethod
    def assessment_id(cls, claim_id: str, sequence: int) -> str:
        return f"ASM-{claim_id}-{sequence:0{cls.CHILD_WIDTH}d}"

    @classmethod
    def reserve_id(cls, claim_id: str, sequence: int) -> str:
        return f"RES-{claim_id}-{sequence:0{cls.CHILD_WIDTH}d}"

    @classmethod
    def settlement_id(cls, claim_id: str, sequence: int) -> str:
        return f"SET-{claim_id}-{sequence:0{cls.CHILD_WIDTH}d}"

    @classmethod
    def settlement_payment_id(cls, settlement_id: str, sequence: int) -> str:
        return f"PAY-{settlement_id}-{sequence:0{cls.CHILD_WIDTH}d}"

    @classmethod
    def audit_event_id(cls, sequence: int, year: int = DEFAULT_YEAR) -> str:
        return f"AUD-{year}-{sequence:0{cls.GLOBAL_WIDTH}d}"

    @classmethod
    def claim_status_history_id(cls, claim_id: str, sequence: int) -> str:
        return f"CSH-{claim_id}-{sequence:0{cls.CHILD_WIDTH}d}"

