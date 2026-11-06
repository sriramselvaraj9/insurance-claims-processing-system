"""Generator for realistic synthetic Customer records."""

from datetime import date, datetime, timedelta, timezone
import random
from faker import Faker

from app.core.id_generator import IdGenerator
from app.models.customer import Customer
from app.models.enums import KYCStatus, RiskProfile


def generate_customers(count: int, seed: int, base_year: int = 2026) -> list[Customer]:
    """Generate deterministically unique Customer records."""
    fake = Faker()
    Faker.seed(seed)
    rng = random.Random(seed)

    customers: list[Customer] = []
    base_time = datetime(base_year, 1, 1, 9, 0, 0, tzinfo=timezone.utc)

    for i in range(1, count + 1):
        cust_id = IdGenerator.customer_id(i, year=base_year)
        first_name = fake.first_name()
        last_name = fake.last_name()
        email = f"customer_{i:06d}@example.com"
        phone = f"+1-{rng.randint(200, 999):03d}-{rng.randint(100, 999):03d}-{rng.randint(1000, 9999):04d}"
        
        # Age between 21 and 75
        age_days = rng.randint(21 * 365, 75 * 365)
        dob = date(base_year, 1, 1) - timedelta(days=age_days)

        # KYC distribution: 88% VERIFIED, 7% PENDING, 3% FLAGGED, 2% REJECTED
        kyc_roll = rng.random()
        if kyc_roll < 0.88:
            kyc_status = KYCStatus.VERIFIED
        elif kyc_roll < 0.95:
            kyc_status = KYCStatus.PENDING
        elif kyc_roll < 0.98:
            kyc_status = KYCStatus.FLAGGED
        else:
            kyc_status = KYCStatus.REJECTED

        # Risk profile: 60% LOW, 30% MEDIUM, 10% HIGH
        risk_roll = rng.random()
        if risk_roll < 0.60:
            risk_profile = RiskProfile.LOW
        elif risk_roll < 0.90:
            risk_profile = RiskProfile.MEDIUM
        else:
            risk_profile = RiskProfile.HIGH

        created_at = base_time + timedelta(hours=i * 2, minutes=rng.randint(0, 59))
        customer = Customer(
            id=cust_id,
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            date_of_birth=dob,
            kyc_status=kyc_status,
            risk_profile=risk_profile,
            created_at=created_at,
            updated_at=created_at,
        )
        customers.append(customer)

    return customers

