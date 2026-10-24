"""Database seeding script for RouteRescue AI demonstration datasets.

Populates SQLite with:
- 14 transit hub locations across Delhi, Jaipur, Chandigarh, Agra, Gurugram, Noida, Mathura, Ambala.
- 32 train services (including express, Shatabdi, Vande Bharat, Rajdhani, overnight sleepers)
- 32 intercity bus services (Zingbus, IntrCity SmartBus, NueGo Electric, RSRTC Volvo)
- 21 cab and road connections (Uber Intercity, BluSmart, Savaari, intra-city transit connectors)
- 10 simulated disruption scenarios
- 1 sample disrupted passenger journey
"""

from datetime import datetime, timedelta
from typing import Optional

from config.settings import IST
from data.database import DatabaseManager
from data.synthetic_network import (
    DEMO_LOCATIONS,
    get_simulated_disruptions,
    get_synthetic_bus_services,
    get_synthetic_cab_services,
    get_synthetic_train_services,
)
from schemas.common import BookingStatus
from schemas.travel import UserJourney


def seed_database(db: Optional[DatabaseManager] = None) -> DatabaseManager:
    """Initializes tables and seeds all synthetic demonstration datasets."""
    if db is None:
        db = DatabaseManager()

    db.init_db()

    # 1. Seed Locations
    for loc in DEMO_LOCATIONS.values():
        db.save_location(loc)

    # 2. Seed Transport Services (Trains, Buses, Cabs)
    today = datetime.now(IST).replace(hour=0, minute=0, second=0, microsecond=0)
    trains = get_synthetic_train_services(base_date=today)
    buses = get_synthetic_bus_services(base_date=today)
    cabs = get_synthetic_cab_services(base_date=today)

    all_services = trains + buses + cabs
    db.save_services(all_services)

    # 3. Seed Disruption Scenarios (10 scenarios)
    disruptions = get_simulated_disruptions(base_time=datetime.now(IST))
    for d in disruptions:
        db.save_disruption(d, is_active=True)

    # 4. Seed A Demonstration Stranded Passenger Journey
    # Rohan Sharma booked on Train 12015 (Ajmer Shatabdi NDLS -> JP) which is cancelled
    impacted_train = next((t for t in trains if t.service_id == "TRN-12015"), trains[0])
    sample_journey = UserJourney(
        journey_id="JRN-ROHAN-9901",
        passenger_name="Rohan Sharma",
        passenger_email="rohan.sharma@example.com",
        booked_service=impacted_train,
        booking_status=BookingStatus.CANCELLED_BY_DISRUPTION,
        booking_reference="PNR-8429104821",
        booked_fare_inr=impacted_train.fare_inr,
        created_at=datetime.now(IST) - timedelta(days=2),
    )
    db.save_user_journey(sample_journey)

    db.log_monitoring_event(
        event_type="DATABASE_SEEDED",
        details={
            "locations_count": len(DEMO_LOCATIONS),
            "trains_count": len(trains),
            "buses_count": len(buses),
            "cabs_count": len(cabs),
            "total_services": len(all_services),
            "disruptions_count": len(disruptions),
        },
    )

    return db


if __name__ == "__main__":
    db = DatabaseManager()
    seed_database(db)
    print("Database successfully seeded with RouteRescue AI demonstration network.")
    print(f"Locations: {len(db.list_all_locations())}")
    print(f"Services: {len(db.query_services())}")
    print(f"Active Disruptions: {len(db.get_active_disruptions())}")
