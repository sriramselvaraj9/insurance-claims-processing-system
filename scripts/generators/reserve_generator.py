"""Generator for deterministic synthetic Reserve records."""

from datetime import timedelta
from decimal import Decimal
import random

from app.core.id_generator import IdGenerator
from app.models.claim import Claim
from app.models.coverage import Coverage
from app.models.enums import ReserveCalculationMethod
from app.models.policy import Policy
from app.models.reserve import Reserve
from app.rules.financial_rules import compute_total_reserve


def generate_reserves(
    claims: list[Claim],
    policies: list[Policy],
    coverages: list[Coverage],
    seed: int,
) -> list[Reserve]:
    """Generate deterministically calculated preliminary Reserve records for claims."""
    rng = random.Random(seed + 700)
    reserves: list[Reserve] = []

    policies_by_id = {p.id: p for p in policies}
    coverages_by_policy: dict[str, list[Coverage]] = {}
    for cov in coverages:
        coverages_by_policy.setdefault(cov.policy_id, []).append(cov)

    for claim in claims:
        policy = policies_by_id[claim.policy_id]
        pol_coverages = coverages_by_policy.get(policy.id, [])
        primary_cov = pol_coverages[0] if pol_coverages else None
        cov_limit = primary_cov.coverage_limit if primary_cov else Decimal("50000.00")

        breakdown = compute_total_reserve(
            estimated_loss=claim.estimated_loss,
            coverage_limit=cov_limit,
            deductible=policy.deductible,
            expense_ratio=Decimal("0.1200"),
        )

        res_id = IdGenerator.reserve_id(claim.id, 1)
        calc_at = claim.reported_date + timedelta(hours=rng.randint(3, 10))

        reserve = Reserve(
            id=res_id,
            claim_id=claim.id,
            estimated_indemnity_reserve=breakdown.indemnity_reserve,
            estimated_expense_reserve=breakdown.expense_reserve,
            total_reserve=breakdown.total_reserve,
            expense_ratio=Decimal("0.1200"),
            calculation_method=ReserveCalculationMethod.FORMULAIC_STANDARD,
            calculated_at=calc_at,
            calculated_by="SYSTEM_RULE_RESERVE",
            created_at=calc_at,
        )
        reserves.append(reserve)

    return reserves

