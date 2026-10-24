"""Travel, segment, journey, and passenger profile schemas."""

from datetime import datetime
from typing import List, Optional
from uagents import Field, Model

from routerescue.schemas.common import (
    BookingApprovalStatus,
    DataVerificationStatus,
    OptimizationPriority,
    TransportMode,
)


class Location(Model):
    """Geographic and transit node entity."""
    code: str = Field(description="Transit station code, IATA code, or slug (e.g., EUS, MAN, LHR)")
    name: str = Field(description="Full friendly name (e.g., London Euston, Manchester Piccadilly)")
    city: str = Field(description="City or metropolitan area name")
    latitude: float = Field(description="Latitude coordinate")
    longitude: float = Field(description="Longitude coordinate")
    location_type: str = Field(
        default="station",
        description="Type: station, airport, coach_station, metro_stop, street_address",
    )


class TravelSegment(Model):
    """An individual leg of a multimodal journey."""
    segment_id: str = Field(description="Unique segment identifier")
    mode: TransportMode = Field(description="Transport mode used for this segment")
    operator: str = Field(description="Transit service operator (e.g., Avanti, National Express, Uber)")
    service_number: str = Field(description="Train number, flight code, or coach service ID")
    origin: Location = Field(description="Departure location")
    destination: Location = Field(description="Arrival location")
    departure_time: datetime = Field(description="Scheduled departure timestamp")
    arrival_time: datetime = Field(description="Scheduled arrival timestamp")
    duration_minutes: int = Field(ge=0, description="Transit duration in minutes")
    distance_km: float = Field(ge=0.0, description="Transit distance in kilometers")
    price_gbp: float = Field(ge=0.0, description="Ticket or fare price in GBP")
    seats_available: Optional[int] = Field(
        default=None,
        description="Available capacity count if known, None if unmetered",
    )
    verification_status: DataVerificationStatus = Field(
        default=DataVerificationStatus.SIMULATED_ESTIMATE,
        description="Differentiates verified partner inventory vs synthetic travel estimate",
    )
    verification_source: str = Field(
        default="Synthetic Multi-Corridor Dataset v1.0",
        description="Audit attribution describing the exact source feed or calculation model",
    )
    confidence_score: float = Field(
        default=0.95,
        ge=0.0,
        le=1.0,
        description="Reliability and schedule confidence rating",
    )
    co2_kg: Optional[float] = Field(
        default=None,
        description="Estimated carbon footprint in kilograms of CO2",
    )


class Journey(Model):
    """A complete end-to-end trip comprising one or more connected segments."""
    journey_id: str = Field(description="Unique journey identification")
    origin: Location = Field(description="Trip origin")
    destination: Location = Field(description="Trip final destination")
    segments: List[TravelSegment] = Field(default_factory=list, description="Ordered trip legs")
    total_price_gbp: float = Field(ge=0.0, description="Cumulative price in GBP")
    total_duration_minutes: int = Field(ge=0, description="Total journey time including layovers")
    total_transfers: int = Field(ge=0, description="Number of transfers between segments")
    departure_time: datetime = Field(description="Initial departure timestamp")
    arrival_time: datetime = Field(description="Final destination arrival timestamp")
    verification_status: DataVerificationStatus = Field(
        default=DataVerificationStatus.SIMULATED_ESTIMATE,
        description="Aggregate verification tag across all included segments",
    )
    feasibility_score: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Calculated feasibility and safety margin rating",
    )
    notes: List[str] = Field(default_factory=list, description="Advisories, transfer warnings, or highlights")


class PassengerProfile(Model):
    """User context, disruption state, and recovery constraints."""
    user_id: str = Field(description="Unique passenger ID")
    name: str = Field(description="Passenger display name")
    email: str = Field(default="passenger@example.com", description="Notification contact")
    current_location: Location = Field(description="Where the passenger is stranded or located")
    intended_destination: Location = Field(description="Final intended destination")
    budget_gbp: float = Field(ge=0.0, description="Maximum budget allocated for recovery")
    arrival_deadline: datetime = Field(description="Hard cutoff time for reaching the destination")
    max_transfers: int = Field(default=3, ge=0, description="Maximum acceptable transfers")
    priority: OptimizationPriority = Field(
        default=OptimizationPriority.BALANCED,
        description="User preference objective",
    )
    requires_step_free_access: bool = Field(default=False, description="Accessibility constraint")
    original_journey: Optional[Journey] = Field(
        default=None,
        description="Original ticketed journey that suffered disruption",
    )
