"""Disruption event models for RouteRescue AI."""

from datetime import datetime, timezone
from typing import List, Optional
from uagents import Field, Model

from routerescue.schemas.common import (
    DataVerificationStatus,
    DisruptionSeverity,
    DisruptionType,
    TransportMode,
)


class DisruptionEvent(Model):
    """Structured travel disruption event detected across rail, air, or road networks."""
    event_id: str = Field(description="Unique identifier of the disruption event")
    mode: TransportMode = Field(description="Primary transport mode affected")
    disruption_type: DisruptionType = Field(description="Nature of the disruption")
    severity: DisruptionSeverity = Field(description="Severity classification")
    source_reference: str = Field(description="External incident code or reference ID")
    operator: str = Field(description="Transport operating company affected")
    affected_origin: str = Field(description="Origin station/stop or code")
    affected_destination: str = Field(description="Destination station/stop or code")
    affected_stations: List[str] = Field(
        default_factory=list,
        description="List of impacted intermediate or corridor stations",
    )
    delay_minutes: int = Field(default=0, ge=0, description="Estimated delay in minutes")
    is_cancelled: bool = Field(default=False, description="Whether the service is fully cancelled")
    description: str = Field(description="Human-readable summary of the disruption")
    verification_status: DataVerificationStatus = Field(
        default=DataVerificationStatus.SIMULATED_ESTIMATE,
        description="Authenticity flag: verified live feed vs simulated incident",
    )
    reported_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when disruption was reported/detected",
    )
    valid_until: Optional[datetime] = Field(
        default=None,
        description="Estimated resolution or expiration timestamp",
    )
