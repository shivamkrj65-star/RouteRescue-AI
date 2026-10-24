"""Agent-to-agent and external interface message schemas for RouteRescue AI.

All message schemas derive from `uagents.Model` for Fetch.ai messaging compliance.
"""

from datetime import datetime, timezone
from typing import List, Optional
from uagents import Field, Model

from routerescue.schemas.common import (
    BookingApprovalStatus,
    DataVerificationStatus,
    OptimizationPriority,
    RecoveryStatus,
    TransportMode,
)
from routerescue.schemas.disruption import DisruptionEvent
from routerescue.schemas.travel import Journey, Location, PassengerProfile, TravelSegment


# -----------------------------------------------------------------------------
# 1. Disruption Monitor Agent Messages
# -----------------------------------------------------------------------------

class DisruptionAlertMessage(Model):
    """Broadcast/direct alert sent from Disruption Monitor Agent to Recovery Planner."""
    alert_id: str = Field(description="Unique alert identifier")
    disruption: DisruptionEvent = Field(description="Details of the detected disruption")
    affected_journey_ids: List[str] = Field(
        default_factory=list,
        description="IDs of registered passenger journeys impacted by this event",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Alert creation timestamp",
    )


class DisruptionQuery(Model):
    """Query active disruptions by corridor, station, or mode."""
    query_id: str = Field(description="Unique query identifier")
    origin_code: Optional[str] = Field(default=None, description="Optional origin station/airport code")
    destination_code: Optional[str] = Field(default=None, description="Optional destination station/airport code")
    mode: Optional[TransportMode] = Field(default=None, description="Optional transport mode filter")


class DisruptionQueryResponse(Model):
    """Response containing active travel disruptions."""
    query_id: str = Field(description="Correlating query identifier")
    active_disruptions: List[DisruptionEvent] = Field(
        default_factory=list,
        description="List of active disruptions matching query",
    )
    count: int = Field(ge=0, description="Total matching disruptions count")
    reported_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# -----------------------------------------------------------------------------
# 2. Modal Search Agent Messages (Rail, Bus, Cab & Road)
# -----------------------------------------------------------------------------

class ModalSearchRequest(Model):
    """Request dispatched from Recovery Planner to specialized Modal Search Agents."""
    request_id: str = Field(description="Correlation request ID")
    origin: Location = Field(description="Search leg departure location")
    destination: Location = Field(description="Search leg destination location")
    earliest_departure: datetime = Field(description="Earliest time passenger can leave")
    latest_arrival: datetime = Field(description="Cutoff arrival time at destination")
    max_budget_gbp: float = Field(ge=0.0, description="Allocated budget cap for this leg")
    mode: TransportMode = Field(description="Target transport mode for the agent")
    passenger_id: str = Field(description="Passenger seeking alternatives")
    requires_step_free_access: bool = Field(default=False)


class ModalSearchResponse(Model):
    """Response returned by Modal Search Agents back to Recovery Planner."""
    request_id: str = Field(description="Correlating search request ID")
    agent_name: str = Field(description="Responding agent identifier (e.g. rail_search_agent)")
    mode: TransportMode = Field(description="Transport mode handled")
    segments: List[TravelSegment] = Field(
        default_factory=list,
        description="Candidate segments discovered by this search agent",
    )
    verification_status: DataVerificationStatus = Field(
        default=DataVerificationStatus.SIMULATED_ESTIMATE,
        description="Verified partner status vs synthetic dataset",
    )
    search_duration_ms: float = Field(default=0.0, ge=0.0, description="Execution runtime in milliseconds")
    error_message: Optional[str] = Field(default=None, description="Any search error encountered")


# -----------------------------------------------------------------------------
# 3. Recovery Planner Agent Messages
# -----------------------------------------------------------------------------

class RecoveryPlanRequest(Model):
    """Trigger sent to Recovery Planner Agent to compute multimodal recovery options."""
    recovery_id: str = Field(description="Unique recovery pipeline execution ID")
    passenger: PassengerProfile = Field(description="Passenger requirements and constraints")
    trigger_disruption_id: Optional[str] = Field(
        default=None,
        description="ID of the disruption triggering this recovery, if known",
    )
    priority_override: Optional[OptimizationPriority] = Field(
        default=None,
        description="Optional override for optimization objective",
    )


class RecoveryOption(Model):
    """A scored alternative recovery route presented to the passenger."""
    option_id: str = Field(description="Unique option ID")
    rank: int = Field(ge=1, description="Ranking recommendation (1 = best)")
    journey: Journey = Field(description="Complete multimodal journey")
    tradeoff_summary: str = Field(description="Clear explanation of cost, time, and transfer tradeoffs")
    meets_all_constraints: bool = Field(default=True, description="Strict budget & deadline conformance")
    estimated_arrival_buffer_minutes: int = Field(
        description="Minutes between journey arrival and user deadline (negative if late)",
    )
    risk_assessment: str = Field(description="Layover buffer and reliability commentary")
    verification_status: DataVerificationStatus = Field(
        default=DataVerificationStatus.SIMULATED_ESTIMATE,
        description="Authenticity flag: verified live vs synthetic",
    )


class RecoveryPlanResponse(Model):
    """Synthesized multimodal recovery plan returned by Recovery Planner Agent."""
    recovery_id: str = Field(description="Correlating recovery ID")
    passenger_id: str = Field(description="Passenger ID")
    status: RecoveryStatus = Field(description="Plan generation outcome status")
    recommended_options: List[RecoveryOption] = Field(
        default_factory=list,
        description="Ranked multimodal alternative journeys",
    )
    execution_time_ms: float = Field(ge=0.0, description="Planning pipeline execution time in ms")
    explanation: str = Field(description="Architectural rationale and decision breakdown")
    disclaimer: str = Field(
        default="All alternatives require explicit user approval. Simulated options are clearly marked.",
        description="Legal and human-in-the-loop safety disclosure",
    )


# -----------------------------------------------------------------------------
# 4. Human-In-The-Loop Approval Messages
# -----------------------------------------------------------------------------

class UserApprovalActionRequest(Model):
    """
    Message sent when a user interacts with the UI to approve, reject,
    or modify a proposed recovery option.
    """
    action_id: str = Field(description="Unique action tracking ID")
    recovery_id: str = Field(description="Target recovery plan ID")
    option_id: str = Field(description="Chosen alternative option ID")
    user_id: str = Field(description="User initiating the approval decision")
    decision: BookingApprovalStatus = Field(
        description="APPROVED_BY_USER or REJECTED_BY_USER",
    )
    user_notes: Optional[str] = Field(default=None, description="Optional comments or constraints from user")
    action_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class UserApprovalActionResponse(Model):
    """
    Audit response confirming receipt of user decision.
    Ensures no auto-booking occurs without explicit authorization.
    """
    action_id: str = Field(description="Correlating action ID")
    recovery_id: str = Field(description="Recovery plan ID")
    option_id: str = Field(description="Option ID")
    approval_status: BookingApprovalStatus = Field(description="New approval state recorded in database")
    is_booking_authorized: bool = Field(
        default=False,
        description="True ONLY if user explicitly approved and conditions hold",
    )
    booking_instructions: str = Field(
        description="Safe next steps: direct booking links or operator contact details",
    )
    message: str = Field(description="Status confirmation message")
