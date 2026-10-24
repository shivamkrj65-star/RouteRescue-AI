"""Agent-specific modal search logic, kept strictly separated from agent communication code.

Provides specialized search engines for:
1. RailSearchService (Trains, Shatabdi, Vande Bharat, Rajdhani, Sleepers)
2. BusSearchService (Intercity Volvo, Sleeper coaches, Electric buses)
3. CabRoadSearchService (Uber Intercity, BluSmart, Savaari, transit connectors)
"""

import time as _pytime
from datetime import date, datetime, time
from typing import List, Optional

from config.settings import IST
from data.database import DatabaseManager
from schemas.agent_messages import (
    TransportSearchAlternative,
    TransportSearchQuery,
    TransportSearchResult,
)
from schemas.common import SeatAvailabilityStatus, TransportMode
from schemas.travel import TransportService
from services.transport_service import TransportDataService


class BaseModalSearcher:
    """Base class for mode-specific search logic."""

    def __init__(self, db: Optional[DatabaseManager] = None):
        self.db = db or DatabaseManager()
        self.transport_service = TransportDataService(db=self.db)

    def parse_time(self, time_str: Optional[str]) -> Optional[time]:
        """Safely parses an ISO time string HH:MM or HH:MM:SS."""
        if not time_str:
            return None
        try:
            return time.fromisoformat(time_str)
        except (ValueError, TypeError):
            return None

    def parse_date(self, date_str: Optional[str]) -> Optional[date]:
        """Safely parses an ISO date string YYYY-MM-DD."""
        if not date_str:
            return None
        try:
            return date.fromisoformat(date_str)
        except (ValueError, TypeError):
            return None

    def service_to_alternative(self, svc: TransportService, rank: int, tradeoffs: str) -> TransportSearchAlternative:
        """Converts a domain TransportService to a serializable uAgents TransportSearchAlternative."""
        return TransportSearchAlternative(
            alternative_id=f"ALT-{svc.service_id}",
            rank=rank,
            service_id=svc.service_id,
            service_number=svc.service_number,
            provider=svc.provider,
            mode=svc.mode.value,
            origin_code=svc.origin.code,
            origin_name=svc.origin.name,
            destination_code=svc.destination.code,
            destination_name=svc.destination.name,
            departure_time=svc.departure_time.isoformat(),
            arrival_time=svc.arrival_time.isoformat(),
            duration_minutes=svc.duration_minutes,
            distance_km=svc.distance_km,
            fare_inr=svc.fare_inr,
            seat_availability=svc.seat_availability.value,
            available_seats_count=svc.available_seats_count,
            booking_url=svc.booking_url,
            is_overnight=svc.is_overnight,
            tradeoffs=tradeoffs,
            data_label=svc.data_label,
        )


class RailSearchService(BaseModalSearcher):
    """Specialized search engine for rail journeys (Indian Railways / IRCTC)."""

    def search_rail(
        self,
        query: TransportSearchQuery,
        agent_name: str,
        agent_address: str,
    ) -> TransportSearchResult:
        """Queries and filters alternative train services."""
        start_time = _pytime.perf_counter()

        try:
            origin_codes = self.transport_service.resolve_location_codes(query.origin)
            dest_codes = self.transport_service.resolve_location_codes(query.destination)

            earliest_dep = self.parse_time(query.earliest_departure)
            latest_arr = self.parse_time(query.latest_arrival)
            travel_d = self.parse_date(query.travel_date)

            services = self.db.query_services(
                origin_codes=origin_codes,
                destination_codes=dest_codes,
                mode=TransportMode.TRAIN,
                max_fare_inr=query.max_budget_inr,
                available_only=query.require_available_seats,
            )

            filtered: List[TransportService] = []
            for s in services:
                if travel_d and s.departure_time.astimezone(IST).date() != travel_d:
                    continue
                if earliest_dep and s.departure_time.astimezone(IST).time() < earliest_dep:
                    continue
                if latest_arr and not s.is_overnight and s.arrival_time.astimezone(IST).time() > latest_arr:
                    continue
                if query.require_available_seats and s.available_seats_count is not None:
                    if s.available_seats_count < query.min_seats:
                        continue
                filtered.append(s)

            # Sort by duration, then fare
            filtered.sort(key=lambda x: (x.duration_minutes, x.fare_inr))

            alternatives: List[TransportSearchAlternative] = []
            for idx, svc in enumerate(filtered, start=1):
                hours = svc.duration_minutes // 60
                mins = svc.duration_minutes % 60
                time_str = f"{hours}h {mins}m" if hours > 0 else f"{mins}m"

                if "Vande Bharat" in svc.service_number or "Shatabdi" in svc.service_number:
                    tradeoffs = f"Premium express train ({time_str}), executive AC chair car, scheduled meals included."
                elif svc.is_overnight:
                    tradeoffs = f"Overnight sleeper train ({time_str}), comfortable berths, early morning arrival."
                else:
                    tradeoffs = f"Budget superfast train ({time_str}), economical fare of INR {svc.fare_inr:.0f}."

                alternatives.append(self.service_to_alternative(svc, idx, tradeoffs))

            exec_time = (_pytime.perf_counter() - start_time) * 1000

            return TransportSearchResult(
                request_id=query.request_id,
                agent_name=agent_name,
                agent_address=agent_address,
                mode="TRAIN",
                success=True,
                total_found=len(alternatives),
                results=alternatives,
                execution_time_ms=round(exec_time, 2),
            )

        except Exception as exc:
            exec_time = (_pytime.perf_counter() - start_time) * 1000
            return TransportSearchResult(
                request_id=query.request_id,
                agent_name=agent_name,
                agent_address=agent_address,
                mode="TRAIN",
                success=False,
                total_found=0,
                results=[],
                error_message=f"Rail search exception: {str(exc)}",
                execution_time_ms=round(exec_time, 2),
            )


class BusSearchService(BaseModalSearcher):
    """Specialized search engine for intercity bus and coach services."""

    def search_bus(
        self,
        query: TransportSearchQuery,
        agent_name: str,
        agent_address: str,
    ) -> TransportSearchResult:
        """Queries and filters alternative intercity bus services."""
        start_time = _pytime.perf_counter()

        try:
            origin_codes = self.transport_service.resolve_location_codes(query.origin)
            dest_codes = self.transport_service.resolve_location_codes(query.destination)

            earliest_dep = self.parse_time(query.earliest_departure)
            latest_arr = self.parse_time(query.latest_arrival)
            travel_d = self.parse_date(query.travel_date)

            services = self.db.query_services(
                origin_codes=origin_codes,
                destination_codes=dest_codes,
                mode=TransportMode.BUS,
                max_fare_inr=query.max_budget_inr,
                available_only=query.require_available_seats,
            )

            filtered: List[TransportService] = []
            for s in services:
                if travel_d and s.departure_time.astimezone(IST).date() != travel_d:
                    continue
                if earliest_dep and s.departure_time.astimezone(IST).time() < earliest_dep:
                    continue
                if latest_arr and not s.is_overnight and s.arrival_time.astimezone(IST).time() > latest_arr:
                    continue
                if query.require_available_seats and s.available_seats_count is not None:
                    if s.available_seats_count < query.min_seats:
                        continue
                filtered.append(s)

            filtered.sort(key=lambda x: (x.duration_minutes, x.fare_inr))

            alternatives: List[TransportSearchAlternative] = []
            for idx, svc in enumerate(filtered, start=1):
                hours = svc.duration_minutes // 60
                mins = svc.duration_minutes % 60
                time_str = f"{hours}h {mins}m" if hours > 0 else f"{mins}m"

                if svc.is_overnight:
                    tradeoffs = f"Overnight luxury sleeper bus coach ({time_str}), recliner berths, convenient morning arrival."
                elif "Electric" in svc.provider or "NueGo" in svc.provider:
                    tradeoffs = f"Zero-emission green electric bus ({time_str}), silent cabin, frequent departures."
                else:
                    tradeoffs = f"Direct highway AC bus coach ({time_str}), point-to-point transit from ISBT terminal."

                alternatives.append(self.service_to_alternative(svc, idx, tradeoffs))

            exec_time = (_pytime.perf_counter() - start_time) * 1000

            return TransportSearchResult(
                request_id=query.request_id,
                agent_name=agent_name,
                agent_address=agent_address,
                mode="BUS",
                success=True,
                total_found=len(alternatives),
                results=alternatives,
                execution_time_ms=round(exec_time, 2),
            )

        except Exception as exc:
            exec_time = (_pytime.perf_counter() - start_time) * 1000
            return TransportSearchResult(
                request_id=query.request_id,
                agent_name=agent_name,
                agent_address=agent_address,
                mode="BUS",
                success=False,
                total_found=0,
                results=[],
                error_message=f"Bus search exception: {str(exc)}",
                execution_time_ms=round(exec_time, 2),
            )


class CabRoadSearchService(BaseModalSearcher):
    """Specialized search engine for highway cabs, rideshares, and station connectors."""

    def search_cabs(
        self,
        query: TransportSearchQuery,
        agent_name: str,
        agent_address: str,
    ) -> TransportSearchResult:
        """Queries and filters alternative road and cab connections."""
        start_time = _pytime.perf_counter()

        try:
            origin_codes = self.transport_service.resolve_location_codes(query.origin)
            dest_codes = self.transport_service.resolve_location_codes(query.destination)

            earliest_dep = self.parse_time(query.earliest_departure)
            latest_arr = self.parse_time(query.latest_arrival)
            travel_d = self.parse_date(query.travel_date)

            services = self.db.query_services(
                origin_codes=origin_codes,
                destination_codes=dest_codes,
                mode=TransportMode.CAB,
                max_fare_inr=query.max_budget_inr,
                available_only=query.require_available_seats,
            )

            filtered: List[TransportService] = []
            for s in services:
                if travel_d and s.departure_time.astimezone(IST).date() != travel_d:
                    continue
                if earliest_dep and s.departure_time.astimezone(IST).time() < earliest_dep:
                    continue
                if latest_arr and not s.is_overnight and s.arrival_time.astimezone(IST).time() > latest_arr:
                    continue
                filtered.append(s)

            filtered.sort(key=lambda x: (x.duration_minutes, x.fare_inr))

            alternatives: List[TransportSearchAlternative] = []
            for idx, svc in enumerate(filtered, start=1):
                hours = svc.duration_minutes // 60
                mins = svc.duration_minutes % 60
                time_str = f"{hours}h {mins}m" if hours > 0 else f"{mins}m"

                if svc.distance_km > 100:
                    tradeoffs = f"Direct on-demand highway cab ({time_str}), doorstep pickup via expressway, private comfort."
                else:
                    tradeoffs = f"Intra-city rapid cab transfer ({time_str}), connects railway and coach terminals."

                alternatives.append(self.service_to_alternative(svc, idx, tradeoffs))

            exec_time = (_pytime.perf_counter() - start_time) * 1000

            return TransportSearchResult(
                request_id=query.request_id,
                agent_name=agent_name,
                agent_address=agent_address,
                mode="CAB",
                success=True,
                total_found=len(alternatives),
                results=alternatives,
                execution_time_ms=round(exec_time, 2),
            )

        except Exception as exc:
            exec_time = (_pytime.perf_counter() - start_time) * 1000
            return TransportSearchResult(
                request_id=query.request_id,
                agent_name=agent_name,
                agent_address=agent_address,
                mode="CAB",
                success=False,
                total_found=0,
                results=[],
                error_message=f"Cab search exception: {str(exc)}",
                execution_time_ms=round(exec_time, 2),
            )
