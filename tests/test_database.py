"""Unit tests for SQLite database manager and audit trail logging."""

from datetime import datetime, timedelta, timezone
from routerescue.data.database import DatabaseManager
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
    RecoveryOption,
    RecoveryPlanResponse,
    UserApprovalActionRequest,
)
from routerescue.schemas.travel import (
    Journey,
    Location,
    PassengerProfile,
    TravelSegment,
)


def test_locations_crud(db_manager: DatabaseManager, sample_location_origin: Location):
    """Test inserting, retrieving, and listing transit locations."""
    db_manager.save_location(sample_location_origin)

    fetched = db_manager.get_location("EUS")
    assert fetched is not None
    assert fetched.name == "London Euston"
    assert fetched.city == "London"

    all_locs = db_manager.list_all_locations()
    assert len(all_locs) == 1
    assert all_locs[0].code == "EUS"


def test_travel_segments_bulk_and_queries(
    db_manager: DatabaseManager,
    sample_location_origin: Location,
    sample_location_destination: Location,
    sample_segment: TravelSegment,
):
    """Test bulk segment insertion and parameterized querying."""
    db_manager.save_location(sample_location_origin)
    db_manager.save_location(sample_location_destination)

    db_manager.save_segments([sample_segment])

    # Query all
    results = db_manager.query_segments()
    assert len(results) == 1
    assert results[0].segment_id == "TEST-SEG-01"
    assert results[0].price_gbp == 55.0

    # Query with matching filter
    matching = db_manager.query_segments(
        origin_code="EUS",
        destination_code="MAN",
        mode=TransportMode.TRAIN,
        max_price_gbp=60.0,
    )
    assert len(matching) == 1

    # Query with non-matching budget
    unaffordable = db_manager.query_segments(max_price_gbp=20.0)
    assert len(unaffordable) == 0


def test_disruptions_crud(
    db_manager: DatabaseManager,
    sample_location_origin: Location,
    sample_location_destination: Location,
    sample_disruption: DisruptionEvent,
):
    """Test saving disruption and querying active incidents."""
    db_manager.save_location(sample_location_origin)
    db_manager.save_location(sample_location_destination)

    db_manager.save_disruption(sample_disruption, is_active=True)

    active = db_manager.get_active_disruptions()
    assert len(active) == 1
    assert active[0].event_id == "TEST-DISR-01"
    assert active[0].is_cancelled is True

    # Filter by station code
    bhm_disruptions = db_manager.get_active_disruptions(station_code="BHM")
    assert len(bhm_disruptions) == 1

    other_disruptions = db_manager.get_active_disruptions(station_code="XYZ")
    assert len(other_disruptions) == 0


def test_passenger_profile_with_original_journey(
    db_manager: DatabaseManager,
    sample_location_origin: Location,
    sample_location_destination: Location,
    sample_segment: TravelSegment,
):
    """Test storing passenger profile and attached disrupted journey."""
    db_manager.save_location(sample_location_origin)
    db_manager.save_location(sample_location_destination)

    journey = Journey(
        journey_id="J-ORIG-01",
        origin=sample_location_origin,
        destination=sample_location_destination,
        segments=[sample_segment],
        total_price_gbp=55.0,
        total_duration_minutes=120,
        total_transfers=0,
        departure_time=sample_segment.departure_time,
        arrival_time=sample_segment.arrival_time,
    )

    profile = PassengerProfile(
        user_id="USR-442",
        name="Alex Turner",
        email="alex@example.com",
        current_location=sample_location_origin,
        intended_destination=sample_location_destination,
        budget_gbp=100.0,
        arrival_deadline=sample_segment.arrival_time + timedelta(hours=2),
        max_transfers=2,
        priority=OptimizationPriority.FASTEST,
        requires_step_free_access=True,
        original_journey=journey,
    )

    db_manager.save_passenger_profile(profile)

    fetched = db_manager.get_passenger_profile("USR-442")
    assert fetched is not None
    assert fetched.name == "Alex Turner"
    assert fetched.requires_step_free_access is True
    assert fetched.original_journey is not None
    assert fetched.original_journey.journey_id == "J-ORIG-01"


def test_recovery_plan_and_approval_audit(
    db_manager: DatabaseManager,
    sample_location_origin: Location,
    sample_location_destination: Location,
    sample_segment: TravelSegment,
):
    """Test saving recovery plan and tracking user approval decisions."""
    db_manager.save_location(sample_location_origin)
    db_manager.save_location(sample_location_destination)

    profile = PassengerProfile(
        user_id="USR-AUDIT-1",
        name="Elena Rostova",
        email="elena@example.com",
        current_location=sample_location_origin,
        intended_destination=sample_location_destination,
        budget_gbp=120.0,
        arrival_deadline=datetime.now(timezone.utc) + timedelta(hours=4),
    )
    db_manager.save_passenger_profile(profile)

    journey = Journey(
        journey_id="J-RECOVERY-TEST",
        origin=sample_location_origin,
        destination=sample_location_destination,
        segments=[sample_segment],
        total_price_gbp=55.0,
        total_duration_minutes=120,
        total_transfers=0,
        departure_time=sample_segment.departure_time,
        arrival_time=sample_segment.arrival_time,
    )

    option = RecoveryOption(
        option_id="OPT-RECOVERY-1",
        rank=1,
        journey=journey,
        tradeoff_summary="Direct alternative via rail.",
        meets_all_constraints=True,
        estimated_arrival_buffer_minutes=45,
        risk_assessment="Low risk, 45 minute buffer ahead of deadline.",
        verification_status=DataVerificationStatus.SIMULATED_ESTIMATE,
    )

    plan = RecoveryPlanResponse(
        recovery_id="REC-TEST-77",
        passenger_id="USR-AUDIT-1",
        status=RecoveryStatus.PROPOSED,
        recommended_options=[option],
        execution_time_ms=14.2,
        explanation="Evaluated rail alternatives.",
    )

    db_manager.save_recovery_plan(plan)

    fetched_plan = db_manager.get_recovery_plan("REC-TEST-77")
    assert fetched_plan is not None
    assert len(fetched_plan.recommended_options) == 1
    assert fetched_plan.recommended_options[0].option_id == "OPT-RECOVERY-1"

    # Record User Approval Action
    action = UserApprovalActionRequest(
        action_id="ACT-APPROVAL-100",
        recovery_id="REC-TEST-77",
        option_id="OPT-RECOVERY-1",
        user_id="USR-AUDIT-1",
        decision=BookingApprovalStatus.APPROVED_BY_USER,
        user_notes="Confirmed by passenger on mobile",
    )
    db_manager.record_approval_action(action, is_booking_authorized=True)

    actions = db_manager.get_approval_actions("REC-TEST-77")
    assert len(actions) == 1
    assert actions[0]["action_id"] == "ACT-APPROVAL-100"
    assert actions[0]["decision"] == BookingApprovalStatus.APPROVED_BY_USER.value
    assert actions[0]["is_booking_authorized"] == 1
