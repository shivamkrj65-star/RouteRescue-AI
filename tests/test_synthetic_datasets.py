"""Unit tests for synthetic dataset integrity, quantities, and demonstration requirements."""

from datetime import datetime, timezone
import pytest

from config.settings import IST
from data.database import DatabaseManager
from data.synthetic_network import (
    DEMO_LOCATIONS,
    get_simulated_disruptions,
    get_synthetic_bus_services,
    get_synthetic_cab_services,
    get_synthetic_train_services,
)
from schemas.common import TransportMode


def test_required_dataset_counts():
    """Verify that dataset counts satisfy the project specification."""
    trains = get_synthetic_train_services()
    buses = get_synthetic_bus_services()
    cabs = get_synthetic_cab_services()
    disruptions = get_simulated_disruptions()

    assert len(trains) >= 30, f"Expected >= 30 train services, got {len(trains)}"
    assert len(buses) >= 30, f"Expected >= 30 bus services, got {len(buses)}"
    assert len(cabs) >= 20, f"Expected >= 20 cab/road connections, got {len(cabs)}"
    assert len(disruptions) >= 10, f"Expected >= 10 disruption scenarios, got {len(disruptions)}"


def test_geographic_corridor_coverage():
    """Verify that demonstration network covers Delhi, Jaipur, Chandigarh, Agra, and nearby hubs."""
    covered_cities = {loc.city for loc in DEMO_LOCATIONS.values()}
    required_cities = {"Delhi", "Jaipur", "Chandigarh", "Agra"}

    for city in required_cities:
        assert city in covered_cities, f"Required demonstration city '{city}' missing from network"

    # Verify nearby hubs
    assert "Gurugram" in covered_cities or "Noida" in covered_cities or "Mathura" in covered_cities


def test_mandatory_journey_fields_and_integrity():
    """
    Verify every journey includes:
    - Origin and destination
    - Departure and arrival timestamps
    - Estimated fare
    - Transport mode
    - Seat availability status
    - Provider identifier
    - Booking URL
    """
    all_services = get_synthetic_train_services() + get_synthetic_bus_services() + get_synthetic_cab_services()

    for svc in all_services:
        # Origin and destination
        assert svc.origin is not None and svc.origin.code in DEMO_LOCATIONS
        assert svc.destination is not None and svc.destination.code in DEMO_LOCATIONS
        assert svc.origin.code != svc.destination.code

        # Timestamps
        assert svc.departure_time is not None
        assert svc.arrival_time is not None
        assert svc.arrival_time > svc.departure_time, f"Arrival must follow departure in service {svc.service_id}"

        # Estimated fare
        assert svc.fare_inr > 0.0, f"Fare must be positive for service {svc.service_id}"

        # Transport mode
        assert svc.mode in (TransportMode.TRAIN, TransportMode.BUS, TransportMode.CAB, TransportMode.ROAD)

        # Seat availability status
        assert svc.seat_availability is not None

        # Provider identifier
        assert svc.provider is not None and len(svc.provider.strip()) > 0

        # Booking URL if supported
        assert svc.booking_url is not None and svc.booking_url.startswith("http")


def test_timezone_awareness_and_overnight_accounting():
    """Verify timezone-aware timestamps and proper handling of overnight journeys."""
    all_services = get_synthetic_train_services() + get_synthetic_bus_services() + get_synthetic_cab_services()

    overnight_count = 0
    for svc in all_services:
        # Timezone-aware check
        assert svc.departure_time.tzinfo is not None, f"Departure time for {svc.service_id} must be timezone-aware"
        assert svc.arrival_time.tzinfo is not None, f"Arrival time for {svc.service_id} must be timezone-aware"

        # Check overnight flag
        dep_day = svc.departure_time.astimezone(IST).date()
        arr_day = svc.arrival_time.astimezone(IST).date()
        if arr_day > dep_day:
            assert svc.is_overnight is True, f"Service {svc.service_id} crosses midnight but is_overnight is False"
            overnight_count += 1
        elif svc.is_overnight:
            assert arr_day > dep_day, f"Service {svc.service_id} marked overnight but departs and arrives on same day"

    assert overnight_count >= 5, "Expected several overnight trains/sleepers across Delhi-Jaipur/Chandigarh corridors"


def test_demonstration_data_labeling():
    """Verify all synthetic records are clearly labeled as demonstration data."""
    all_services = get_synthetic_train_services() + get_synthetic_bus_services() + get_synthetic_cab_services()
    disruptions = get_simulated_disruptions()

    for svc in all_services:
        assert svc.is_synthetic is True, f"Service {svc.service_id} missing synthetic flag"
        assert "DEMONSTRATION" in svc.data_label

    for disr in disruptions:
        assert disr.is_synthetic is True, f"Disruption {disr.event_id} missing synthetic flag"
        assert "DEMONSTRATION" in disr.data_label


def test_database_seeding_and_retrieval(test_db: DatabaseManager):
    """Verify that seeded SQLite database correctly stores and returns all datasets."""
    locations = test_db.list_all_locations()
    services = test_db.query_services()
    disruptions = test_db.get_active_disruptions()

    assert len(locations) >= 12
    assert len(services) >= 80  # 32 trains + 32 buses + 21 cabs = 85
    assert len(disruptions) == 10

    # Verify stranded passenger record
    journey = test_db.get_user_journey("JRN-ROHAN-9901")
    assert journey is not None
    assert journey.passenger_name == "Rohan Sharma"
    assert journey.booked_service.service_id == "TRN-12015"
