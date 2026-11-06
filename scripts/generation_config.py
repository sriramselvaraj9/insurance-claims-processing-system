"""Configuration and presets for synthetic data generation and ground truth injection."""

from dataclasses import dataclass
from typing import Literal

ScaleType = Literal["starter", "full"]


@dataclass(frozen=True)
class GenerationConfig:
    scale: ScaleType
    seed: int
    num_customers: int
    num_policies: int
    num_adjusters: int
    num_claims: int
    
    # Anomaly counts (for full scale: 1000 claims total)
    neg_01_pre_effective_count: int
    neg_01_post_cancel_count: int
    neg_02_uncovered_peril_count: int
    neg_03_untimely_filing_count: int
    neg_04_missing_document_count: int
    neg_05_excessive_amount_count: int
    neg_05_exceeds_coverage_limit_count: int
    neg_06_duplicate_claim_count: int
    neg_06_duplicate_incident_count: int
    neg_06_double_payment_count: int


def get_generation_config(scale: ScaleType = "full", seed: int = 20261022) -> GenerationConfig:
    """Retrieve calibrated generation configuration by scale."""
    if scale == "starter":
        return GenerationConfig(
            scale="starter",
            seed=seed,
            num_customers=35,
            num_policies=50,
            num_adjusters=8,
            num_claims=25,
            neg_01_pre_effective_count=1,
            neg_01_post_cancel_count=1,
            neg_02_uncovered_peril_count=1,
            neg_03_untimely_filing_count=1,
            neg_04_missing_document_count=2,
            neg_05_excessive_amount_count=1,
            neg_05_exceeds_coverage_limit_count=1,
            neg_06_duplicate_claim_count=1,
            neg_06_duplicate_incident_count=1,
            neg_06_double_payment_count=1,
        )
    elif scale == "full":
        return GenerationConfig(
            scale="full",
            seed=seed,
            num_customers=1200,
            num_policies=2000,  # Assessment requirement: exactly 2,000 policies
            num_adjusters=25,
            num_claims=1000,    # Assessment requirement: exactly 1,000 claims
            neg_01_pre_effective_count=20,
            neg_01_post_cancel_count=15,
            neg_02_uncovered_peril_count=15,
            neg_03_untimely_filing_count=15,
            neg_04_missing_document_count=25,
            neg_05_excessive_amount_count=15,
            neg_05_exceeds_coverage_limit_count=15,
            neg_06_duplicate_claim_count=15,
            neg_06_duplicate_incident_count=15,
            neg_06_double_payment_count=15,
        )
    else:
        raise ValueError(f"Unknown scale '{scale}'. Choose 'starter' or 'full'.")

