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


class ScoringWeights(Model):
    """Configurable weights for multi-criteria recovery ranking (must sum to ~1.0)."""
    duration_weight: float = Field(default=0.40, description="Weight for journey speed / duration")
    cost_weight: float = Field(default=0.30, description="Weight for fare economy vs budget")
    reliability_weight: float = Field(default=0.20, description="Weight for seat availability & mode reliability")
    transfer_weight: float = Field(default=0.10, description="Weight for minimizing transfers / directness")


class RecoveryRequest(Model):
    """Recovery planning request dispatched to the Recovery Planner Agent."""
    request_id: str = Field(description="Unique correlation ID for tracing the recovery lifecycle")
    origin: str = Field(description="Origin city name or station code (e.g. Delhi, NDLS)")
    destination: str = Field(description="Destination city name or station code (e.g. Jaipur, JP)")
    journey_date: Optional[str] = Field(default=None, description="ISO format date YYYY-MM-DD")
    earliest_departure: Optional[str] = Field(default=None, description="ISO format time or datetime for earliest allowed departure")
    latest_acceptable_arrival: Optional[str] = Field(default=None, description="ISO format time or datetime for hard arrival deadline")
    max_budget: Optional[float] = Field(default=None, description="Hard budget ceiling in INR")
    max_transfers: int = Field(default=1, description="Hard limit on allowable route transfers")
    user_id: Optional[str] = Field(default=None, description="Associated passenger ID if known")
    disrupted_service_id: Optional[str] = Field(default=None, description="Original disrupted service ID if triggered by disruption")
    weights: Optional[ScoringWeights] = Field(default=None, description="Custom multi-criteria scoring weights")


class RankedAlternative(Model):
    """Ranked recovery alternative evaluated and scored by the Recovery Planner."""
    rank: int = Field(description="Recovery ranking (1 = best, 2, 3)")
    composite_score: float = Field(description="Overall normalized utility score (0.0 - 100.0)")
    score_breakdown: dict = Field(
        default_factory=dict,
        description="Component scores e.g. duration_score, cost_score, reliability_score, transfer_score",
    )
    alternative: TransportSearchAlternative = Field(description="Underlying travel alternative")
    selection_reason: str = Field(description="Option-specific justification")


class RecoveryResponse(Model):
    """Comprehensive recovery plan returned by the Recovery Planner Agent."""
    request_id: str = Field(description="Correlating recovery request ID")
    planner_address: str = Field(description="Cryptographic address of the Recovery Planner Agent")
    success: bool = Field(description="Whether the recovery coordination succeeded")
    origin: str = Field(description="Resolved origin location")
    destination: str = Field(description="Resolved destination location")
    total_options_evaluated: int = Field(default=0, description="Total alternatives received across modal agents")
    valid_options_count: int = Field(default=0, description="Count of alternatives passing all hard constraints")
    rejected_options_count: int = Field(default=0, description="Count of alternatives rejected by hard constraints")
    rejection_reasons: dict = Field(
        default_factory=dict,
        description="Summary of rejection counts by constraint type",
    )
    top_3_options: List[RankedAlternative] = Field(
        default_factory=list,
        description="Top three recommended recovery options",
    )
    best_option_explanation: str = Field(
        default="",
        description="Detailed natural-language rationale explaining why the #1 option was selected",
    )
    modal_responses: dict = Field(
        default_factory=dict,
        description="Status summary from each modal agent (RAIL, BUS, CAB)",
    )
    error_message: Optional[str] = Field(default=None, description="Error explanation if coordination failed")
    execution_time_ms: float = Field(default=0.0, description="End-to-end recovery planning latency in ms")
    disclaimer: str = Field(
        default="Synthetic demonstration recovery plan for Fetch-A-Thon 3.0. Booking requires explicit user authorization.",
        description="Integrity and safety disclaimer",
    )


class DisruptionInjectionRequest(Model):
    """Payload for injecting a simulated disruption via API or agent messaging."""
    journey_id: str = Field(description="Target journey ID to disrupt")
    status: str = Field(description="New status e.g. CANCELLED, DELAYED, DROPPED_CHART_PREPARED, WAITLISTED")
    delay_minutes: int = Field(default=0, description="Delay duration in minutes if applicable")
    pnr_position: Optional[str] = Field(default=None, description="PNR position update e.g. WL 5, RAC 1, DROPPED")
    chart_prepared: bool = Field(default=False, description="Whether reservation chart has been finalized")
    reason: str = Field(default="Simulated disruption injection", description="Cause or operational explanation")
