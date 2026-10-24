"""Common enums and primitive models for RouteRescue AI."""

from enum import Enum


class TransportMode(str, Enum):
    """Supported transportation modes."""
    TRAIN = "TRAIN"
    BUS = "BUS"
    CAB = "CAB"
    FLIGHT = "FLIGHT"
    WALK = "WALK"
    METRO = "METRO"


class DisruptionSeverity(str, Enum):
    """Disruption impact severity."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class DisruptionType(str, Enum):
    """Root cause or category of travel disruption."""
    CANCELLATION = "CANCELLATION"
    DELAY = "DELAY"
    STRIKE = "STRIKE"
    WEATHER = "WEATHER"
    MECHANICAL = "MECHANICAL"
    TRACK_CLOSURE = "TRACK_CLOSURE"
    ROAD_ACCIDENT = "ROAD_ACCIDENT"
    AIRPORT_ATC = "AIRPORT_ATC"


class DataVerificationStatus(str, Enum):
    """
    Integrity tagging to ensure transparent differentiation between
    verified live data and simulated/estimated datasets.
    """
    VERIFIED_LIVE = "VERIFIED_LIVE"
    SIMULATED_ESTIMATE = "SIMULATED_ESTIMATE"
    HISTORICAL_FALLBACK = "HISTORICAL_FALLBACK"


class BookingApprovalStatus(str, Enum):
    """
    Strict human-in-the-loop state machine for booking and recovery execution.
    """
    PENDING_USER_APPROVAL = "PENDING_USER_APPROVAL"
    APPROVED_BY_USER = "APPROVED_BY_USER"
    REJECTED_BY_USER = "REJECTED_BY_USER"
    EXPIRED = "EXPIRED"
    SIMULATED_HELD = "SIMULATED_HELD"


class OptimizationPriority(str, Enum):
    """Objective function weighting for route recovery."""
    FASTEST = "FASTEST"
    CHEAPEST = "CHEAPEST"
    MIN_TRANSFERS = "MIN_TRANSFERS"
    BALANCED = "BALANCED"


class RecoveryStatus(str, Enum):
    """Status of an active travel recovery plan."""
    DETECTED = "DETECTED"
    PLANNING = "PLANNING"
    PROPOSED = "PROPOSED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    RESOLVED = "RESOLVED"
    FAILED = "FAILED"
