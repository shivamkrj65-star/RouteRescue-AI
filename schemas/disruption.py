"""Travel disruption event schema."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

from config.settings import IST
from schemas.common import DisruptionSeverity, DisruptionType, TransportMode


class DisruptionEvent(BaseModel):
    """Structured travel disruption alert across rail, bus, air, or road corridors."""
    event_id: str = Field(description="Unique disruption identifier e.g. DISR-FOG-001")
    mode: TransportMode = Field(description="Transport mode impacted")
    disruption_type: DisruptionType = Field(description="Classification of incident")
    severity: DisruptionSeverity = Field(description="Incident severity level")
    source_reference: str = Field(description="External reference code e.g. NTES-INC-4091")
    operator: str = Field(description="Impacted agency or operator e.g. Northern Railway, NHAI")
    affected_origin: str = Field(description="Origin city or station code")
    affected_destination: str = Field(description="Destination city or station code")
    affected_stations: List[str] = Field(
        default_factory=list,
        description="List of corridor stations or junctions impacted",
    )
    delay_minutes: int = Field(default=0, ge=0, description="Estimated delay in minutes")
    is_cancelled: bool = Field(default=False, description="Whether the scheduled service is cancelled")
    headline: str = Field(description="Brief headline e.g. Dense Fog Warning across Delhi-Agra Yamuna Expressway")
    description: str = Field(description="Detailed explanation of the disruption and operational impact")
    reported_at: datetime = Field(
        default_factory=lambda: datetime.now(IST),
        description="Timezone-aware detection timestamp",
    )
    valid_until: Optional[datetime] = Field(
        default=None,
        description="Estimated resolution timestamp",
    )
    is_synthetic: bool = Field(
        default=True,
        description="Indicates this is demonstration data",
    )
    data_label: str = Field(
        default="DEMONSTRATION SYNTHETIC DATASET (Fetch-A-Thon 3.0)",
        description="Demonstration data transparency label",
    )
