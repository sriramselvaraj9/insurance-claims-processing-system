"""Generator for realistic synthetic Incident records."""

from datetime import datetime, timedelta, timezone
import random
from faker import Faker

from app.core.id_generator import IdGenerator
from app.models.enums import IncidentType
from app.models.incident import Incident


def generate_incidents(
    count: int,
    seed: int,
    base_year: int = 2026,
) -> list[Incident]:
    """Generate deterministically unique Incident records."""
    fake = Faker()
    Faker.seed(seed + 200)
    rng = random.Random(seed + 200)

    incident_types = [
        IncidentType.VEHICLE_COLLISION,
        IncidentType.WATER_LEAK,
        IncidentType.FIRE,
        IncidentType.THEFT,
        IncidentType.BODILY_INJURY,
        IncidentType.SLIP_AND_FALL,
        IncidentType.TRAVEL_DISRUPTION,
        IncidentType.HAIL_STORM,
    ]

    cities = [
        ("Chicago", "IL", "60601"),
        ("Springfield", "IL", "62701"),
        ("Peoria", "IL", "61602"),
        ("Dallas", "TX", "75201"),
        ("Austin", "TX", "78701"),
        ("Denver", "CO", "80202"),
        ("Seattle", "WA", "98101"),
        ("Miami", "FL", "33101"),
    ]

    incidents: list[Incident] = []
    base_occurrence = datetime(base_year, 1, 15, 10, 0, 0, tzinfo=timezone.utc)

    for i in range(1, count + 1):
        inc_id = IdGenerator.incident_id(i, year=base_year)
        itype = incident_types[(i - 1) % len(incident_types)]
        city, state, zipcode = rng.choice(cities)
        street = fake.street_address()

        # Spread occurrence dates across 2025 and 2026
        day_offset = rng.randint(0, 360)
        occ_date = base_occurrence + timedelta(days=day_offset, hours=rng.randint(0, 23))

        police_filed = itype in (IncidentType.VEHICLE_COLLISION, IncidentType.THEFT, IncidentType.FIRE) or rng.random() < 0.3
        police_number = f"PD-{state}-{base_year}-{rng.randint(10000, 99999)}" if police_filed else None

        desc_templates = {
            IncidentType.VEHICLE_COLLISION: "Multi-vehicle rear-end collision at intersection under slick road conditions.",
            IncidentType.WATER_LEAK: "Sudden pipe burst causing water pooling across main hallway floor.",
            IncidentType.FIRE: "Kitchen electrical short-circuit resulting in localized cabinet fire.",
            IncidentType.THEFT: "Unattended personal belongings and electronics removed from vehicle.",
            IncidentType.BODILY_INJURY: "Pedestrian slip and impact on private walkway resulting in shoulder sprain.",
            IncidentType.SLIP_AND_FALL: "Customer slip on wet lobby tile during maintenance hours.",
            IncidentType.TRAVEL_DISRUPTION: "Airline flight cancellation and lost connecting luggage during adverse weather.",
            IncidentType.HAIL_STORM: "Severe localized hailstorm causing roof shingle cracking and vehicle denting.",
            IncidentType.OTHER: "Accidental property impact resulting in surface structural damage.",
        }
        description = desc_templates.get(itype, "Standard insured loss event.")

        created_at = occ_date + timedelta(hours=rng.randint(1, 24))
        incident = Incident(
            id=inc_id,
            incident_type=itype,
            occurrence_date=occ_date,
            description=description,
            location_street=street,
            location_city=city,
            location_state=state,
            location_zip=zipcode,
            police_report_filed=police_filed,
            police_report_number=police_number,
            created_at=created_at,
            updated_at=created_at,
        )
        incidents.append(incident)

    return incidents
