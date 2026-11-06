"""Generator for deterministic synthetic Settlement and SettlementPayment records."""

from datetime import timedelta
from decimal import Decimal
import random

from app.core.id_generator import IdGenerator
from app.models.assessment import Assessment
from app.models.claim import Claim
from app.models.coverage import Coverage
from app.models.enums import (
    ClaimStatus,
    PaymentMethod,
    PaymentStatus,
    SettlementStatus,
)
from app.models.policy import Policy
from app.models.settlement import Settlement
from app.models.settlement_payment import SettlementPayment
from app.rules.financial_rules import compute_settlement
from scripts.generators.anomaly_injector import AnomalyInjectionPlan


def generate_settlements_and_payments(
    claims: list[Claim],
    policies: list[Policy],
    coverages: list[Coverage],
    assessments: list[Assessment],
    anomaly_plan: AnomalyInjectionPlan,
    seed: int,
) -> tuple[list[Settlement], list[SettlementPayment]]:
    """Generate Settlements and Payments, implementing Scenario 4 (Exceeds limit) and Scenario 6 (Paid twice)."""
    rng = random.Random(seed + 800)
    settlements: list[Settlement] = []
    payments: list[SettlementPayment] = []

    policies_by_id = {p.id: p for p in policies}
    coverages_by_policy: dict[str, list[Coverage]] = {}
    for cov in coverages:
        coverages_by_policy.setdefault(cov.policy_id, []).append(cov)

    assessments_by_claim = {asm.claim_id: asm for asm in assessments}

    for claim in claims:
        policy = policies_by_id[claim.policy_id]
        pol_coverages = coverages_by_policy.get(policy.id, [])
        primary_cov = pol_coverages[0] if pol_coverages else None
        cov_limit = primary_cov.coverage_limit if primary_cov else Decimal("50000.00")
        copay_pct = primary_cov.copay_percentage if primary_cov else Decimal("0.00")

        assessment = assessments_by_claim.get(claim.id)
        is_eligible = assessment.is_eligible if assessment else False

        # Scenario 4: Settlement exceeding coverage limit
        if claim.id in anomaly_plan.exceeds_limit_claim_ids:
            excessive_net = (cov_limit * Decimal("1.50")).quantize(Decimal("0.01"))
            settle_id = IdGenerator.settlement_id(claim.id, 1)
            settled_at = claim.reported_date + timedelta(days=2)
            settlement = Settlement(
                id=settle_id,
                claim_id=claim.id,
                recommended_amount=excessive_net,
                approved_amount=None,
                deductible_applied=Decimal("0.00"),
                copay_applied=Decimal("0.00"),
                net_settlement_amount=excessive_net,
                status=SettlementStatus.REJECTED,
                settled_at=settled_at,
                settled_by="SUPERVISOR_AUDIT",
                payment_reference=None,
                created_at=settled_at,
                updated_at=settled_at,
            )
            settlements.append(settlement)
            claim.status = ClaimStatus.REJECTED
            continue

        # If eligible, calculate legitimate settlement
        if is_eligible:
            breakdown = compute_settlement(
                claimed_amount=claim.claimed_amount,
                coverage_limit=cov_limit,
                deductible=policy.deductible,
                copay_percentage=copay_pct,
            )

            settle_id = IdGenerator.settlement_id(claim.id, 1)
            settled_at = claim.reported_date + timedelta(days=rng.randint(2, 6))

            if breakdown.net_settlement_amount > Decimal("0.00"):
                pay_ref_primary = f"PAYREF-{settle_id}-01"
                settlement = Settlement(
                    id=settle_id,
                    claim_id=claim.id,
                    recommended_amount=breakdown.allowable_loss,
                    approved_amount=breakdown.net_settlement_amount,
                    deductible_applied=breakdown.deductible_applied,
                    copay_applied=breakdown.copay_applied,
                    net_settlement_amount=breakdown.net_settlement_amount,
                    status=SettlementStatus.DISBURSED,
                    settled_at=settled_at,
                    settled_by="SETTLEMENT_OFFICER_V1",
                    payment_reference=pay_ref_primary,
                    created_at=settled_at,
                    updated_at=settled_at,
                )
                settlements.append(settlement)
                claim.status = ClaimStatus.SETTLED

                # Primary disbursement payment
                pay_id = IdGenerator.settlement_payment_id(settle_id, 1)
                payment_date = settled_at + timedelta(hours=rng.randint(4, 24))
                pay = SettlementPayment(
                    id=pay_id,
                    settlement_id=settle_id,
                    payment_amount=breakdown.net_settlement_amount,
                    payment_method=PaymentMethod.ACH,
                    payment_reference=pay_ref_primary,
                    payment_date=payment_date,
                    status=PaymentStatus.COMPLETED,
                )
                payments.append(pay)

                # Scenario 6: Claim paid twice (Double payment anomaly)
                if claim.id in anomaly_plan.double_payment_claim_ids:
                    dup_pay_id = IdGenerator.settlement_payment_id(settle_id, 2)
                    dup_pay_ref = f"PAYREF-{settle_id}-02"
                    dup_payment_date = payment_date + timedelta(hours=rng.randint(12, 36))
                    dup_pay = SettlementPayment(
                        id=dup_pay_id,
                        settlement_id=settle_id,
                        payment_amount=breakdown.net_settlement_amount,
                        payment_method=PaymentMethod.ACH,
                        payment_reference=dup_pay_ref,
                        payment_date=dup_payment_date,
                        status=PaymentStatus.COMPLETED,
                    )
                    payments.append(dup_pay)
                    claim.status = ClaimStatus.FLAGGED

    return settlements, payments
