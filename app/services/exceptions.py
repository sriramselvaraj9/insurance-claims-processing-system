"""Domain exceptions for insurance claims processing services."""


class ClaimsServiceError(Exception):
    """Base domain exception for all claims processing services."""
    def __init__(self, message: str, entity_id: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.entity_id = entity_id


class ClaimNotFoundError(ClaimsServiceError):
    def __init__(self, claim_id: str) -> None:
        super().__init__(f"Claim '{claim_id}' not found", entity_id=claim_id)


class PolicyNotFoundError(ClaimsServiceError):
    def __init__(self, policy_id: str) -> None:
        super().__init__(f"Policy '{policy_id}' not found", entity_id=policy_id)


class CustomerNotFoundError(ClaimsServiceError):
    def __init__(self, customer_id: str) -> None:
        super().__init__(f"Customer '{customer_id}' not found", entity_id=customer_id)


class IncidentNotFoundError(ClaimsServiceError):
    def __init__(self, incident_id: str) -> None:
        super().__init__(f"Incident '{incident_id}' not found", entity_id=incident_id)


class CustomerPolicyMismatchError(ClaimsServiceError):
    def __init__(self, claim_customer_id: str, policy_customer_id: str, policy_id: str) -> None:
        super().__init__(
            f"Customer '{claim_customer_id}' does not own policy '{policy_id}' (owned by '{policy_customer_id}')",
            entity_id=policy_id,
        )
        self.claim_customer_id = claim_customer_id
        self.policy_customer_id = policy_customer_id


class MissingCoverageError(ClaimsServiceError):
    def __init__(self, policy_id: str, claim_type: str) -> None:
        super().__init__(
            f"Policy '{policy_id}' lacks active coverage clause for peril '{claim_type}'",
            entity_id=policy_id,
        )
        self.claim_type = claim_type


class InvalidFinancialValueError(ClaimsServiceError):
    def __init__(self, field_name: str, value: str, reason: str) -> None:
        super().__init__(f"Invalid financial value for {field_name} ({value}): {reason}")
        self.field_name = field_name
        self.value = value


class NoEligibleAdjusterError(ClaimsServiceError):
    def __init__(self, specialization: str, reason: str = "No adjuster with capacity found") -> None:
        super().__init__(f"No eligible adjuster available for specialization '{specialization}': {reason}")
        self.specialization = specialization


class DuplicatePaymentError(ClaimsServiceError):
    def __init__(self, settlement_id: str, existing_payment_id: str) -> None:
        super().__init__(
            f"Duplicate payment blocked: Settlement '{settlement_id}' already disbursed under payment '{existing_payment_id}'",
            entity_id=settlement_id,
        )
        self.settlement_id = settlement_id
        self.existing_payment_id = existing_payment_id


class SettlementLimitExceededError(ClaimsServiceError):
    def __init__(self, settlement_amount: str, coverage_limit: str, policy_id: str) -> None:
        super().__init__(
            f"Settlement blocked: amount (${settlement_amount}) exceeds coverage limit (${coverage_limit}) for policy '{policy_id}'",
            entity_id=policy_id,
        )
        self.settlement_amount = settlement_amount
        self.coverage_limit = coverage_limit


class DuplicateClaimSubmissionError(ClaimsServiceError):
    def __init__(self, existing_claim_id: str, reason: str) -> None:
        super().__init__(f"Duplicate claim submission rejected: identical to '{existing_claim_id}'. {reason}", entity_id=existing_claim_id)
