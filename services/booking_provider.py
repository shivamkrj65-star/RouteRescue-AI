"""Simulated booking-status provider for RouteRescue AI.

Simulates live transit APIs (IRCTC, Zingbus, Uber, State Roadways) supporting:
- Confirmed (CONFIRMED)
- RAC (RAC)
- Waitlisted (WAITLISTED)
- Delayed (DELAYED)
- Cancelled (CANCELLED)
- Dropped after chart preparation (DROPPED_CHART_PREPARED)

Maintains real-time status overrides, simulation injection hooks, and PNR position tracking.
"""

from datetime import datetime
from typing import Any, Dict, Optional, Union
from pydantic import BaseModel, ConfigDict, Field

from config.settings import IST
from schemas.agent_messages import DisruptionInjectionRequest
from schemas.common import BookingStatus
from schemas.disruption import DisruptionInjectionPayload
from schemas.travel import UserJourney


class SimulatedBookingStatus(BaseModel):
    """Detailed booking and operational status representation for a monitored journey."""
    model_config = ConfigDict(use_enum_values=True)

    journey_id: str
    booking_reference: str
    service_id: str
    status: BookingStatus = Field(description="Operational status e.g. CONFIRMED, DELAYED, CANCELLED")
    delay_minutes: int = Field(default=0, description="Service delay in minutes")
    pnr_position: Optional[str] = Field(default=None, description="Current queue/coach position e.g. 'WL 5', 'RAC 2'")
    chart_prepared: bool = Field(default=False, description="Whether reservation chart has been prepared")
    reason: str = Field(default="Normal operations", description="Operational explanation or disruption cause")
    last_updated: datetime = Field(default_factory=lambda: datetime.now(IST))


class SimulatedBookingProvider:
    """Provider for simulated live booking and transit schedule statuses."""

    def __init__(self):
        # In-memory dictionary of simulated journey overrides: journey_id -> SimulatedBookingStatus
        self._overrides: Dict[str, SimulatedBookingStatus] = {}

    def get_status(self, journey: UserJourney) -> SimulatedBookingStatus:
        """Retrieves current simulated booking status for a passenger journey."""
        if journey.journey_id in self._overrides:
            return self._overrides[journey.journey_id]

        # Default fallback: mirror journey's existing SQLite status or CONFIRMED
        status = journey.booking_status
        return SimulatedBookingStatus(
            journey_id=journey.journey_id,
            booking_reference=journey.booking_reference,
            service_id=journey.booked_service.service_id,
            status=status,
            delay_minutes=0,
            pnr_position="CNF" if status == BookingStatus.CONFIRMED else None,
            chart_prepared=False,
            reason="Operating normally as scheduled",
            last_updated=datetime.now(IST),
        )

    def set_status(
        self,
        journey_id: str,
        status: BookingStatus | str,
        booking_reference: str = "",
        service_id: str = "",
        delay_minutes: int = 0,
        pnr_position: Optional[str] = None,
        chart_prepared: bool = False,
        reason: str = "Simulated status update",
    ) -> SimulatedBookingStatus:
        """Sets or overrides status for a journey."""
        if isinstance(status, str):
            status = BookingStatus(status)

        sim_status = SimulatedBookingStatus(
            journey_id=journey_id,
            booking_reference=booking_reference or f"PNR-{journey_id}",
            service_id=service_id or "UNKNOWN",
            status=status,
            delay_minutes=delay_minutes,
            pnr_position=pnr_position,
            chart_prepared=chart_prepared,
            reason=reason,
            last_updated=datetime.now(IST),
        )
        self._overrides[journey_id] = sim_status
        return sim_status

    def inject_disruption(
        self,
        payload: Union[DisruptionInjectionPayload, DisruptionInjectionRequest, Any],
    ) -> SimulatedBookingStatus:
        """Injects a demonstration disruption into the provider."""
        return self.set_status(
            journey_id=payload.journey_id,
            status=payload.status,
            delay_minutes=getattr(payload, "delay_minutes", 0),
            pnr_position=getattr(payload, "pnr_position", None),
            chart_prepared=getattr(payload, "chart_prepared", False),
            reason=getattr(payload, "reason", "Injected disruption"),
        )

    def clear_override(self, journey_id: str) -> None:
        """Removes the simulated override for a journey."""
        self._overrides.pop(journey_id, None)

    def reset_all(self) -> None:
        """Resets all simulated overrides."""
        self._overrides.clear()

    def list_all_statuses(self) -> Dict[str, SimulatedBookingStatus]:
        """Returns all currently active status overrides."""
        return dict(self._overrides)
