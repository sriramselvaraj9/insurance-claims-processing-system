"""Generator for realistic synthetic Policy records."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import random

from app.core.id_generator import IdGenerator
from app.models.customer import Customer
from app.models.enums import PolicyStatus, PolicyType
from app.models.policy import Policy


def generate_policies(
    count: int,
    customers: list[Customer],
    seed: int,
    base_year: int = 2026,
) -> list[Policy]:
    """Generate deterministically unique Policy records mapped to customers."""
    rng = random.Random(seed)
    policies: list[Policy] = []

    policy_types = [
        PolicyType.AUTO,
        PolicyType.HOME,
        PolicyType.HEALTH,
        PolicyType.TRAVEL,
        PolicyType.COMMERCIAL,
    ]

    # Pre-allocate customer IDs so every customer has at least 1 policy
    customer_ids_pool: list[str] = [c.id for c in customers]
    allocated_customer_ids: list[str] = list(customer_ids_pool)

    # If count > len(customers), distribute remaining policies among customers
    while len(allocated_customer_ids) < count:
        allocated_customer_ids.append(rng.choice(customer_ids_pool))
    
    # Shuffle customer mapping deterministically
    rng.shuffle(allocated_customer_ids)
    allocated_customer_ids = allocated_customer_ids[:count]

    base_time = datetime(base_year - 1, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    for i in range(1, count + 1):
        cust_id = allocated_customer_ids[i - 1]
        
        # Policy type distribution
        ptype_roll = rng.random()
        if ptype_roll < 0.30:
            ptype = PolicyType.AUTO
        elif ptype_roll < 0.55:
            ptype = PolicyType.HOME
        elif ptype_roll < 0.75:
            ptype = PolicyType.HEALTH
        elif ptype_roll < 0.90:
            ptype = PolicyType.TRAVEL
        else:
            ptype = PolicyType.COMMERCIAL

        pol_id = IdGenerator.policy_id(ptype.value, i, year=base_year)

        # Policy dates: effective between 2025-01-01 and 2026-06-01
        eff_offset = rng.randint(0, 500)
        eff_date = date(base_year - 1, 1, 1) + timedelta(days=eff_offset)
        # Policy term: standard 1 year (365 days), travel can be 30-90 days
        if ptype == PolicyType.TRAVEL:
            term_days = rng.choice([30, 60, 90, 180])
        else:
            term_days = 365
        exp_date = eff_date + timedelta(days=term_days)

        # Status distribution: 85% ACTIVE, 6% CANCELLED, 5% EXPIRED, 3% SUSPENDED, 1% DRAFT
        status_roll = rng.random()
        cancellation_date: date | None = None
        if status_roll < 0.85:
            status = PolicyStatus.ACTIVE
        elif status_roll < 0.91:
            status = PolicyStatus.CANCELLED
            cancel_offset = rng.randint(5, max(6, term_days - 5))
            cancellation_date = eff_date + timedelta(days=cancel_offset)
        elif status_roll < 0.96:
            status = PolicyStatus.EXPIRED
        elif status_roll < 0.99:
            status = PolicyStatus.SUSPENDED
        else:
            status = PolicyStatus.DRAFT

        # Financials
        if ptype == PolicyType.AUTO:
            premium = Decimal(str(rng.randint(600, 2400)))
            deductible = Decimal(str(rng.choice([250, 500, 1000])))
        elif ptype == PolicyType.HOME:
            premium = Decimal(str(rng.randint(900, 3500)))
            deductible = Decimal(str(rng.choice([500, 1000, 2000, 2500])))
        elif ptype == PolicyType.HEALTH:
            premium = Decimal(str(rng.randint(2400, 8000)))
            deductible = Decimal(str(rng.choice([500, 1000, 1500, 3000])))
        elif ptype == PolicyType.TRAVEL:
            premium = Decimal(str(rng.randint(80, 500)))
            deductible = Decimal(str(rng.choice([100, 250, 500])))
        else:  # COMMERCIAL
            premium = Decimal(str(rng.randint(3000, 15000)))
            deductible = Decimal(str(rng.choice([1000, 2500, 5000])))

        created_at = base_time + timedelta(hours=i * 2, minutes=rng.randint(0, 59))
        policy = Policy(
            id=pol_id,
            customer_id=cust_id,
            policy_type=ptype,
            status=status,
            effective_date=eff_date,
            expiration_date=exp_date,
            cancellation_date=cancellation_date,
            total_premium=premium,
            deductible=deductible,
            created_at=created_at,
            updated_at=created_at,
        )
        policies.append(policy)

    return policies
