"""Intelligent multimodal routing and time-dependent connection graph engine.

Constructs a transit network graph using NetworkX (MultiDiGraph) where edges represent
scheduled rail, bus, and road services with realistic time-dependent scheduling.

Key capabilities:
1. Time-dependent edge traversal and feasible transfer buffer enforcement:
   - >= 20 minutes for same-hub transfers (e.g. at NDLS, JP, UMB, AGC)
   - >= 40 minutes for inter-terminal transfers in the same city (e.g. NDLS -> DEL_ISBT)
2. Rejection of impossible connections (negative or insufficient transfer buffers).
3. Support for direct routes (0 transfers) and multimodal connections (1+ transfers):
   - DIRECT_TRAIN, DIRECT_BUS, DIRECT_CAB
   - CAB + TRAIN, CAB + BUS, TRAIN + BUS, TRAIN + CAB
4. Strict constraint enforcement (budget ceiling, arrival deadlines, earliest departure).
5. Accurate calculation of total fare, actual final arrival, and total elapsed duration.
6. Leg-by-leg itineraries with clear identification of estimated vs verified ticket costs.
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

import networkx as nx

from config.settings import IST
from data.database import DatabaseManager
from data.synthetic_network import DEMO_LOCATIONS
from schemas.agent_messages import TransportSearchAlternative
from schemas.common import SeatAvailabilityStatus, TransportMode
from schemas.travel import Location, TransportService
from services.transport_service import TransportDataService

# Transfer buffer constants
MIN_SAME_HUB_BUFFER_MINUTES = 20
MIN_INTER_TERMINAL_BUFFER_MINUTES = 40
MAX_ACCEPTABLE_LAYOVER_MINUTES = 360  # 6 hours maximum connection wait


@dataclass
class TransferPoint:
    """Represents a transfer intermediate point between two journey legs."""

    hub_code: str
    hub_name: str
    city: str
    transfer_type: str  # "SAME_HUB" or "INTER_TERMINAL"
    layover_minutes: int


@dataclass
class JourneyLeg:
    """Represents a single leg within a travel itinerary."""

    leg_index: int
    service_id: str
    service_number: str
    provider: str
    mode: str
    origin_code: str
    origin_name: str
    origin_city: str
    destination_code: str
    destination_name: str
    destination_city: str
    departure_time: datetime
    arrival_time: datetime
    duration_minutes: int
    distance_km: float
    fare_inr: float
    seat_availability: str
    available_seats_count: Optional[int] = None
    booking_url: Optional[str] = None
    is_overnight: bool = False
    is_estimated_cost: bool = False


@dataclass
class MultimodalItinerary:
    """Complete direct or multimodal travel itinerary composed of one or more legs."""

    itinerary_id: str
    legs: List[JourneyLeg]
    transfers: List[TransferPoint]
    transfers_count: int
    journey_pattern: str  # e.g. DIRECT_TRAIN, CAB+TRAIN, CAB+BUS, TRAIN+BUS
    origin_code: str
    origin_name: str
    origin_city: str
    destination_code: str
    destination_name: str
    destination_city: str
    departure_time: datetime
    arrival_time: datetime
    total_duration_minutes: int
    total_fare_inr: float
    has_estimated_costs: bool
    seat_availability: str
    available_seats_count: Optional[int]
    legs_summary: str
    tradeoffs: str
    is_overnight: bool
    data_label: str = "DEMONSTRATION SYNTHETIC DATASET (Fetch-A-Thon 3.0)"

    def to_alternative(self, rank: int = 1) -> TransportSearchAlternative:
        """Converts itinerary into a standardized uAgents TransportSearchAlternative."""
        service_ids = " + ".join(leg.service_id for leg in self.legs)
        service_nums = " -> ".join(leg.service_number for leg in self.legs)
        providers_list = list(dict.fromkeys(leg.provider for leg in self.legs))
        providers = " + ".join(providers_list)

        total_distance = round(sum(leg.distance_km for leg in self.legs), 1)

        # Primary booking url if single leg or first scheduled leg
        booking_url = self.legs[0].booking_url if len(self.legs) == 1 else None

        return TransportSearchAlternative(
            alternative_id=self.itinerary_id,
            rank=rank,
            service_id=service_ids,
            service_number=service_nums,
            provider=providers,
            mode=self.journey_pattern,
            origin_code=self.origin_code,
            origin_name=self.origin_name,
            destination_code=self.destination_code,
            destination_name=self.destination_name,
            departure_time=self.departure_time.isoformat(),
            arrival_time=self.arrival_time.isoformat(),
            duration_minutes=self.total_duration_minutes,
            distance_km=total_distance,
            fare_inr=round(self.total_fare_inr, 2),
            seat_availability=self.seat_availability,
            available_seats_count=self.available_seats_count,
            booking_url=booking_url,
            is_overnight=self.is_overnight,
            transfers_count=self.transfers_count,
            journey_pattern=self.journey_pattern,
            legs_summary=self.legs_summary,
            has_estimated_costs=self.has_estimated_costs,
            tradeoffs=self.tradeoffs,
            data_label=self.data_label,
        )


class MultimodalRouter:
    """Time-dependent routing engine using NetworkX MultiDiGraph for multimodal journeys."""

    def __init__(self, db: Optional[DatabaseManager] = None):
        self.db = db or DatabaseManager()
        self.transport_service = TransportDataService(db=self.db)
        self.graph = nx.MultiDiGraph()
        self._build_graph()

    def _build_graph(self) -> None:
        """Loads transit hubs and synthetic transport services into the NetworkX MultiDiGraph."""
        self.graph.clear()

        # Add all transit hubs as nodes
        locations = self.db.get_all_locations()
        for loc in locations:
            self.graph.add_node(
                loc.code,
                name=loc.name,
                city=loc.city,
                state=loc.state,
                location_type=loc.location_type,
                latitude=loc.latitude,
                longitude=loc.longitude,
            )

        # Add all transport services as directed edges
        services = self.db.get_all_services()
        for svc in services:
            self._add_service_edge(svc)

    def _add_service_edge(self, svc: TransportService) -> None:
        """Adds a transport service as a directed edge in the multigraph."""
        mode_val = svc.mode.value if hasattr(svc.mode, "value") else str(svc.mode)
        status_val = svc.seat_availability.value if hasattr(svc.seat_availability, "value") else str(svc.seat_availability)

        # On-demand cabs have estimated fares
        is_estimated = (mode_val == "cab") or (status_val == "ON_DEMAND")

        self.graph.add_edge(
            svc.origin.code,
            svc.destination.code,
            key=svc.service_id,
            service_id=svc.service_id,
            service_number=svc.service_number,
            provider=svc.provider,
            mode=mode_val,
            origin_code=svc.origin.code,
            origin_name=svc.origin.name,
            origin_city=svc.origin.city,
            destination_code=svc.destination.code,
            destination_name=svc.destination.name,
            destination_city=svc.destination.city,
            departure_time=svc.departure_time,
            arrival_time=svc.arrival_time,
            duration_minutes=svc.duration_minutes,
            distance_km=svc.distance_km,
            fare_inr=svc.fare_inr,
            seat_availability=status_val,
            available_seats_count=svc.available_seats_count,
            booking_url=svc.booking_url,
            is_overnight=svc.is_overnight,
            is_estimated_cost=is_estimated,
        )

    def reload_graph(self) -> None:
        """Refreshes the graph from the latest database state."""
        self._build_graph()

    @staticmethod
    def is_transfer_feasible(
        leg1: JourneyLeg,
        leg2: JourneyLeg,
        max_layover_minutes: int = MAX_ACCEPTABLE_LAYOVER_MINUTES,
    ) -> Tuple[bool, int, str]:
        """Validates if two consecutive legs form a realistic, feasible transfer.

        Returns (is_feasible, layover_minutes, reason).
        Transfer buffer rules:
        - Same hub (e.g. NDLS -> NDLS): min 20 min
        - Inter-terminal in same city (e.g. NDLS -> DEL_ISBT): min 40 min
        - Different cities: not a direct transfer without transit leg
        """
        # 1. Geographic feasibility
        if leg1.destination_code == leg2.origin_code:
            transfer_type = "SAME_HUB"
            min_buffer = MIN_SAME_HUB_BUFFER_MINUTES
        elif leg1.destination_city.lower() == leg2.origin_city.lower():
            transfer_type = "INTER_TERMINAL"
            min_buffer = MIN_INTER_TERMINAL_BUFFER_MINUTES
        else:
            return (
                False,
                0,
                f"Incompatible transfer hubs in different cities ({leg1.destination_city} vs {leg2.origin_city})",
            )

        # 2. Time-dependent schedule feasibility
        layover_seconds = (leg2.departure_time - leg1.arrival_time).total_seconds()
        layover_minutes = int(layover_seconds // 60)

        if layover_minutes < min_buffer:
            return (
                False,
                layover_minutes,
                f"Impossible connection: layover ({layover_minutes}m) is less than required {transfer_type.lower()} buffer ({min_buffer}m)",
            )

        if layover_minutes > max_layover_minutes:
            return (
                False,
                layover_minutes,
                f"Excessive layover: {layover_minutes}m exceeds maximum allowed {max_layover_minutes}m",
            )

        return True, layover_minutes, f"Feasible {transfer_type.lower()} transfer ({layover_minutes}m layover)"

    def _edge_to_journey_leg(self, edge_data: Dict[str, Any], leg_index: int = 1) -> JourneyLeg:
        """Converts graph edge attributes to a JourneyLeg."""
        return JourneyLeg(
            leg_index=leg_index,
            service_id=edge_data["service_id"],
            service_number=edge_data["service_number"],
            provider=edge_data["provider"],
            mode=edge_data["mode"],
            origin_code=edge_data["origin_code"],
            origin_name=edge_data["origin_name"],
            origin_city=edge_data["origin_city"],
            destination_code=edge_data["destination_code"],
            destination_name=edge_data["destination_name"],
            destination_city=edge_data["destination_city"],
            departure_time=edge_data["departure_time"],
            arrival_time=edge_data["arrival_time"],
            duration_minutes=edge_data["duration_minutes"],
            distance_km=edge_data["distance_km"],
            fare_inr=edge_data["fare_inr"],
            seat_availability=edge_data["seat_availability"],
            available_seats_count=edge_data.get("available_seats_count"),
            booking_url=edge_data.get("booking_url"),
            is_overnight=edge_data.get("is_overnight", False),
            is_estimated_cost=edge_data.get("is_estimated_cost", False),
        )

    def _determine_bottleneck_availability(
        self, statuses: List[str]
    ) -> Tuple[str, Optional[int]]:
        """Determines the worst-case seat availability across legs."""
        priority = {
            "SOLD_OUT": 0,
            "WAITLISTED": 1,
            "RAC": 2,
            "FEW_SEATS": 3,
            "ON_DEMAND": 4,
            "AVAILABLE": 5,
        }
        sorted_statuses = sorted(statuses, key=lambda s: priority.get(s, 0))
        worst_status = sorted_statuses[0] if sorted_statuses else "AVAILABLE"
        return worst_status

    def _create_direct_itinerary(self, leg: JourneyLeg) -> MultimodalItinerary:
        """Constructs a 0-transfer direct itinerary."""
        pattern = f"DIRECT_{leg.mode.upper()}"
        summary = (
            f"Direct {leg.mode.title()}: {leg.service_number} ({leg.provider}) "
            f"from {leg.origin_name} to {leg.destination_name} "
            f"[{leg.departure_time.strftime('%H:%M')} - {leg.arrival_time.strftime('%H:%M')}], "
            f"Fare: Rs. {leg.fare_inr:.0f}"
        )

        cost_note = "Estimated cab fare" if leg.is_estimated_cost else "Verified scheduled ticket fare"
        tradeoffs = f"{pattern} point-to-point journey ({cost_note}). No intermediate transfers."

        return MultimodalItinerary(
            itinerary_id=f"ITIN-{leg.service_id}",
            legs=[leg],
            transfers=[],
            transfers_count=0,
            journey_pattern=pattern,
            origin_code=leg.origin_code,
            origin_name=leg.origin_name,
            origin_city=leg.origin_city,
            destination_code=leg.destination_code,
            destination_name=leg.destination_name,
            destination_city=leg.destination_city,
            departure_time=leg.departure_time,
            arrival_time=leg.arrival_time,
            total_duration_minutes=leg.duration_minutes,
            total_fare_inr=leg.fare_inr,
            has_estimated_costs=leg.is_estimated_cost,
            seat_availability=leg.seat_availability,
            available_seats_count=leg.available_seats_count,
            legs_summary=summary,
            tradeoffs=tradeoffs,
            is_overnight=leg.is_overnight,
        )

    def _create_multimodal_itinerary(
        self,
        leg1: JourneyLeg,
        leg2: JourneyLeg,
        transfer: TransferPoint,
    ) -> MultimodalItinerary:
        """Constructs a 1-transfer multimodal itinerary with complete metadata."""
        legs = [leg1, leg2]
        pattern = f"{leg1.mode.upper()}+{leg2.mode.upper()}"

        dep_time = leg1.departure_time
        arr_time = leg2.arrival_time
        total_duration = int((arr_time - dep_time).total_seconds() // 60)
        total_fare = round(leg1.fare_inr + leg2.fare_inr, 2)
        has_estimated = leg1.is_estimated_cost or leg2.is_estimated_cost
        is_overnight = arr_time.date() > dep_time.date()

        bottleneck_status = self._determine_bottleneck_availability(
            [leg1.seat_availability, leg2.seat_availability]
        )

        seat_counts = [
            leg.available_seats_count
            for leg in legs
            if leg.available_seats_count is not None
        ]
        min_seats = min(seat_counts) if seat_counts else None

        transfer_desc = (
            f"Transfer at {transfer.hub_name} ({transfer.layover_minutes}m buffer, {transfer.transfer_type.lower()})"
        )
        summary = (
            f"Leg 1: [{leg1.mode.title()}] {leg1.service_number} ({leg1.origin_name} {leg1.departure_time.strftime('%H:%M')} -> "
            f"{leg1.destination_name} {leg1.arrival_time.strftime('%H:%M')}, Rs. {leg1.fare_inr:.0f}) | "
            f"{transfer_desc} | "
            f"Leg 2: [{leg2.mode.title()}] {leg2.service_number} ({leg2.origin_name} {leg2.departure_time.strftime('%H:%M')} -> "
            f"{leg2.destination_name} {leg2.arrival_time.strftime('%H:%M')}, Rs. {leg2.fare_inr:.0f}) | "
            f"Total: Rs. {total_fare:.0f}, Arrives {arr_time.strftime('%H:%M')}"
        )

        cost_disclaimer = "Includes on-demand cab estimate" if has_estimated else "Verified scheduled tickets"
        tradeoffs = (
            f"Multimodal {pattern} route with 1 transfer at {transfer.city} ({transfer.layover_minutes}m layover). "
            f"{cost_disclaimer}. Total transit & transfer time: {total_duration} mins."
        )

        itin_id = f"ITIN-{leg1.service_id}+{leg2.service_id}"

        return MultimodalItinerary(
            itinerary_id=itin_id,
            legs=legs,
            transfers=[transfer],
            transfers_count=1,
            journey_pattern=pattern,
            origin_code=leg1.origin_code,
            origin_name=leg1.origin_name,
            origin_city=leg1.origin_city,
            destination_code=leg2.destination_code,
            destination_name=leg2.destination_name,
            destination_city=leg2.destination_city,
            departure_time=dep_time,
            arrival_time=arr_time,
            total_duration_minutes=total_duration,
            total_fare_inr=total_fare,
            has_estimated_costs=has_estimated,
            seat_availability=bottleneck_status,
            available_seats_count=min_seats,
            legs_summary=summary,
            tradeoffs=tradeoffs,
            is_overnight=is_overnight,
        )

    def find_routes(
        self,
        origin: str,
        destination: str,
        earliest_departure: Optional[str] = None,
        latest_arrival: Optional[str] = None,
        max_budget: Optional[float] = None,
        max_transfers: int = 1,
        allowed_patterns: Optional[List[str]] = None,
    ) -> List[MultimodalItinerary]:
        """Discovers feasible direct and multimodal travel itineraries adhering to all constraints.

        Constraints checked:
        1. Earliest departure cutoff
        2. Latest arrival deadline
        3. Maximum budget ceiling
        4. Maximum transfers permitted (0 = direct only, 1 = 1 transfer)
        5. Time-dependent transfer feasibility (minimum buffers, layover caps)
        6. Seat availability (excludes SOLD_OUT)
        """
        origin_codes = self.transport_service.resolve_location_codes(origin)
        dest_codes = self.transport_service.resolve_location_codes(destination)

        # Parse earliest departure requirement
        req_dep_dt: Optional[datetime] = None
        req_dep_time: Optional[time] = None
        if earliest_departure:
            try:
                req_dep_dt = datetime.fromisoformat(earliest_departure)
            except ValueError:
                for fmt in ("%H:%M:%S", "%H:%M"):
                    try:
                        req_dep_time = datetime.strptime(earliest_departure, fmt).time()
                        break
                    except ValueError:
                        pass

        # Parse latest arrival requirement
        req_arr_dt: Optional[datetime] = None
        req_arr_time: Optional[time] = None
        if latest_arrival:
            try:
                req_arr_dt = datetime.fromisoformat(latest_arrival)
            except ValueError:
                for fmt in ("%H:%M:%S", "%H:%M"):
                    try:
                        req_arr_time = datetime.strptime(latest_arrival, fmt).time()
                        break
                    except ValueError:
                        pass

        feasible_itineraries: List[MultimodalItinerary] = []

        # ---------------------------------------------------------------------
        # 1. Discover Direct Routes (0 Transfers)
        # ---------------------------------------------------------------------
        for u in origin_codes:
            for v in dest_codes:
                if not self.graph.has_edge(u, v):
                    continue

                for key, edge_data in self.graph[u][v].items():
                    leg = self._edge_to_journey_leg(edge_data, leg_index=1)

                    # Availability constraint
                    if leg.seat_availability == "SOLD_OUT":
                        continue

                    # Budget constraint
                    if max_budget is not None and leg.fare_inr > max_budget:
                        continue

                    # Earliest departure constraint
                    if req_dep_dt and leg.departure_time < req_dep_dt:
                        continue
                    elif req_dep_time and not req_dep_dt:
                        if leg.departure_time.time() < req_dep_time:
                            continue

                    # Latest arrival constraint
                    if req_arr_dt and leg.arrival_time > req_arr_dt:
                        continue
                    elif req_arr_time and not req_arr_dt:
                        if (leg.is_overnight or leg.arrival_time.date() > leg.departure_time.date()) and req_arr_time < leg.departure_time.time():
                            deadline_dt = datetime.combine(
                                leg.arrival_time.date(), req_arr_time, tzinfo=leg.arrival_time.tzinfo
                            )
                        else:
                            deadline_dt = datetime.combine(
                                leg.departure_time.date(), req_arr_time, tzinfo=leg.arrival_time.tzinfo
                            )
                        if leg.arrival_time > deadline_dt or leg.departure_time >= deadline_dt:
                            continue

                    itin = self._create_direct_itinerary(leg)
                    if allowed_patterns and itin.journey_pattern not in allowed_patterns:
                        continue

                    feasible_itineraries.append(itin)

        # ---------------------------------------------------------------------
        # 2. Discover Multimodal Routes (1 Transfer)
        # ---------------------------------------------------------------------
        if max_transfers >= 1:
            # Candidate intermediate hubs
            all_nodes = set(self.graph.nodes)
            candidate_intermediates = all_nodes - set(origin_codes) - set(dest_codes)

            for u in origin_codes:
                for mid in candidate_intermediates:
                    if not self.graph.has_edge(u, mid):
                        continue

                    mid_city = self.graph.nodes[mid].get("city")

                    # Connect mid to destination hubs (same hub or same city hubs)
                    possible_transfer_starts: List[str] = [mid]
                    # Check other terminals in the same city for inter-terminal transfers
                    for other_hub in self.graph.nodes:
                        if (
                            other_hub != mid
                            and other_hub not in origin_codes
                            and self.graph.nodes[other_hub].get("city") == mid_city
                        ):
                            possible_transfer_starts.append(other_hub)

                    for start_mid in possible_transfer_starts:
                        for v in dest_codes:
                            if not self.graph.has_edge(start_mid, v):
                                continue

                            # Evaluate all combinations of Leg 1 (u -> mid) and Leg 2 (start_mid -> v)
                            for key1, edge1 in self.graph[u][mid].items():
                                leg1 = self._edge_to_journey_leg(edge1, leg_index=1)
                                if leg1.seat_availability == "SOLD_OUT":
                                    continue

                                # Check leg 1 departure constraint early
                                if req_dep_dt and leg1.departure_time < req_dep_dt:
                                    continue
                                elif req_dep_time and not req_dep_dt:
                                    if leg1.departure_time.time() < req_dep_time:
                                        continue

                                for key2, edge2 in self.graph[start_mid][v].items():
                                    leg2 = self._edge_to_journey_leg(edge2, leg_index=2)
                                    if leg2.seat_availability == "SOLD_OUT":
                                        continue

                                    # Validate time-dependent transfer feasibility
                                    is_feasible, layover_m, reason = self.is_transfer_feasible(leg1, leg2)
                                    if not is_feasible:
                                        continue

                                    total_fare = leg1.fare_inr + leg2.fare_inr
                                    if max_budget is not None and total_fare > max_budget:
                                        continue

                                    final_arr = leg2.arrival_time
                                    if req_arr_dt and final_arr > req_arr_dt:
                                        continue
                                    elif req_arr_time and not req_arr_dt:
                                        if final_arr.date() > leg1.departure_time.date() and req_arr_time < leg1.departure_time.time():
                                            deadline_dt = datetime.combine(
                                                final_arr.date(), req_arr_time, tzinfo=final_arr.tzinfo
                                            )
                                        else:
                                            deadline_dt = datetime.combine(
                                                leg1.departure_time.date(), req_arr_time, tzinfo=final_arr.tzinfo
                                            )
                                        if final_arr > deadline_dt or leg1.departure_time >= deadline_dt:
                                            continue

                                    transfer_type = "SAME_HUB" if mid == start_mid else "INTER_TERMINAL"
                                    transfer_hub_name = (
                                        leg1.destination_name
                                        if mid == start_mid
                                        else f"{leg1.destination_name} -> {leg2.origin_name}"
                                    )

                                    transfer = TransferPoint(
                                        hub_code=mid if mid == start_mid else f"{mid}+{start_mid}",
                                        hub_name=transfer_hub_name,
                                        city=mid_city or leg1.destination_city,
                                        transfer_type=transfer_type,
                                        layover_minutes=layover_m,
                                    )

                                    itin = self._create_multimodal_itinerary(leg1, leg2, transfer)
                                    if allowed_patterns and itin.journey_pattern not in allowed_patterns:
                                        continue

                                    feasible_itineraries.append(itin)

        return feasible_itineraries
