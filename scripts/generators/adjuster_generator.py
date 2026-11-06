"""Generator for realistic synthetic Adjuster records."""

from datetime import datetime, timedelta, timezone
import random
from faker import Faker

from app.core.id_generator import IdGenerator
from app.models.adjuster import Adjuster
from app.models.enums import AdjusterSpecialization, AdjusterStatus


def generate_adjusters(count: int, seed: int, base_year: int = 2026) -> list[Adjuster]:
    """Generate deterministically unique Adjuster records covering all specializations."""
    fake = Faker()
    Faker.seed(seed + 100)
    rng = random.Random(seed + 100)

    specializations = [
        AdjusterSpecialization.AUTO,
        AdjusterSpecialization.PROPERTY,
        AdjusterSpecialization.HEALTH,
        AdjusterSpecialization.TRAVEL,
        AdjusterSpecialization.COMMERCIAL,
        AdjusterSpecialization.GENERAL,
    ]

    adjusters: list[Adjuster] = []
    base_time = datetime(base_year - 2, 1, 1, 8, 0, 0, tzinfo=timezone.utc)

    for i in range(1, count + 1):
        adj_id = IdGenerator.adjuster_id(i, year=base_year)
        emp_id = f"EMP-{base_year}-{i:03d}"
        name = fake.name()
        email = f"adjuster_{i:03d}@insuranceclaims.com"
        phone = f"+1-800-{rng.randint(100, 999):03d}-{rng.randint(1000, 9999):04d}"
        
        # Round-robin assign specializations so each specialization is guaranteed represented
        spec = specializations[(i - 1) % len(specializations)]
        max_capacity = rng.choice([20, 25, 30])

        created_at = base_time + timedelta(days=i * 10)
        adjuster = Adjuster(
            id=adj_id,
            employee_id=emp_id,
            name=name,
            email=email,
            phone=phone,
            specialization=spec,
            active_claims_count=0,
            max_capacity=max_capacity,
            status=AdjusterStatus.ACTIVE,
            created_at=created_at,
            updated_at=created_at,
        )
        adjusters.append(adjuster)

    return adjusters

