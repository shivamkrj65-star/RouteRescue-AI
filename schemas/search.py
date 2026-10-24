"""Search and recovery recommendation schemas."""

from datetime import date, datetime, time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from config.settings import IST
from schemas.common import BookingStatus, SeatAvailabilityStatus, TransportMode
from schemas.disruption import DisruptionEvent
from schemas.travel import TransportService


class TransportSearchRequest(BaseModel):
    """Criteria for querying alternative travel options across the multimodal network."""
    search_id: str = Field(description="Unique query trace identifier")
    origin_city_or_code: str = Field(description="Origin city name or code e.g. Delhi or NDLS")
    destination_city_or_code: str = Field(description="Destination city name or code e.g. Jaipur or JP")
    travel_date: Optional[date] = Field(default=None, description="Optional target travel date")
    earliest_departure: Optional[time] = Field(default=None, description="Earliest departure time filter")
    latest_arrival: Optional[time] = Field(default=None, description="Latest arrival deadline filter")
    max_budget_inr: Optional[float] = Field(default=None, ge=0.0, description="Maximum budget cap in INR")
    mode: Optional[TransportMode] = Field(default=None, description="Transport mode filter")
    require_available_seats: bool = Field(default=False, description="Filter only services with available seats")
    min_seats: int = Field(default=1, ge=1, description="Minimum number of seats required")


class TravelAlternative(BaseModel):
    """A scored alternative journey presented for selection."""
    alternative_id: str = Field(description="Unique option identifier")
    rank: int = Field(ge=1, description="Recommendation ranking (1 = highest)")
    service: TransportService = Field(description="Underlying transport service details")
    total_fare_inr: float = Field(ge=0.0, description="Total fare in INR")
    departure_time: datetime = Field(description="Timezone-aware departure timestamp")
    arrival_time: datetime = Field(description="Timezone-aware arrival timestamp")
    duration_minutes: int = Field(ge=0, description="Trip duration in minutes")
    is_overnight: bool = Field(default=False, description="Whether journey traverses overnight")
    availability_status: SeatAvailabilityStatus = Field(description="Seat availability status")
    fits_budget: bool = Field(default=True, description="True if within user specified budget cap")
    tradeoffs: str = Field(description="Summary of speed, comfort, cost, and reliability tradeoffs")
    booking_url: Optional[str] = Field(default=None, description="Direct booking link")
    is_synthetic: bool = Field(default=True)
    data_label: str = Field(default="DEMONSTRATION SYNTHETIC DATASET (Fetch-A-Thon 3.0)")


class TransportSearchResponse(BaseModel):
    """Output payload from the transport search service."""
    search_id: str = Field(description="Trace ID of the request")
    origin: str = Field(description="Resolved origin location / city")
    destination: str = Field(description="Resolved destination location / city")
    search_timestamp: datetime = Field(default_factory=lambda: datetime.now(IST))
    total_found: int = Field(ge=0, description="Total matching alternative services found")
    applied_filters: Dict[str, Any] = Field(default_factory=dict, description="Summary of applied search filters")
    results: List[TravelAlternative] = Field(default_factory=list, description="Ranked alternative journey options")
    disclaimer: str = Field(
        default="All records are demonstration synthetic data for Fetch-A-Thon 3.0. No live bookings are made.",
        description="Data authenticity disclaimer",
    )


class RecoveryRecommendation(BaseModel):
    """Comprehensive recovery plan coordinated following a travel disruption."""
    recommendation_id: str = Field(description="Unique recovery recommendation ID")
    impacted_journey_id: str = Field(description="ID of the passenger journey impacted by disruption")
    trigger_disruption: DisruptionEvent = Field(description="Disruption that triggered recovery")
    recommended_alternatives: List[TravelAlternative] = Field(
        default_factory=list,
        description="Ranked candidate recovery options",
    )
    best_option: Optional[TravelAlternative] = Field(
        default=None,
        description="Top-ranked recovery option based on time and budget optimization",
    )
    approval_status: BookingStatus = Field(
        default=BookingStatus.PENDING_APPROVAL,
        description="Strict human-in-the-loop approval state",
    )
    estimated_delay_recovered_minutes: int = Field(
        default=0,
        description="Estimated delay mitigated compared to waiting for disrupted service",
    )
    cost_difference_inr: float = Field(
        default=0.0,
        description="Cost difference between original fare and recommended alternative",
    )
    rationale: str = Field(description="AI explanation explaining why this recommendation was chosen")
    requires_user_approval: bool = Field(
        default=True,
        description="Mandatory human-in-the-loop authorization flag",
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(IST))
    is_synthetic: bool = Field(default=True)
    data_label: str = Field(default="DEMONSTRATION SYNTHETIC DATASET (Fetch-A-Thon 3.0)")
