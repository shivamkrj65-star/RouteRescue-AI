"""Unit tests for synthetic dataset generation and corridor consistency."""

from datetime import datetime, timezone
from routerescue.data.database import DatabaseManager
from routerescue.data.seed_data import generate_synthetic_segments
from routerescue.data.synthetic_corridors import (
    LOCATIONS,
    get_default_disruption_scenarios,
)
from routerescue.schemas.common import DataVerificationStatus, TransportMode


def test_locations_corridor_integrity():
    """Verify that all core hubs are defined with valid coordinates and types."""
    required_codes = ["EUS", "BHM", "MAN", "VIC", "LHR", "LDS", "EDB"]
    for code in required_codes:
        assert code in LOCATIONS, f"Missing core location {code}"
        loc = LOCATIONS[code]
        assert loc.name
        assert loc.city
        assert -90.0 <= loc.latitude <= 90.0
        assert -180.0 <= loc.longitude <= 180.0


def test_synthetic_segments_generation():
    """Test multimodal timetable generator for realistic constraints."""
    now = datetime.now(timezone.utc)
    segments = generate_synthetic_segments(base_time=now, num_days=1)

    assert len(segments) > 500, "Should generate dense schedules for multimodal routing"

    # Modes represented
    modes = {s.mode for s in segments}
    assert TransportMode.TRAIN in modes
    assert TransportMode.BUS in modes
    assert TransportMode.CAB in modes
    assert TransportMode.FLIGHT in modes

    # Integrity checks on every segment
    for seg in segments:
        assert seg.arrival_time > seg.departure_time, f"Arrival must follow departure in {seg.segment_id}"
        delta_min = (seg.arrival_time - seg.departure_time).total_seconds() / 60
        assert abs(delta_min - seg.duration_minutes) < 1e-3
        assert seg.price_gbp >= 0.0
        assert seg.distance_km > 0.0
        assert seg.verification_status == DataVerificationStatus.SIMULATED_ESTIMATE
        assert "Synthetic" in seg.verification_source


def test_default_disruption_scenarios_relevance():
    """Verify that default disruption scenarios match actual corridor transit hubs."""
    disruptions = get_default_disruption_scenarios()
    assert len(disruptions) >= 3

    # Check rail disruption
    rail_disr = next(d for d in disruptions if d.mode == TransportMode.TRAIN)
    assert rail_disr.affected_origin in LOCATIONS
    assert rail_disr.affected_destination in LOCATIONS
    assert rail_disr.is_cancelled is True
    assert rail_disr.verification_status == DataVerificationStatus.SIMULATED_ESTIMATE


def test_seeded_database_fixture(seeded_db: DatabaseManager):
    """Test full database seeding integration."""
    locations = seeded_db.list_all_locations()
    assert len(locations) >= 10

    disruptions = seeded_db.get_active_disruptions()
    assert len(disruptions) >= 3

    passenger = seeded_db.get_passenger_profile("USR-PASSENGER-7712")
    assert passenger is not None
    assert passenger.name == "Sarah Jenkins"
    assert passenger.original_journey is not None
    assert passenger.budget_gbp == 140.0
