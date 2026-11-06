"""Domain services layer."""

from app.services.adjuster_service import AdjusterService
from app.services.claim_intake_service import ClaimIntakeService
from app.services.claims_processing_service import (
    ClaimsProcessingResult,
    ClaimsProcessingService,
)
from app.services.coverage_service import CoverageService, CoverageValidationResult
from app.services.document_service import DocumentService, DocumentVerificationResult
from app.services.duplicate_detection_service import (
    DuplicateDetectionResult,
    DuplicateDetectionService,
)
from app.services.eligibility_service import (
    EligibilityService,
    EligibilityServiceResult,
)
from app.services.exceptions import (
    ClaimNotFoundError,
    CustomerNotFoundError,
    CustomerPolicyMismatchError,
    DuplicateClaimSubmissionError,
    DuplicatePaymentError,
    IncidentNotFoundError,
    InvalidFinancialValueError,
    MissingCoverageError,
    NoEligibleAdjusterError,
    PolicyNotFoundError,
    SettlementLimitExceededError,
)
from app.services.fraud_service import FraudService
from app.services.policy_validation_service import (
    PolicyValidationResult,
    PolicyValidationService,
)
from app.services.reserve_service import ReserveService
from app.services.settlement_service import SettlementService

__all__ = [
    "ClaimIntakeService",
    "PolicyValidationService",
    "PolicyValidationResult",
    "CoverageService",
    "CoverageValidationResult",
    "DocumentService",
    "DocumentVerificationResult",
    "DuplicateDetectionService",
    "DuplicateDetectionResult",
    "FraudService",
    "EligibilityService",
    "EligibilityServiceResult",
    "AdjusterService",
    "ReserveService",
    "SettlementService",
    "ClaimsProcessingService",
    "ClaimsProcessingResult",
    "ClaimNotFoundError",
    "PolicyNotFoundError",
    "CustomerNotFoundError",
    "IncidentNotFoundError",
    "CustomerPolicyMismatchError",
    "MissingCoverageError",
    "InvalidFinancialValueError",
    "NoEligibleAdjusterError",
    "DuplicatePaymentError",
    "SettlementLimitExceededError",
    "DuplicateClaimSubmissionError",
]
