"""Pytest test configuration and fixtures."""

import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest

from routerescue.data.database import DatabaseManager
from routerescue.data.seed_data import seed_database
from routerescue.data.synthetic_corridors import LOCATIONS
from routerescue.schemas.common import (
    DataVerificationStatus,
    DisruptionSeverity,
    DisruptionType,
    OptimizationPriority,
    TransportMode,
)
from routerescue.schemas.disruption import DisruptionEvent
from routerescue.schemas.travel import Location, PassengerProfile, TravelSegment


@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    """Provides a fresh temporary database path for isolated testing."""
    return tmp_path / "test_routerescue.db"


@pytest.fixture
def db_manager(temp_db_path: Path) -> DatabaseManager:
    """Provides an initialized test database manager."""
    mgr = DatabaseManager(db_path=temp_db_path)
    mgr.init_db()
    return mgr


@pytest.fixture
def seeded_db(db_manager: DatabaseManager) -> DatabaseManager:
    """Provides a fully seeded test database."""
    seed_database(db_manager)
    return db_manager


@pytest.fixture
def sample_location_origin() -> Location:
    return LOCATIONS["EUS"]


@pytest.fixture
def sample_location_destination() -> Location:
    return LOCATIONS["MAN"]


@pytest.fixture
def sample_segment(sample_location_origin: Location, sample_location_destination: Location) -> TravelSegment:
    now = datetime.now(timezone.utc)
    return TravelSegment(
        segment_id="TEST-SEG-01",
        mode=TransportMode.TRAIN,
        operator="Avanti West Coast",
        service_number="VT-999",
        origin=sample_location_origin,
        destination=sample_location_destination,
        departure_time=now + timedelta(hours=1),
        arrival_time=now + timedelta(hours=3),
        duration_minutes=120,
        distance_km=305.0,
        price_gbp=55.0,
        seats_available=42,
        verification_status=DataVerificationStatus.SIMULATED_ESTIMATE,
        verification_source="Pytest Synthetic Fixture",
        confidence_score=0.95,
        co2_kg=11.0,
    )


@pytest.fixture
def sample_disruption() -> DisruptionEvent:
    now = datetime.now(timezone.utc)
    return DisruptionEvent(
        event_id="TEST-DISR-01",
        mode=TransportMode.TRAIN,
        disruption_type=DisruptionType.CANCELLATION,
        severity=DisruptionSeverity.CRITICAL,
        source_reference="TEST-NR-1",
        operator="Avanti West Coast",
        affected_origin="EUS",
        affected_destination="MAN",
        affected_stations=["EUS", "BHM", "MAN"],
        delay_minutes=0,
        is_cancelled=True,
        description="Emergency signal test.",
        verification_status=DataVerificationStatus.SIMULATED_ESTIMATE,
        reported_at=now,
        valid_until=now + timedelta(hours=3),
    )
