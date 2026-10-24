"""Unit tests for TransportDataService search, filtering, and recovery evaluation."""

from datetime import datetime, time, timedelta
import pytest

from config.settings import IST
from schemas.common import SeatAvailabilityStatus, TransportMode
from schemas.search import TransportSearchRequest, TransportSearchResponse
from services.transport_service import TransportDataService


def test_resolve_location_codes(transport_service: TransportDataService):
    """Verify city name resolution to underlying station codes."""
    delhi_codes = transport_service.resolve_location_codes("Delhi")
    assert "NDLS" in delhi_codes
    assert "NZM" in delhi_codes
    assert "DEL_ISBT" in delhi_codes

    jaipur_codes = transport_service.resolve_location_codes("Jaipur")
    assert "JP" in jaipur_codes
    assert "JAI_BUS" in jaipur_codes

    # Direct station code
    exact_code = transport_service.resolve_location_codes("AGC")
    assert exact_code == ["AGC"]


def test_search_delhi_to_jaipur_all_modes(transport_service: TransportDataService):
    """Test searching between Delhi and Jaipur across all transport modes."""
    response = transport_service.search_by_params(
        origin="Delhi",
        destination="Jaipur",
    )

    assert isinstance(response, TransportSearchResponse)
    assert response.total_found > 0
    assert len(response.results) == response.total_found

    # Verify ranked ordering (sorted by duration, then fare)
    durations = [alt.duration_minutes for alt in response.results]
    assert durations == sorted(durations)

    # Verify representation of multimodal alternatives
    found_modes = {alt.service.mode for alt in response.results}
    assert TransportMode.TRAIN in found_modes
    assert TransportMode.BUS in found_modes
    assert TransportMode.CAB in found_modes


def test_search_with_budget_constraint(transport_service: TransportDataService):
    """Test filtering alternatives within an affordable budget cap."""
    budget_cap = 600.0
    response = transport_service.search_by_params(
        origin="Delhi",
        destination="Jaipur",
        max_budget_inr=budget_cap,
    )

    assert response.total_found > 0
    for alt in response.results:
        assert alt.total_fare_inr <= budget_cap, f"Fare {alt.total_fare_inr} exceeds budget {budget_cap}"
        assert alt.fits_budget is True


def test_search_with_mode_filter(transport_service: TransportDataService):
    """Test filtering strictly by transport mode."""
    # Rail only
    train_resp = transport_service.search_by_params(
        origin="Delhi",
        destination="Chandigarh",
        mode=TransportMode.TRAIN,
    )
    assert train_resp.total_found > 0
    for alt in train_resp.results:
        assert alt.service.mode == TransportMode.TRAIN

    # Bus only
    bus_resp = transport_service.search_by_params(
        origin="Delhi",
        destination="Chandigarh",
        mode=TransportMode.BUS,
    )
    assert bus_resp.total_found > 0
    for alt in bus_resp.results:
        assert alt.service.mode == TransportMode.BUS


def test_search_with_earliest_departure(transport_service: TransportDataService):
    """Test departure time window filtering."""
    cutoff = time(14, 0)  # 2:00 PM
    response = transport_service.search_by_params(
        origin="Delhi",
        destination="Agra",
        earliest_departure=cutoff,
    )

    assert response.total_found > 0
    for alt in response.results:
        dep_time = alt.departure_time.astimezone(IST).time()
        assert dep_time >= cutoff, f"Departure {dep_time} was before cutoff {cutoff}"


def test_search_with_available_seats_only(transport_service: TransportDataService):
    """Test filtering out waitlisted and sold-out services."""
    response = transport_service.search_by_params(
        origin="Delhi",
        destination="Jaipur",
        require_available_seats=True,
    )

    assert response.total_found > 0
    allowed_statuses = (
        SeatAvailabilityStatus.AVAILABLE,
        SeatAvailabilityStatus.FEW_SEATS,
        SeatAvailabilityStatus.ON_DEMAND,
    )
    for alt in response.results:
        assert alt.availability_status in allowed_statuses


def test_overnight_journey_search(transport_service: TransportDataService):
    """Verify that overnight journeys crossing midnight are identified and searchable."""
    response = transport_service.search_by_params(
        origin="Delhi",
        destination="Jaipur",
        earliest_departure=time(22, 0),
    )

    assert response.total_found > 0
    overnight_alts = [alt for alt in response.results if alt.is_overnight]
    assert len(overnight_alts) >= 1

    for o_alt in overnight_alts:
        assert o_alt.arrival_time > o_alt.departure_time
        # Checks that arrival is next morning
        dep_day = o_alt.departure_time.astimezone(IST).date()
        arr_day = o_alt.arrival_time.astimezone(IST).date()
        assert arr_day > dep_day


def test_nonexistent_corridor_empty_result(transport_service: TransportDataService):
    """Verify that a non-connected route returns 0 results cleanly without errors."""
    response = transport_service.search_by_params(
        origin="Agra",
        destination="Chandigarh",
        max_budget_inr=100.0,  # Unrealistic low budget
    )
    assert response.total_found == 0
    assert len(response.results) == 0


def test_check_service_disruptions(transport_service: TransportDataService):
    """Test checking if a specific service is impacted by active disruptions."""
    # TRN-12015 Ajmer Shatabdi on Delhi-Jaipur line is cancelled in simulated disruption DISR-CNCL-003
    disruptions = transport_service.check_service_disruptions("TRN-12015")
    assert len(disruptions) >= 1
    assert any(d.event_id == "DISR-CNCL-003" for d in disruptions)
    assert disruptions[0].is_cancelled is True


def test_tradeoff_summary_generation(transport_service: TransportDataService):
    """Verify that trade-off summaries are informative and tailored per transport mode."""
    response = transport_service.search_by_params(origin="Delhi", destination="Agra")
    for alt in response.results:
        assert len(alt.tradeoffs) > 10
        assert any(keyword in alt.tradeoffs.lower() for keyword in ["train", "bus", "cab", "fastest", "budget", "express"])
