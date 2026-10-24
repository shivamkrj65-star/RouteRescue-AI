"""Deterministic recovery scoring and constraint validation engine.

Decoupled pure Python business logic for RouteRescue AI's Recovery Planner:
1. Validates hard constraints (earliest departure, arrival deadline, budget ceiling, max transfers, seat availability).
2. Calculates multi-criteria normalized scores (duration, cost economy, reliability, directness).
3. Ranks candidates deterministically and extracts the top 3 options.
4. Synthesizes a natural-language explanation detailing why the highest-ranked alternative was chosen.
"""

from datetime import datetime, time as dt_time, timedelta
from typing import Any, Dict, List, Optional, Tuple

from schemas.agent_messages import (
    RankedAlternative,
    RecoveryRequest,
    RecoveryResponse,
    ScoringWeights,
    TransportSearchAlternative,
    TransportSearchResult,
)


def parse_datetime_or_time(val: Optional[str]) -> Tuple[Optional[datetime], Optional[dt_time]]:
    """Parse an ISO datetime or HH:MM[:SS] time string into (datetime, time) components."""
    if not val:
        return None, None
    val = val.strip()

    # Try full ISO datetime
    try:
        dt = datetime.fromisoformat(val)
        return dt, dt.time()
    except ValueError:
        pass

    # Try standard time formats
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            t = datetime.strptime(val, fmt).time()
            return None, t
        except ValueError:
            pass

    return None, None


class RecoveryEngine:
    """Deterministic constraint validation and multi-criteria recovery ranking engine."""

    RELIABILITY_SCORES = {
        "AVAILABLE": 100.0,
        "FEW_SEATS": 85.0,
        "ON_DEMAND": 90.0,
        "RAC": 50.0,
        "WAITLISTED": 25.0,
        "SOLD_OUT": 0.0,
    }

    def __init__(
        self,
        default_weights: Optional[ScoringWeights] = None,
        multimodal_router: Optional[Any] = None,
    ):
        self.default_weights = default_weights or ScoringWeights()
        if multimodal_router is None:
            try:
                from services.multimodal_router import MultimodalRouter

                self.multimodal_router = MultimodalRouter()
            except Exception:
                self.multimodal_router = None
        else:
            self.multimodal_router = multimodal_router

    def validate_and_filter(
        self,
        alternatives: List[TransportSearchAlternative],
        request: RecoveryRequest,
    ) -> Tuple[List[TransportSearchAlternative], Dict[str, int]]:
        """Filter out alternatives violating hard user constraints.

        Hard constraints checked:
        1. Earliest departure time (must depart on or after earliest_departure)
        2. Latest acceptable arrival (must arrive on or before latest_acceptable_arrival)
        3. Maximum budget (fare_inr <= max_budget)
        4. Maximum transfers (transfers <= max_transfers; direct routes have 0 transfers)
        5. Seat availability (exclude SOLD_OUT)
        """
        valid_alternatives: List[TransportSearchAlternative] = []
        rejection_reasons: Dict[str, int] = {
            "departed_before_earliest_allowed": 0,
            "arrived_after_latest_deadline": 0,
            "fare_exceeded_maximum_budget": 0,
            "transfers_exceeded_maximum_allowed": 0,
            "seats_sold_out": 0,
        }

        req_dep_dt, req_dep_time = parse_datetime_or_time(request.earliest_departure)
        req_arr_dt, req_arr_time = parse_datetime_or_time(request.latest_acceptable_arrival)

        for alt in alternatives:
            # 1. Seat Availability check
            if alt.seat_availability == "SOLD_OUT":
                rejection_reasons["seats_sold_out"] += 1
                continue

            # 2. Maximum Budget check
            if request.max_budget is not None and alt.fare_inr > request.max_budget:
                rejection_reasons["fare_exceeded_maximum_budget"] += 1
                continue

            # Parse alternative timestamps
            try:
                alt_dep_dt = datetime.fromisoformat(alt.departure_time)
                alt_arr_dt = datetime.fromisoformat(alt.arrival_time)
            except (ValueError, TypeError):
                continue

            # 3. Earliest Departure check
            if req_dep_dt and alt_dep_dt < req_dep_dt:
                rejection_reasons["departed_before_earliest_allowed"] += 1
                continue
            elif req_dep_time and not req_dep_dt:
                if alt_dep_dt.time() < req_dep_time:
                    rejection_reasons["departed_before_earliest_allowed"] += 1
                    continue

            # 4. Latest Acceptable Arrival check
            if req_arr_dt and alt_arr_dt > req_arr_dt:
                rejection_reasons["arrived_after_latest_deadline"] += 1
                continue
            elif req_arr_time and not req_arr_dt:
                # Deadline is anchored to the departure date, unless it is an overnight journey arriving next day
                if (getattr(alt, "is_overnight", False) or alt_arr_dt.date() > alt_dep_dt.date()) and req_arr_time < alt_dep_dt.time():
                    deadline_dt = datetime.combine(alt_arr_dt.date(), req_arr_time, tzinfo=alt_arr_dt.tzinfo)
                else:
                    deadline_dt = datetime.combine(alt_dep_dt.date(), req_arr_time, tzinfo=alt_arr_dt.tzinfo)

                if alt_arr_dt > deadline_dt or alt_dep_dt >= deadline_dt:
                    rejection_reasons["arrived_after_latest_deadline"] += 1
                    continue

            # 5. Transfers check
            transfers = getattr(alt, "transfers_count", 0)
            if transfers > request.max_transfers:
                rejection_reasons["transfers_exceeded_maximum_allowed"] += 1
                continue

            valid_alternatives.append(alt)

        return valid_alternatives, rejection_reasons

    def score_and_rank(
        self,
        valid_alternatives: List[TransportSearchAlternative],
        request: RecoveryRequest,
    ) -> List[RankedAlternative]:
        """Compute deterministic multi-criteria scores and rank alternatives."""
        if not valid_alternatives:
            return []

        weights = request.weights or self.default_weights
        w_time = weights.duration_weight
        w_cost = weights.cost_weight
        w_rel = weights.reliability_weight
        w_trf = weights.transfer_weight

        # Normalization bounds across candidates
        durations = [alt.duration_minutes for alt in valid_alternatives]
        fares = [alt.fare_inr for alt in valid_alternatives]

        min_dur, max_dur = min(durations), max(durations)
        min_fare, max_fare = min(fares), max(fares)

        scored_candidates: List[Tuple[float, Dict[str, float], TransportSearchAlternative]] = []

        for alt in valid_alternatives:
            # 1. Duration Score (0.0 to 100.0, shorter is better)
            if max_dur == min_dur:
                duration_score = 100.0
            else:
                duration_score = 100.0 * (1.0 - (alt.duration_minutes - min_dur) / (max_dur - min_dur + 1e-6))
            duration_score = max(0.0, min(100.0, duration_score))

            # 2. Cost Score (0.0 to 100.0, lower fare is better)
            if request.max_budget and request.max_budget > 0:
                cost_score = 100.0 * max(0.0, 1.0 - (alt.fare_inr / request.max_budget))
            elif max_fare == min_fare:
                cost_score = 100.0
            else:
                cost_score = 100.0 * (1.0 - (alt.fare_inr - min_fare) / (max_fare - min_fare + 1e-6))
            cost_score = max(0.0, min(100.0, cost_score))

            # 3. Reliability Score (0.0 to 100.0)
            reliability_score = self.RELIABILITY_SCORES.get(alt.seat_availability, 60.0)

            # 4. Transfer Score (0 transfers gets 100.0; each transfer incurs a modest penalty)
            transfers = getattr(alt, "transfers_count", 0)
            if transfers == 0:
                transfer_score = 100.0
            else:
                transfer_score = max(0.0, 100.0 - (transfers * 30.0))

            # Composite weighted utility score
            composite = (
                w_time * duration_score
                + w_cost * cost_score
                + w_rel * reliability_score
                + w_trf * transfer_score
            )
            composite = round(composite, 2)

            breakdown = {
                "duration_score": round(duration_score, 1),
                "cost_score": round(cost_score, 1),
                "reliability_score": round(reliability_score, 1),
                "transfer_score": round(transfer_score, 1),
            }

            scored_candidates.append((composite, breakdown, alt))

        # Deterministic sorting:
        # Primary: composite score descending
        # Secondary: duration ascending (faster tie-breaker)
        # Tertiary: fare ascending (cheaper tie-breaker)
        # Quaternary: service_id ascending (reproducibility)
        scored_candidates.sort(
            key=lambda item: (-item[0], item[2].duration_minutes, item[2].fare_inr, item[2].service_id)
        )

        ranked: List[RankedAlternative] = []
        for i, (score, breakdown, alt) in enumerate(scored_candidates, start=1):
            dur_h = alt.duration_minutes // 60
            dur_m = alt.duration_minutes % 60
            dur_str = f"{dur_h}h {dur_m}m" if dur_h > 0 else f"{dur_m}m"
            transfers = getattr(alt, "transfers_count", 0)

            if i == 1:
                transfer_note = f", {transfers} transfer(s)" if transfers > 0 else ", direct"
                reason = (
                    f"Optimal overall recovery: top composite score ({score:.1f}/100), "
                    f"travel time {dur_str}, fare INR {alt.fare_inr:,.0f}, status {alt.seat_availability}{transfer_note}."
                )
            elif transfers > 0:
                pattern = getattr(alt, "journey_pattern", "MULTIMODAL")
                reason = f"Multimodal {pattern} route with {transfers} transfer ({dur_str}, INR {alt.fare_inr:,.0f})."
            elif alt.mode == "TRAIN":
                reason = f"High-capacity rail alternative with direct corridor connection ({dur_str})."
            elif alt.mode == "BUS":
                reason = f"Economical road alternative (INR {alt.fare_inr:,.0f}) with frequent departures."
            else:
                reason = f"Private on-demand road alternative offering point-to-point dispatch flexibility."

            ranked.append(
                RankedAlternative(
                    rank=i,
                    composite_score=score,
                    score_breakdown=breakdown,
                    alternative=alt,
                    selection_reason=reason,
                )
            )

        return ranked

    def generate_best_option_explanation(
        self,
        ranked_options: List[RankedAlternative],
        request: RecoveryRequest,
        rejection_reasons: Dict[str, int],
        total_evaluated: int,
    ) -> str:
        """Synthesize natural-language explanation of recovery evaluation and why #1 was chosen."""
        if not ranked_options:
            active_rejections = [f"{k.replace('_', ' ')} ({v})" for k, v in rejection_reasons.items() if v > 0]
            rejection_summary = ", ".join(active_rejections) if active_rejections else "no matching services"
            budget_str = f" under INR {request.max_budget:,.0f}" if request.max_budget else ""
            arrival_str = f" arriving by {request.latest_acceptable_arrival}" if request.latest_acceptable_arrival else ""
            return (
                f"No travel alternatives from {request.origin} to {request.destination}{budget_str}{arrival_str} "
                f"could satisfy all user constraints. Evaluated {total_evaluated} options; "
                f"rejections occurred due to: {rejection_summary}."
            )

        best = ranked_options[0]
        alt = best.alternative
        dur_h = alt.duration_minutes // 60
        dur_m = alt.duration_minutes % 60
        dur_str = f"{dur_h}h {dur_m}m" if dur_h > 0 else f"{dur_m}m"

        explanation_parts = [
            f"**Recommended Option #1 ({alt.mode}: {alt.provider} - {alt.service_number})** "
            f"was selected as the highest-ranked recovery journey with a composite score of {best.composite_score:.1f}/100."
        ]

        # Key strengths
        strengths = []
        if best.score_breakdown.get("duration_score", 0) >= 80:
            strengths.append(f"rapid transit duration of {dur_str}")
        if best.score_breakdown.get("cost_score", 0) >= 60:
            strengths.append(f"cost-effective fare of INR {alt.fare_inr:,.0f}")
        if alt.seat_availability in ("AVAILABLE", "FEW_SEATS"):
            strengths.append(f"guaranteed seat availability ({alt.seat_availability})")
        elif alt.seat_availability == "ON_DEMAND":
            strengths.append("immediate on-demand dispatch flexibility")

        if strengths:
            explanation_parts.append(f"This journey excels due to its {', '.join(strengths)}.")

        # Multimodal connection summary if applicable
        if getattr(alt, "transfers_count", 0) > 0 and getattr(alt, "legs_summary", None):
            explanation_parts.append(f"Connection itinerary: {alt.legs_summary}.")
        if getattr(alt, "has_estimated_costs", False):
            explanation_parts.append("Note: Journey includes on-demand road legs with estimated fares.")

        # Comparison with Rank 2 and 3 if available
        if len(ranked_options) > 1:
            second = ranked_options[1]
            s_alt = second.alternative
            diff_fare = s_alt.fare_inr - alt.fare_inr
            diff_time = s_alt.duration_minutes - alt.duration_minutes

            comp_notes = []
            if diff_fare < 0:
                comp_notes.append(f"Option #2 ({s_alt.mode} - {s_alt.provider}) saves INR {abs(diff_fare):,.0f} but takes {diff_time:+d} min longer")
            elif diff_fare > 0:
                comp_notes.append(f"Option #2 ({s_alt.mode} - {s_alt.provider}) is available at INR {s_alt.fare_inr:,.0f}")

            if len(ranked_options) > 2:
                third = ranked_options[2]
                t_alt = third.alternative
                comp_notes.append(f"Option #3 ({t_alt.mode} - {t_alt.provider}) provides a secondary backup at INR {t_alt.fare_inr:,.0f}")

            if comp_notes:
                explanation_parts.append(f"Compared to alternatives: {'; '.join(comp_notes)}.")

        return " ".join(explanation_parts)

    def process_recovery(
        self,
        modal_results: Dict[str, TransportSearchResult],
        request: RecoveryRequest,
        planner_address: str,
        execution_time_ms: float = 0.0,
    ) -> RecoveryResponse:
        """End-to-end recovery coordination processing."""
        # 1. Aggregate alternatives from all modal results
        all_alternatives: List[TransportSearchAlternative] = []
        modal_summary: Dict[str, dict] = {}

        for mode, result in modal_results.items():
            modal_summary[mode] = {
                "status": "SUCCESS" if result.success else "FAILED",
                "total_found": result.total_found,
                "agent_name": result.agent_name,
                "agent_address": result.agent_address,
                "execution_time_ms": result.execution_time_ms,
                "error_message": result.error_message,
            }
            if result.success and result.results:
                all_alternatives.extend(result.results)

        # 1b. Discover connections via transit graph (direct or multimodal)
        if self.multimodal_router is not None and (not all_alternatives or request.max_transfers >= 1):
            try:
                multimodal_itineraries = self.multimodal_router.find_routes(
                    origin=request.origin,
                    destination=request.destination,
                    earliest_departure=request.earliest_departure,
                    latest_arrival=request.latest_acceptable_arrival,
                    max_budget=None,
                    max_transfers=request.max_transfers,
                )
                existing_service_ids = {a.service_id for a in all_alternatives}
                for itin in multimodal_itineraries:
                    alt = itin.to_alternative()
                    if alt.service_id not in existing_service_ids:
                        all_alternatives.append(alt)
                        existing_service_ids.add(alt.service_id)
            except Exception:
                pass

        total_evaluated = len(all_alternatives)

        # 2. Enforce hard constraints
        valid_alternatives, rejection_reasons = self.validate_and_filter(all_alternatives, request)
        valid_count = len(valid_alternatives)
        rejected_count = total_evaluated - valid_count

        # 3. Deterministic scoring & ranking
        ranked_all = self.score_and_rank(valid_alternatives, request)
        top_3 = ranked_all[:3]

        # 4. Generate best option explanation
        explanation = self.generate_best_option_explanation(
            ranked_options=top_3,
            request=request,
            rejection_reasons=rejection_reasons,
            total_evaluated=total_evaluated,
        )

        return RecoveryResponse(
            request_id=request.request_id,
            planner_address=planner_address,
            success=True,
            origin=request.origin,
            destination=request.destination,
            total_options_evaluated=total_evaluated,
            valid_options_count=valid_count,
            rejected_options_count=rejected_count,
            rejection_reasons=rejection_reasons,
            top_3_options=top_3,
            best_option_explanation=explanation,
            modal_responses=modal_summary,
            execution_time_ms=execution_time_ms,
        )
