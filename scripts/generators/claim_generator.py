"""Generator for realistic synthetic Claim records."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import random

from app.core.id_generator import IdGenerator
from app.models.claim import Claim
from app.models.enums import ClaimStatus, ClaimType, PolicyType
from app.models.incident import Incident
from app.models.policy import Policy


# Map each of the 5 required ClaimTypes to its primary PolicyType
CLAIM_TO_POLICY_TYPE = {
    ClaimType.COLLISION: PolicyType.AUTO,
    ClaimType.PROPERTY_DAMAGE: PolicyType.HOME,
    ClaimType.MEDICAL: PolicyType.HEALTH,
    ClaimType.TRAVEL_LOSS: PolicyType.TRAVEL,
    ClaimType.LIABILITY: PolicyType.COMMERCIAL,
}

CLAIM_AMOUNTS_BY_TYPE = {
    ClaimType.COLLISION: (800, 15000),
    ClaimType.PROPERTY_DAMAGE: (1500, 35000),
    ClaimType.MEDICAL: (500, 25000),
    ClaimType.TRAVEL_LOSS: (300, 4500),
    ClaimType.LIABILITY: (5000, 85000),
}


def generate_claims(
    count: int,
    policies: list[Policy],
    incidents: list[Incident],
    seed: int,
    base_year: int = 2026,
) -> list[Claim]:
    """Generate deterministically unique Claim records mapped to matching policies and customers.

    Guarantees:
    - 5 required claim types are evenly balanced.
    - claim.customer_id == policy.customer_id.
    - claim.policy_id references a policy matching the required policy_type.
    """
    rng = random.Random(seed + 300)
    claims: list[Claim] = []

    # Index policies by PolicyType
    policies_by_type: dict[PolicyType, list[Policy]] = {pt: [] for pt in PolicyType}
    for pol in policies:
        policies_by_type[pol.policy_type].append(pol)

    # 5 claim types to rotate
    claim_types_cycle = [
        ClaimType.COLLISION,
        ClaimType.PROPERTY_DAMAGE,
        ClaimType.MEDICAL,
        ClaimType.TRAVEL_LOSS,
        ClaimType.LIABILITY,
    ]

    for i in range(1, count + 1):
        claim_id = IdGenerator.claim_id(i, year=base_year)
        claim_type = claim_types_cycle[(i - 1) % len(claim_types_cycle)]
        required_policy_type = CLAIM_TO_POLICY_TYPE[claim_type]

        matching_policies = policies_by_type[required_policy_type]
        if not matching_policies:
            # Fallback to any policy if specific type not found
            selected_policy = policies[(i - 1) % len(policies)]
        else:
            selected_policy = matching_policies[(i - 1) % len(matching_policies)]

        # Relational guarantee: claim customer matches policy customer
        customer_id = selected_policy.customer_id
        policy_id = selected_policy.id

        # Incident mapping (re-use incident pool)
        incident = incidents[(i - 1) % len(incidents)]
        incident_id = incident.id

        # Align incident occurrence date within policy effective window for baseline
        # (Anomalous dates will be injected separately by AnomalyInjector)
        incident_date = incident.occurrence_date

        # Reported date: standard 1 to 14 days after incident
        report_delay = timedelta(days=rng.randint(1, 14), hours=rng.randint(1, 12))
        reported_date = incident_date + report_delay

        # Monetary amounts
        min_amt, max_amt = CLAIM_AMOUNTS_BY_TYPE[claim_type]
        claimed_num = rng.randint(min_amt, max_amt)
        # Quantized with realistic cents
        cents = rng.choice([Decimal("0.00"), Decimal("0.50"), Decimal("0.75"), Decimal("0.25")])
        claimed_amount = Decimal(str(claimed_num)) + cents
        # Estimated loss typically close to claimed amount (e.g. 95% to 105%)
        ratio = Decimal(str(rng.randint(95, 105))) / Decimal("100.00")
        estimated_loss = (claimed_amount * ratio).quantize(Decimal("0.01"))

        descriptions = {
            ClaimType.COLLISION: f"Front passenger-side bumper and fender replacement claim on policy {policy_id}.",
            ClaimType.PROPERTY_DAMAGE: f"Drywall water damage restoration and hardwood flooring claim on policy {policy_id}.",
            ClaimType.MEDICAL: f"Emergency room consultation and radiological evaluation fees on policy {policy_id}.",
            ClaimType.TRAVEL_LOSS: f"Flight cancellation accommodation expenses and delayed baggage claim on policy {policy_id}.",
            ClaimType.LIABILITY: f"Third-party premises bodily injury and legal defense claim on policy {policy_id}.",
        }
        description = descriptions.get(claim_type, f"Standard insurance claim under policy {policy_id}.")

        claim = Claim(
            id=claim_id,
            customer_id=customer_id,
            policy_id=policy_id,
            incident_id=incident_id,
            claim_type=claim_type,
            status=ClaimStatus.SUBMITTED,
            reported_date=reported_date,
            claimed_amount=claimed_amount,
            estimated_loss=estimated_loss,
            description=description,
            assigned_adjuster_id=None,
            created_at=reported_date,
            updated_at=reported_date,
        )
        claims.append(claim)

    return claims
