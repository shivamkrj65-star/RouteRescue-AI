"""Transport data service for searching, filtering, and evaluating multimodal travel options."""

import uuid
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Optional

from config.settings import IST
from data.database import DatabaseManager
from schemas.common import (
    SeatAvailabilityStatus,
    TransportMode,
)
from schemas.disruption import DisruptionEvent
from schemas.search import (
    TransportSearchRequest,
    TransportSearchResponse,
    TravelAlternative,
)
from schemas.travel import Location, TransportService


class TransportDataService:
    """Core service for finding available transport journeys across Delhi, Jaipur, Chandigarh, and Agra."""

    def __init__(self, db: Optional[DatabaseManager] = None):
        self.db = db or DatabaseManager()

    def resolve_location_codes(self, city_or_code: str) -> List[str]:
        """
        Resolves station codes matching either an exact location code
        or any transit hub in the specified city.
        """
        raw = city_or_code.strip()
        single_loc = self.db.get_location(raw.upper())
        if single_loc:
            return [single_loc.code]

        city_locs = self.db.find_locations_by_city(raw)
        if city_locs:
            return [loc.code for loc in city_locs]

        # Case-insensitive substring matching fallback
        all_locs = self.db.list_all_locations()
        matched = [
            loc.code
            for loc in all_locs
            if raw.lower() in loc.city.lower()
            or raw.lower() in loc.name.lower()
            or raw.upper() == loc.code.upper()
        ]
        return matched if matched else [raw.upper()]

    def search_transport(self, request: TransportSearchRequest) -> TransportSearchResponse:
        """
        Executes a transport search against the synthetic dataset with origin, destination,
        time, budget, mode, and seat availability filters.
        """
        origin_codes = self.resolve_location_codes(request.origin_city_or_code)
        destination_codes = self.resolve_location_codes(request.destination_city_or_code)

        applied_filters: Dict[str, Any] = {
            "origin_query": request.origin_city_or_code,
            "destination_query": request.destination_city_or_code,
            "resolved_origins": origin_codes,
            "resolved_destinations": destination_codes,
        }

        # Query raw matching services from SQLite
        candidate_services = self.db.query_services(
            origin_codes=origin_codes,
            destination_codes=destination_codes,
            mode=request.mode,
            max_fare_inr=request.max_budget_inr,
            available_only=request.require_available_seats,
        )

        filtered_services: List[TransportService] = []

        for s in candidate_services:
            # 1. Date Filter (if specified)
            if request.travel_date:
                service_date = s.departure_time.astimezone(IST).date()
                if service_date != request.travel_date:
                    continue

            # 2. Earliest Departure Filter (time of day)
            if request.earliest_departure:
                dep_time = s.departure_time.astimezone(IST).time()
                if dep_time < request.earliest_departure:
                    continue

            # 3. Latest Arrival Filter (accounts for overnight journeys)
            if request.latest_arrival:
                arr_time = s.arrival_time.astimezone(IST).time()
                # If non-overnight journey arrives after deadline, exclude
                if not s.is_overnight and arr_time > request.latest_arrival:
                    continue
                # If overnight journey arrives after deadline on next morning, exclude
                if s.is_overnight and arr_time > request.latest_arrival:
                    continue

            # 4. Seat Count Filter
            if request.require_available_seats:
                if s.seat_availability not in (
                    SeatAvailabilityStatus.AVAILABLE,
                    SeatAvailabilityStatus.FEW_SEATS,
                    SeatAvailabilityStatus.ON_DEMAND,
                ):
                    continue
                if s.available_seats_count is not None and s.available_seats_count < request.min_seats:
                    continue

            filtered_services.append(s)

        # Sort results: primary by duration, secondary by fare
        filtered_services.sort(key=lambda x: (x.duration_minutes, x.fare_inr))

        # Build structured TravelAlternative list
        alternatives: List[TravelAlternative] = []
        for idx, svc in enumerate(filtered_services, start=1):
            tradeoffs = self._generate_tradeoff_summary(svc)
            fits_budget = True
            if request.max_budget_inr is not None:
                fits_budget = svc.fare_inr <= request.max_budget_inr

            alternatives.append(
                TravelAlternative(
                    alternative_id=f"ALT-{svc.service_id}",
                    rank=idx,
                    service=svc,
                    total_fare_inr=svc.fare_inr,
                    departure_time=svc.departure_time,
                    arrival_time=svc.arrival_time,
                    duration_minutes=svc.duration_minutes,
                    is_overnight=svc.is_overnight,
                    availability_status=svc.seat_availability,
                    fits_budget=fits_budget,
                    tradeoffs=tradeoffs,
                    booking_url=svc.booking_url,
                    is_synthetic=svc.is_synthetic,
                    data_label=svc.data_label,
                )
            )

        if request.max_budget_inr is not None:
            applied_filters["max_budget_inr"] = request.max_budget_inr
        if request.mode is not None:
            applied_filters["mode"] = request.mode.value
        if request.earliest_departure is not None:
            applied_filters["earliest_departure"] = request.earliest_departure.isoformat()
        if request.latest_arrival is not None:
            applied_filters["latest_arrival"] = request.latest_arrival.isoformat()

        return TransportSearchResponse(
            search_id=request.search_id,
            origin=request.origin_city_or_code,
            destination=request.destination_city_or_code,
            search_timestamp=datetime.now(IST),
            total_found=len(alternatives),
            applied_filters=applied_filters,
            results=alternatives,
        )

    def search_by_params(
        self,
        origin: str,
        destination: str,
        travel_date: Optional[date] = None,
        earliest_departure: Optional[time] = None,
        latest_arrival: Optional[time] = None,
        max_budget_inr: Optional[float] = None,
        mode: Optional[TransportMode] = None,
        require_available_seats: bool = False,
        min_seats: int = 1,
    ) -> TransportSearchResponse:
        """Convenience method to execute transport searches with raw parameters."""
        req = TransportSearchRequest(
            search_id=f"REQ-{uuid.uuid4().hex[:8].upper()}",
            origin_city_or_code=origin,
            destination_city_or_code=destination,
            travel_date=travel_date,
            earliest_departure=earliest_departure,
            latest_arrival=latest_arrival,
            max_budget_inr=max_budget_inr,
            mode=mode,
            require_available_seats=require_available_seats,
            min_seats=min_seats,
        )
        return self.search_transport(req)

    def get_service_details(self, service_id: str) -> Optional[TransportService]:
        """Fetches full specifications for a transport service."""
        return self.db.get_service_by_id(service_id)

    def list_active_disruptions(
        self,
        station_or_city: Optional[str] = None,
        mode: Optional[TransportMode] = None,
    ) -> List[DisruptionEvent]:
        """Retrieves active travel disruption incidents."""
        return self.db.get_active_disruptions(mode=mode, station_or_city=station_or_city)

    def check_service_disruptions(self, service_id: str) -> List[DisruptionEvent]:
        """Checks if a given service is affected by any active disruption."""
        svc = self.db.get_service_by_id(service_id)
        if not svc:
            return []

        active = self.db.get_active_disruptions(mode=svc.mode)
        matching: List[DisruptionEvent] = []
        orig_code = svc.origin.code.upper()
        dest_code = svc.destination.code.upper()

        for d in active:
            aff_orig = d.affected_origin.upper()
            aff_dest = d.affected_destination.upper()
            aff_stations = [s.upper() for s in d.affected_stations]

            if (orig_code == aff_orig and dest_code == aff_dest) or (
                orig_code in aff_stations and dest_code in aff_stations
            ):
                matching.append(d)

        return matching

    def _generate_tradeoff_summary(self, svc: TransportService) -> str:
        """Produces a human-readable tradeoff explanation for alternative options."""
        hours = svc.duration_minutes // 60
        mins = svc.duration_minutes % 60
        time_str = f"{hours}h {mins}m" if hours > 0 else f"{mins}m"

        if svc.mode == TransportMode.TRAIN:
            if "Vande Bharat" in svc.service_number or "Shatabdi" in svc.service_number:
                return f"Fastest rail option ({time_str}), executive AC comfort, scheduled meal options."
            elif svc.is_overnight:
                return f"Overnight sleeper train ({time_str}), saves hotel accommodation, arrives early morning."
            else:
                return f"Budget superfast train ({time_str}), economical fare of INR {svc.fare_inr:.0f}."

        elif svc.mode == TransportMode.BUS:
            if svc.is_overnight:
                return f"Overnight luxury sleeper bus coach ({time_str}), recliner berths, convenient morning arrival."
            elif "Electric" in svc.provider or "NueGo" in svc.provider:
                return f"Zero-emission green electric bus ({time_str}), quiet cabin, frequent departures."
            else:
                return f"Direct highway AC bus coach ({time_str}), point-to-point transit from ISBT."

        elif svc.mode == TransportMode.CAB:
            if svc.distance_km > 100:
                return f"Direct on-demand highway cab ({time_str}), doorstep pickup via expressway, flexible stops."
            else:
                return f"Intra-city rapid cab transfer ({time_str}), connects railway and coach terminals."

        return f"{svc.mode.value} connection ({time_str}) via {svc.provider}."
