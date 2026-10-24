"""Disruption evaluation and deduplication engine for RouteRescue AI.

Evaluates simulated booking status changes to determine:
1. Whether a status change is meaningful.
2. Whether the condition triggers automated recovery:
   - Any cancellation (CANCELLED)
   - Qualifying delay (DELAYED >= threshold_minutes, default 45m)
   - Waitlist dropped after chart preparation (DROPPED_CHART_PREPARED)
   - Waitlist not confirmed after chart preparation (WAITLISTED with chart_prepared=True)
3. Deduplication: Ensures only one automated recovery request is dispatched per disruption event.
"""

from typing import Set, Tuple
from schemas.common import BookingStatus
from services.booking_provider import SimulatedBookingStatus


class DisruptionEvaluator:
    """Evaluates journey status transitions and enforces recovery triggering rules with deduplication."""

    def __init__(self, default_delay_threshold_minutes: int = 45):
        self.default_delay_threshold = default_delay_threshold_minutes
        self._triggered_dedup_keys: Set[str] = set()

    def evaluate_status_change(
        self,
        old_status: BookingStatus,
        new_status: SimulatedBookingStatus,
        delay_threshold_minutes: int = 45,
    ) -> Tuple[bool, bool, str]:
        """
        Evaluates a status transition.

        Returns:
            (is_meaningful_change, triggers_recovery, reason_code)
        """
        curr_val = new_status.status.value if hasattr(new_status.status, "value") else str(new_status.status)
        old_val = old_status.value if hasattr(old_status, "value") else str(old_status)
        threshold = delay_threshold_minutes or self.default_delay_threshold

        # 1. Cancellation Detection
        if curr_val in (BookingStatus.CANCELLED.value, BookingStatus.CANCELLED_BY_DISRUPTION.value):
            return True, True, "SERVICE_CANCELLED"

        # 2. Dropped after Chart Preparation
        if curr_val == BookingStatus.DROPPED_CHART_PREPARED.value:
            return True, True, "DROPPED_AFTER_CHART_PREPARATION"

        # 3. Waitlist Risk when Chart is Prepared
        if curr_val == BookingStatus.WAITLISTED.value and new_status.chart_prepared:
            return True, True, "WAITLIST_NOT_CONFIRMED_AT_CHARTING"

        # 4. Qualifying Delay Detection
        if curr_val == BookingStatus.DELAYED.value and new_status.delay_minutes >= threshold:
            # Bucket delay by 30-min intervals for escalation detection (e.g. 60m vs 120m)
            bucket = (new_status.delay_minutes // 30) * 30
            return True, True, f"QUALIFYING_DELAY_{bucket}M"

        # 5. Non-recovery status transitions (e.g. Waitlisted -> RAC, RAC -> Confirmed)
        if curr_val != old_val:
            return True, False, f"TRANSITION_{old_val}_TO_{curr_val}"

        return False, False, "NO_CHANGE"

    def get_dedup_key(self, journey_id: str, reason_code: str) -> str:
        """Generates a unique deduplication fingerprint."""
        return f"{journey_id}::{reason_code}"

    def is_duplicate(self, journey_id: str, reason_code: str) -> bool:
        """Checks if a recovery request has already been triggered for this event."""
        return self.get_dedup_key(journey_id, reason_code) in self._triggered_dedup_keys

    def mark_triggered(self, journey_id: str, reason_code: str) -> None:
        """Records that an automated recovery request was dispatched for this event."""
        self._triggered_dedup_keys.add(self.get_dedup_key(journey_id, reason_code))

    def reset_dedup(self) -> None:
        """Clears deduplication history (useful in test suites)."""
        self._triggered_dedup_keys.clear()
