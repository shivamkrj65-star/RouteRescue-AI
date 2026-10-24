"""Fetch.ai uAgents communication message models for transport search agents.

All models subclass `uagents.Model` for native serialization and protocol compliance.
"""

from typing import List, Optional
from uagents import Field, Model


class TransportSearchQuery(Model):
    """Structured search query sent to modal search agents."""
    request_id: str = Field(description="Unique correlation ID for tracing request-response lifecycle")
    origin: str = Field(description="Origin city name or station code (e.g. Delhi, NDLS)")
    destination: str = Field(description="Destination city name or station code (e.g. Jaipur, JP)")
    travel_date: Optional[str] = Field(default=None, description="ISO format date YYYY-MM-DD")
    earliest_departure: Optional[str] = Field(default=None, description="ISO format time HH:MM:SS")
    latest_arrival: Optional[str] = Field(default=None, description="ISO format time HH:MM:SS")
    max_budget_inr: Optional[float] = Field(default=None, description="Budget cap in INR")
    require_available_seats: bool = Field(default=False, description="Filter only available/few seats")
    min_seats: int = Field(default=1, description="Minimum seats required")


class TransportSearchAlternative(Model):
    """Structured travel alternative payload serialized for agent-to-agent messaging."""
    alternative_id: str = Field(description="Alternative option ID")
    rank: int = Field(description="Recommendation rank within modal search results")
    service_id: str = Field(description="Unique service identifier e.g. TRN-12015")
    service_number: str = Field(description="Train/Bus/Cab service number or name")
    provider: str = Field(description="Transit operator name")
    mode: str = Field(description="Transport mode: TRAIN, BUS, CAB")
    origin_code: str = Field(description="Departure station/terminal code")
    origin_name: str = Field(description="Departure station/terminal name")
    destination_code: str = Field(description="Arrival station/terminal code")
    destination_name: str = Field(description="Arrival station/terminal name")
    departure_time: str = Field(description="Timezone-aware departure timestamp in ISO 8601")
    arrival_time: str = Field(description="Timezone-aware arrival timestamp in ISO 8601")
    duration_minutes: int = Field(description="Duration in minutes")
    distance_km: float = Field(description="Distance in kilometers")
    fare_inr: float = Field(description="Fare in INR")
    seat_availability: str = Field(description="Seat availability status e.g. AVAILABLE, FEW_SEATS, ON_DEMAND")
    available_seats_count: Optional[int] = Field(default=None, description="Seat count if available")
    booking_url: Optional[str] = Field(default=None, description="Booking URL if supported")
    is_overnight: bool = Field(default=False, description="Overnight journey indicator")
    tradeoffs: str = Field(description="Human-readable tradeoff evaluation")
    data_label: str = Field(
        default="DEMONSTRATION SYNTHETIC DATASET (Fetch-A-Thon 3.0)",
        description="Data authenticity label",
    )


class TransportSearchResult(Model):
    """Structured result returned by modal search agents via uAgents messaging."""
    request_id: str = Field(description="Correlating request ID")
    agent_name: str = Field(description="Responding agent name e.g. rail_search_agent")
    agent_address: str = Field(description="Cryptographic address of responding agent")
    mode: str = Field(description="Transport mode handled: TRAIN, BUS, CAB")
    success: bool = Field(description="Whether the query succeeded")
    total_found: int = Field(default=0, description="Count of found alternatives")
    results: List[TransportSearchAlternative] = Field(
        default_factory=list,
        description="List of alternative options discovered",
    )
    error_message: Optional[str] = Field(default=None, description="Error explanation if search failed")
    execution_time_ms: float = Field(default=0.0, description="Runtime in milliseconds")
    disclaimer: str = Field(
        default="Demonstration synthetic data for Fetch-A-Thon 3.0. No live bookings executed.",
        description="Integrity disclaimer",
    )
