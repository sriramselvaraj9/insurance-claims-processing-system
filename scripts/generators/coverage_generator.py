"""Generator for realistic synthetic Coverage records mapped to policies."""

from decimal import Decimal
import random

from app.core.id_generator import IdGenerator
from app.models.coverage import Coverage
from app.models.enums import CoverageType, PolicyType
from app.models.policy import Policy


def generate_coverages(policies: list[Policy], seed: int) -> list[Coverage]:
    """Generate deterministically unique Coverage records for each policy."""
    rng = random.Random(seed)
    coverages: list[Coverage] = []

    for pol in policies:
        cov_specs: list[tuple[CoverageType, Decimal, Decimal, Decimal, list[str] | None]] = []

        if pol.policy_type == PolicyType.AUTO:
            cov_specs.append((
                CoverageType.COLLISION,
                Decimal(str(rng.choice([30000, 50000, 75000]))),
                pol.deductible,
                Decimal("0.00"),
                None,
            ))
            cov_specs.append((
                CoverageType.COMPREHENSIVE,
                Decimal(str(rng.choice([25000, 40000, 60000]))),
                Decimal(str(rng.choice([250, 500]))),
                Decimal("0.00"),
                None,
            ))
            cov_specs.append((
                CoverageType.LIABILITY,
                Decimal(str(rng.choice([100000, 250000, 500000]))),
                Decimal("0.00"),
                Decimal("0.00"),
                None,
            ))
        elif pol.policy_type == PolicyType.HOME:
            cov_specs.append((
                CoverageType.DWELLING,
                Decimal(str(rng.choice([250000, 400000, 600000]))),
                pol.deductible,
                Decimal("0.00"),
                ["EARTHQUAKE", "FLOOD"],
            ))
            cov_specs.append((
                CoverageType.PERSONAL_PROPERTY,
                Decimal(str(rng.choice([75000, 150000, 250000]))),
                Decimal("500.00"),
                Decimal("0.00"),
                ["FLOOD"],
            ))
            cov_specs.append((
                CoverageType.LIABILITY,
                Decimal(str(rng.choice([100000, 300000, 500000]))),
                Decimal("0.00"),
                Decimal("0.00"),
                None,
            ))
        elif pol.policy_type == PolicyType.HEALTH:
            cov_specs.append((
                CoverageType.MEDICAL_PAYMENTS,
                Decimal(str(rng.choice([50000, 100000, 250000]))),
                pol.deductible,
                Decimal(str(rng.choice([10, 15, 20]))),
                None,
            ))
            cov_specs.append((
                CoverageType.BODILY_INJURY,
                Decimal(str(rng.choice([50000, 100000]))),
                pol.deductible,
                Decimal("10.00"),
                None,
            ))
        elif pol.policy_type == PolicyType.TRAVEL:
            cov_specs.append((
                CoverageType.TRIP_INTERRUPTION,
                Decimal(str(rng.choice([5000, 10000, 20000]))),
                pol.deductible,
                Decimal("0.00"),
                ["WAR_ZONE", "ILLEGAL_ACTIVITY"],
            ))
            cov_specs.append((
                CoverageType.BAGGAGE_LOSS,
                Decimal(str(rng.choice([1500, 3000, 5000]))),
                Decimal("100.00"),
                Decimal("0.00"),
                None,
            ))
        else:  # COMMERCIAL
            cov_specs.append((
                CoverageType.LIABILITY,
                Decimal(str(rng.choice([500000, 1000000, 2000000]))),
                pol.deductible,
                Decimal("0.00"),
                None,
            ))
            cov_specs.append((
                CoverageType.PERSONAL_PROPERTY,
                Decimal(str(rng.choice([150000, 300000, 500000]))),
                pol.deductible,
                Decimal("0.00"),
                None,
            ))

        for seq, (cov_type, limit, ded, copay, exclusions) in enumerate(cov_specs, start=1):
            cov_id = IdGenerator.coverage_id(pol.id, seq)
            coverage = Coverage(
                id=cov_id,
                policy_id=pol.id,
                coverage_type=cov_type,
                coverage_limit=limit,
                deductible=ded,
                copay_percentage=copay,
                exclusions=exclusions,
                effective_date=pol.effective_date,
                expiration_date=pol.expiration_date,
                is_active=True,
                created_at=pol.created_at,
                updated_at=pol.created_at,
            )
            coverages.append(coverage)

    return coverages

