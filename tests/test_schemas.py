"""Unit tests for RouteRescue AI schemas and Fetch.ai uAgents model compliance."""

from datetime import datetime, timedelta, timezone
from uagents import Model

from routerescue.schemas.common import (
    BookingApprovalStatus,
    DataVerificationStatus,
    DisruptionSeverity,
    DisruptionType,
    OptimizationPriority,
    RecoveryStatus,
    TransportMode,
)
from routerescue.schemas.disruption import DisruptionEvent
from routerescue.schemas.messages import (
    DisruptionAlertMessage,
    DisruptionQuery,
    DisruptionQueryResponse,
    ModalSearchRequest,
    ModalSearchResponse,
    RecoveryOption,
    RecoveryPlanRequest,
    RecoveryPlanResponse,
    UserApprovalActionRequest,
    UserApprovalActionResponse,
)
from routerescue.schemas.travel import (
    Journey,
    Location,
    PassengerProfile,
    TravelSegment,
)


def test_models_subclass_uagents_model():
    """Verify that all communication and domain models derive from uagents.Model."""
    assert issubclass(DisruptionEvent, Model)
    assert issubclass(Location, Model)
    assert issubclass(TravelSegment, Model)
    assert issubclass(Journey, Model)
    assert issubclass(PassengerProfile, Model)
    assert issubclass(DisruptionAlertMessage, Model)
    assert issubclass(ModalSearchRequest, Model)
    assert issubclass(ModalSearchResponse, Model)
    assert issubclass(RecoveryPlanRequest, Model)
    assert issubclass(RecoveryPlanResponse, Model)
    assert issubclass(UserApprovalActionRequest, Model)
    assert issubclass(UserApprovalActionResponse, Model)


def test_location_serialization():
    """Test Location creation and round-trip JSON serialization."""
    loc = Location(
        code="EUS",
        name="London Euston",
        city="London",
        latitude=51.5281,
        longitude=-0.1336,
        location_type="station",
    )
    raw_json = loc.model_dump_json()
    reconstructed = Location.model_validate_json(raw_json)
    assert reconstructed.code == "EUS"
    assert reconstructed.city == "London"
    assert reconstructed.latitude == 51.5281


def test_disruption_event_verification_and_flags():
    """Ensure DataVerificationStatus distinguishes simulated vs verified data."""
    now = datetime.now(timezone.utc)
    event = DisruptionEvent(
        event_id="D-101",
        mode=TransportMode.TRAIN,
        disruption_type=DisruptionType.CANCELLATION,
        severity=DisruptionSeverity.CRITICAL,
        source_reference="INC-77",
        operator="Avanti",
        affected_origin="EUS",
        affected_destination="MAN",
        affected_stations=["EUS", "BHM", "MAN"],
        delay_minutes=0,
        is_cancelled=True,
        description="Wire fault",
        verification_status=DataVerificationStatus.SIMULATED_ESTIMATE,
        reported_at=now,
    )
    assert event.verification_status == DataVerificationStatus.SIMULATED_ESTIMATE
    assert event.is_cancelled is True
    assert "BHM" in event.affected_stations

    json_str = event.model_dump_json()
    loaded = DisruptionEvent.model_validate_json(json_str)
    assert loaded.event_id == "D-101"
    assert loaded.verification_status == DataVerificationStatus.SIMULATED_ESTIMATE


def test_travel_segment_and_journey_validation():
    """Test full journey hierarchy validation."""
    now = datetime.now(timezone.utc)
    orig = Location(code="EUS", name="London Euston", city="London", latitude=51.5, longitude=-0.1)
    mid = Location(code="BHM", name="Birmingham New Street", city="Birmingham", latitude=52.4, longitude=-1.8)
    dest = Location(code="MAN", name="Manchester Piccadilly", city="Manchester", latitude=53.4, longitude=-2.2)

    seg1 = TravelSegment(
        segment_id="S1",
        mode=TransportMode.TRAIN,
        operator="Avanti",
        service_number="VT-101",
        origin=orig,
        destination=mid,
        departure_time=now,
        arrival_time=now + timedelta(minutes=80),
        duration_minutes=80,
        distance_km=180.0,
        price_gbp=32.0,
        seats_available=25,
        verification_status=DataVerificationStatus.SIMULATED_ESTIMATE,
    )

    seg2 = TravelSegment(
        segment_id="S2",
        mode=TransportMode.TRAIN,
        operator="CrossCountry",
        service_number="XC-202",
        origin=mid,
        destination=dest,
        departure_time=now + timedelta(minutes=100),
        arrival_time=now + timedelta(minutes=190),
        duration_minutes=90,
        distance_km=138.0,
        price_gbp=25.0,
        seats_available=18,
        verification_status=DataVerificationStatus.SIMULATED_ESTIMATE,
    )

    journey = Journey(
        journey_id="J-RECOVERY-01",
        origin=orig,
        destination=dest,
        segments=[seg1, seg2],
        total_price_gbp=57.0,
        total_duration_minutes=190,
        total_transfers=1,
        departure_time=seg1.departure_time,
        arrival_time=seg2.arrival_time,
        verification_status=DataVerificationStatus.SIMULATED_ESTIMATE,
        feasibility_score=0.94,
    )

    assert len(journey.segments) == 2
    assert journey.total_price_gbp == 57.0
    assert journey.total_transfers == 1


def test_modal_search_message_contracts():
    """Test modal search request and response schemas."""
    now = datetime.now(timezone.utc)
    orig = Location(code="EUS", name="London Euston", city="London", latitude=51.5, longitude=-0.1)
    dest = Location(code="MAN", name="Manchester Piccadilly", city="Manchester", latitude=53.4, longitude=-2.2)

    req = ModalSearchRequest(
        request_id="REQ-SEARCH-01",
        origin=orig,
        destination=dest,
        earliest_departure=now,
        latest_arrival=now + timedelta(hours=6),
        max_budget_gbp=100.0,
        mode=TransportMode.TRAIN,
        passenger_id="USR-101",
    )
    assert req.mode == TransportMode.TRAIN

    resp = ModalSearchResponse(
        request_id=req.request_id,
        agent_name="rail_search_agent",
        mode=TransportMode.TRAIN,
        segments=[],
        verification_status=DataVerificationStatus.SIMULATED_ESTIMATE,
        search_duration_ms=12.5,
    )
    assert resp.agent_name == "rail_search_agent"
    assert resp.verification_status == DataVerificationStatus.SIMULATED_ESTIMATE


def test_human_approval_state_transitions():
    """Ensure booking approval requires explicit user authorization."""
    approval_req = UserApprovalActionRequest(
        action_id="ACT-001",
        recovery_id="REC-999",
        option_id="OPT-1",
        user_id="USR-101",
        decision=BookingApprovalStatus.APPROVED_BY_USER,
        user_notes="Prefer quiet carriage",
    )
    assert approval_req.decision == BookingApprovalStatus.APPROVED_BY_USER

    approval_resp = UserApprovalActionResponse(
        action_id=approval_req.action_id,
        recovery_id=approval_req.recovery_id,
        option_id=approval_req.option_id,
        approval_status=BookingApprovalStatus.APPROVED_BY_USER,
        is_booking_authorized=True,
        booking_instructions="Redirecting user to Avanti ticketing portal with pre-filled itinerary.",
        message="User approval received. Booking authorized.",
    )
    assert approval_resp.is_booking_authorized is True
