"""Generator for realistic synthetic ClaimItem records."""

from decimal import Decimal
import random

from app.core.id_generator import IdGenerator
from app.models.claim import Claim
from app.models.claim_item import ClaimItem
from app.models.coverage import Coverage


def generate_claim_items(
    claims: list[Claim],
    coverages: list[Coverage],
    seed: int,
) -> list[ClaimItem]:
    """Generate deterministically unique ClaimItem records whose sum strictly equals claim.claimed_amount."""
    rng = random.Random(seed + 400)
    claim_items: list[ClaimItem] = []

    # Index coverages by policy_id
    coverages_by_policy: dict[str, list[Coverage]] = {}
    for cov in coverages:
        coverages_by_policy.setdefault(cov.policy_id, []).append(cov)

    item_descriptions = {
        "COLLISION": [
            "OEM Front Bumper Assembly Replacement",
            "Left Fender Painting and Alignment",
            "Headlight Cluster Replacement",
            "Body Shop Structural Labor",
        ],
        "PROPERTY_DAMAGE": [
            "Drywall Demolition and Replacement",
            "Oak Hardwood Floor Sanding & Refinishing",
            "Plumbing Pipe Section Replacement",
            "Industrial Dehumidifier Rental & Drying Labor",
        ],
        "MEDICAL": [
            "Emergency Department Physician Evaluation",
            "Diagnostic MRI Spinal Imaging",
            "Physical Therapy Rehabilitation Sessions",
            "Prescription Anti-Inflammatory Medication",
        ],
        "TRAVEL_LOSS": [
            "Non-Refundable Hotel Reservation Cancellation",
            "Emergency Return Flight Rebooking Fee",
            "Replacement Clothing and Toiletries",
            "Luggage Carrier Fee",
        ],
        "LIABILITY": [
            "Third-Party Outpatient Orthopedic Treatment",
            "Independent Medical Examination Fee",
            "Legal Defense Retainer and Consultation",
            "Property Repair Settlement for Claimant",
        ],
    }

    for claim in claims:
        available_covs = coverages_by_policy.get(claim.policy_id, [])
        primary_cov_id = available_covs[0].id if available_covs else None

        desc_list = item_descriptions.get(
            claim.claim_type.value,
            ["General Damage Assessment", "Remediation Labor", "Material Surcharge"],
        )

        # 1 to 3 items per claim
        num_items = rng.choice([1, 2, 3])
        claimed = claim.claimed_amount

        if num_items == 1:
            item_id = IdGenerator.claim_item_id(claim.id, 1)
            item = ClaimItem(
                id=item_id,
                claim_id=claim.id,
                coverage_id=primary_cov_id,
                item_description=desc_list[0],
                quantity=1,
                unit_amount=claimed,
                total_amount=claimed,
                created_at=claim.created_at,
            )
            claim_items.append(item)
        elif num_items == 2:
            # Split roughly 60% / 40%
            part1 = (claimed * Decimal("0.60")).quantize(Decimal("0.01"))
            part2 = claimed - part1

            item1 = ClaimItem(
                id=IdGenerator.claim_item_id(claim.id, 1),
                claim_id=claim.id,
                coverage_id=primary_cov_id,
                item_description=desc_list[0],
                quantity=1,
                unit_amount=part1,
                total_amount=part1,
                created_at=claim.created_at,
            )
            item2 = ClaimItem(
                id=IdGenerator.claim_item_id(claim.id, 2),
                claim_id=claim.id,
                coverage_id=primary_cov_id,
                item_description=desc_list[1 % len(desc_list)],
                quantity=1,
                unit_amount=part2,
                total_amount=part2,
                created_at=claim.created_at,
            )
            claim_items.extend([item1, item2])
        else:  # num_items == 3
            # Split roughly 40% / 35% / 25%
            part1 = (claimed * Decimal("0.40")).quantize(Decimal("0.01"))
            part2 = (claimed * Decimal("0.35")).quantize(Decimal("0.01"))
            part3 = claimed - part1 - part2

            items_parts = [(part1, desc_list[0]), (part2, desc_list[1 % len(desc_list)]), (part3, desc_list[2 % len(desc_list)])]
            for seq, (part_amt, desc) in enumerate(items_parts, start=1):
                item = ClaimItem(
                    id=IdGenerator.claim_item_id(claim.id, seq),
                    claim_id=claim.id,
                    coverage_id=primary_cov_id,
                    item_description=desc,
                    quantity=1,
                    unit_amount=part_amt,
                    total_amount=part_amt,
                    created_at=claim.created_at,
                )
                claim_items.append(item)

    return claim_items
