"""Pytest fixtures for RouteRescue AI Phase 1 test suite."""

from datetime import datetime, timezone
from pathlib import Path
import pytest

from config.settings import IST
from data.database import DatabaseManager
from data.seed_data import seed_database
from schemas.common import SeatAvailabilityStatus, TransportMode
from schemas.travel import Location, TransportService
from services.transport_service import TransportDataService


@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    """Provides an isolated SQLite database path per test."""
    return tmp_path / "test_routerescue.db"


@pytest.fixture
def test_db(temp_db_path: Path) -> DatabaseManager:
    """Provides an initialized, freshly seeded test database."""
    db = DatabaseManager(db_path=temp_db_path)
    seed_database(db)
    return db


@pytest.fixture
def transport_service(test_db: DatabaseManager) -> TransportDataService:
    """Provides an instance of TransportDataService hooked to the test database."""
    return TransportDataService(db=test_db)


@pytest.fixture
def sample_location_delhi() -> Location:
    return Location(
        code="NDLS",
        name="New Delhi Railway Station",
        city="Delhi",
        state="Delhi",
        latitude=28.6415,
        longitude=77.2194,
        location_type="railway_station",
    )


@pytest.fixture
def sample_location_jaipur() -> Location:
    return Location(
        code="JP",
        name="Jaipur Junction Railway Station",
        city="Jaipur",
        state="Rajasthan",
        latitude=26.9200,
        longitude=75.7878,
        location_type="railway_station",
    )
