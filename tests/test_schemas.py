"""Unit tests for shared Pydantic data models."""

from datetime import date, datetime, time, timedelta
import pytest
from pydantic import ValidationError

from config.settings import IST
from schemas.common import (
    BookingStatus,
    DisruptionSeverity,
    DisruptionType,
    RecoveryStatus,
    SeatAvailabilityStatus,
    TransportMode,
)
from schemas.disruption import DisruptionEvent
from schemas.search import (
    RecoveryRecommendation,
    TransportSearchRequest,
    TransportSearchResponse,
    TravelAlternative,
)
from schemas.travel import Location, TransportService, UserJourney


def test_location_model_validation():
    """Verify Location model creation and constraints."""
    loc = Location(
        code="NDLS",
        name="New Delhi Railway Station",
        city="Delhi",
        state="Delhi",
        latitude=28.6415,
        longitude=77.2194,
    )
    assert loc.code == "NDLS"
    assert loc.city == "Delhi"

    # Test JSON dump & reconstruction
    data = loc.model_dump()
    reconstructed = Location.model_validate(data)
    assert reconstructed == loc


def test_transport_service_model():
    """Verify TransportService validation and demonstration labels."""
    now = datetime.now(IST)
    orig = Location(code="NDLS", name="New Delhi", city="Delhi", state="Delhi", latitude=28.6, longitude=77.2)
    dest = Location(code="JP", name="Jaipur Jn", city="Jaipur", state="Rajasthan", latitude=26.9, longitude=75.7)

    service = TransportService(
        service_id="TRN-12015",
        mode=TransportMode.TRAIN,
        provider="Indian Railways",
        service_number="12015 Ajmer Shatabdi",
        origin=orig,
        destination=dest,
        departure_time=now,
        arrival_time=now + timedelta(hours=4, minutes=40),
        duration_minutes=280,
        distance_km=308.0,
        fare_inr=940.0,
        seat_availability=SeatAvailabilityStatus.AVAILABLE,
        available_seats_count=45,
        booking_url="https://www.irctc.co.in",
        is_overnight=False,
    )
    assert service.service_id == "TRN-12015"
    assert service.fare_inr == 940.0
    assert service.is_synthetic is True
    assert "DEMONSTRATION" in service.data_label


def test_user_journey_model():
    """Verify UserJourney and BookingStatus lifecycle."""
    now = datetime.now(IST)
    orig = Location(code="NDLS", name="New Delhi", city="Delhi", state="Delhi", latitude=28.6, longitude=77.2)
    dest = Location(code="JP", name="Jaipur Jn", city="Jaipur", state="Rajasthan", latitude=26.9, longitude=75.7)

    service = TransportService(
        service_id="TRN-12015",
        mode=TransportMode.TRAIN,
        provider="Indian Railways",
        service_number="12015 Ajmer Shatabdi",
        origin=orig,
        destination=dest,
        departure_time=now,
        arrival_time=now + timedelta(hours=4, minutes=40),
        duration_minutes=280,
        distance_km=308.0,
        fare_inr=940.0,
    )

    journey = UserJourney(
        journey_id="JRN-TEST-001",
        passenger_name="Aarav Mehta",
        passenger_email="aarav@example.com",
        booked_service=service,
        booking_status=BookingStatus.CONFIRMED,
        booking_reference="PNR-1092841029",
        booked_fare_inr=940.0,
    )
    assert journey.booking_status == BookingStatus.CONFIRMED
    assert journey.passenger_name == "Aarav Mehta"
    assert journey.is_synthetic is True

    # Test status change when disruption strikes
    journey.booking_status = BookingStatus.CANCELLED_BY_DISRUPTION
    assert journey.booking_status == BookingStatus.CANCELLED_BY_DISRUPTION


def test_disruption_event_model():
    """Verify DisruptionEvent schema and fields."""
    now = datetime.now(IST)
    event = DisruptionEvent(
        event_id="DISR-TEST-01",
        mode=TransportMode.TRAIN,
        disruption_type=DisruptionType.FOG_DELAY,
        severity=DisruptionSeverity.CRITICAL,
        source_reference="NR-FOG-TEST",
        operator="Northern Railway",
        affected_origin="NDLS",
        affected_destination="AGC",
        affected_stations=["NDLS", "MTJ", "AGC"],
        delay_minutes=150,
        is_cancelled=False,
        headline="Winter Fog Halts Trains",
        description="Visibility below 50m.",
        reported_at=now,
    )
    assert event.is_cancelled is False
    assert event.delay_minutes == 150
    assert event.is_synthetic is True
    assert "DEMONSTRATION" in event.data_label


def test_transport_search_request_and_response_models():
    """Verify TransportSearchRequest and TransportSearchResponse schemas."""
    now = datetime.now(IST)
    req = TransportSearchRequest(
        search_id="REQ-TEST-01",
        origin_city_or_code="Delhi",
        destination_city_or_code="Jaipur",
        travel_date=date(2026, 10, 24),
        earliest_departure=time(6, 0),
        latest_arrival=time(22, 0),
        max_budget_inr=1500.0,
        mode=TransportMode.TRAIN,
        require_available_seats=True,
    )
    assert req.origin_city_or_code == "Delhi"
    assert req.max_budget_inr == 1500.0

    orig = Location(code="NDLS", name="New Delhi", city="Delhi", state="Delhi", latitude=28.6, longitude=77.2)
    dest = Location(code="JP", name="Jaipur Jn", city="Jaipur", state="Rajasthan", latitude=26.9, longitude=75.7)
    service = TransportService(
        service_id="TRN-12015",
        mode=TransportMode.TRAIN,
        provider="Indian Railways",
        service_number="12015 Ajmer Shatabdi",
        origin=orig,
        destination=dest,
        departure_time=now,
        arrival_time=now + timedelta(hours=4),
        duration_minutes=240,
        distance_km=308.0,
        fare_inr=940.0,
    )

    alt = TravelAlternative(
        alternative_id="ALT-01",
        rank=1,
        service=service,
        total_fare_inr=940.0,
        departure_time=service.departure_time,
        arrival_time=service.arrival_time,
        duration_minutes=240,
        is_overnight=False,
        availability_status=SeatAvailabilityStatus.AVAILABLE,
        fits_budget=True,
        tradeoffs="Fastest executive train.",
    )

    resp = TransportSearchResponse(
        search_id=req.search_id,
        origin="Delhi",
        destination="Jaipur",
        search_timestamp=now,
        total_found=1,
        applied_filters={"mode": "TRAIN"},
        results=[alt],
    )
    assert resp.total_found == 1
    assert resp.results[0].rank == 1
    assert "demonstration" in resp.disclaimer.lower()


def test_recovery_recommendation_model():
    """Verify RecoveryRecommendation schema and human-in-the-loop requirement."""
    now = datetime.now(IST)
    orig = Location(code="NDLS", name="New Delhi", city="Delhi", state="Delhi", latitude=28.6, longitude=77.2)
    dest = Location(code="JP", name="Jaipur Jn", city="Jaipur", state="Rajasthan", latitude=26.9, longitude=75.7)

    service = TransportService(
        service_id="BUS-ZB-101",
        mode=TransportMode.BUS,
        provider="Zingbus",
        service_number="Volvo 9600 Express",
        origin=orig,
        destination=dest,
        departure_time=now + timedelta(hours=1),
        arrival_time=now + timedelta(hours=6),
        duration_minutes=300,
        distance_km=290.0,
        fare_inr=550.0,
    )

    alt = TravelAlternative(
        alternative_id="ALT-BUS-101",
        rank=1,
        service=service,
        total_fare_inr=550.0,
        departure_time=service.departure_time,
        arrival_time=service.arrival_time,
        duration_minutes=300,
        is_overnight=False,
        availability_status=SeatAvailabilityStatus.AVAILABLE,
        fits_budget=True,
        tradeoffs="Express bus departing in 60 mins.",
    )

    disr = DisruptionEvent(
        event_id="D-1",
        mode=TransportMode.TRAIN,
        disruption_type=DisruptionType.TRACK_MAINTENANCE,
        severity=DisruptionSeverity.CRITICAL,
        source_reference="REF-1",
        operator="Northern Railway",
        affected_origin="NDLS",
        affected_destination="JP",
        headline="Track Repair",
        description="Emergency work.",
        reported_at=now,
    )

    rec = RecoveryRecommendation(
        recommendation_id="REC-001",
        impacted_journey_id="JRN-ROHAN-9901",
        trigger_disruption=disr,
        recommended_alternatives=[alt],
        best_option=alt,
        approval_status=BookingStatus.PENDING_APPROVAL,
        estimated_delay_recovered_minutes=180,
        cost_difference_inr=-390.0,
        rationale="Shift from cancelled train to Zingbus departing within 1 hour.",
        requires_user_approval=True,
    )
    assert rec.requires_user_approval is True
    assert rec.approval_status == BookingStatus.PENDING_APPROVAL
    assert rec.best_option is not None
    assert rec.best_option.alternative_id == "ALT-BUS-101"
