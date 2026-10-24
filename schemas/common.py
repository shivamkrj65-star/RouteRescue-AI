"""Common enums and status models for RouteRescue AI."""

from enum import Enum


class TransportMode(str, Enum):
    """Supported multimodal transport modes."""
    TRAIN = "TRAIN"
    BUS = "BUS"
    CAB = "CAB"
    ROAD = "ROAD"
    FLIGHT = "FLIGHT"
    METRO = "METRO"


class SeatAvailabilityStatus(str, Enum):
    """Real-time / synthetic seat availability state."""
    AVAILABLE = "AVAILABLE"
    FEW_SEATS = "FEW_SEATS"
    RAC = "RAC"              # Reservation Against Cancellation (Indian Railways)
    WAITLISTED = "WAITLISTED"
    ON_DEMAND = "ON_DEMAND"   # Cabs / rideshare
    SOLD_OUT = "SOLD_OUT"


class BookingStatus(str, Enum):
    """Lifecycle status for a passenger booking or recovery approval."""
    CONFIRMED = "CONFIRMED"
    RAC = "RAC"
    WAITLISTED = "WAITLISTED"
    DELAYED = "DELAYED"
    CANCELLED = "CANCELLED"
    DROPPED_CHART_PREPARED = "DROPPED_CHART_PREPARED"
    CANCELLED_BY_DISRUPTION = "CANCELLED_BY_DISRUPTION"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED_BY_USER = "APPROVED_BY_USER"
    REJECTED_BY_USER = "REJECTED_BY_USER"
    REFUND_INITIATED = "REFUND_INITIATED"
    COMPLETED = "COMPLETED"


class DisruptionSeverity(str, Enum):
    """Impact level of a detected disruption."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class DisruptionType(str, Enum):
    """Root cause categories for travel disruptions."""
    FOG_DELAY = "FOG_DELAY"
    TRACK_MAINTENANCE = "TRACK_MAINTENANCE"
    LOCOMOTIVE_FAILURE = "LOCOMOTIVE_FAILURE"
    SIGNAL_FAILURE = "SIGNAL_FAILURE"
    HIGHWAY_CONGESTION = "HIGHWAY_CONGESTION"
    ROAD_ACCIDENT = "ROAD_ACCIDENT"
    AIRPORT_ATC = "AIRPORT_ATC"
    WEATHER = "WEATHER"
    STRIKE = "STRIKE"


class RecoveryStatus(str, Enum):
    """Current progression of an automated recovery workflow."""
    DETECTED = "DETECTED"
    SEARCHING_ALTERNATIVES = "SEARCHING_ALTERNATIVES"
    PROPOSED = "PROPOSED"
    AWAITING_USER_APPROVAL = "AWAITING_USER_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    RESOLVED = "RESOLVED"
