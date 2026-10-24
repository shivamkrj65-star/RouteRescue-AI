"""SQLite database manager for RouteRescue AI.

Manages transit locations, transport services (timetables), disruption alerts,
user journeys, and monitoring event logs.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from config.settings import IST, settings
from schemas.common import (
    BookingStatus,
    DisruptionSeverity,
    DisruptionType,
    SeatAvailabilityStatus,
    TransportMode,
)
from schemas.disruption import DisruptionEvent
from schemas.travel import Location, TransportService, UserJourney


class DatabaseManager:
    """Handles thread-safe SQLite database connectivity, schema creation, and queries."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or settings.db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def get_connection(self) -> sqlite3.Connection:
        """Returns an active SQLite connection configured with foreign key enforcement."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def init_db(self) -> None:
        """Creates all necessary database tables and performance indexes."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # 1. Locations Table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS locations (
                    code TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    city TEXT NOT NULL,
                    state TEXT NOT NULL,
                    latitude REAL NOT NULL,
                    longitude REAL NOT NULL,
                    location_type TEXT NOT NULL
                );
                """
            )

            # 2. Transport Services (Schedules / Inventory)
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS transport_services (
                    service_id TEXT PRIMARY KEY,
                    mode TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    service_number TEXT NOT NULL,
                    origin_code TEXT NOT NULL,
                    destination_code TEXT NOT NULL,
                    departure_time TEXT NOT NULL,
                    arrival_time TEXT NOT NULL,
                    duration_minutes INTEGER NOT NULL,
                    distance_km REAL NOT NULL,
                    fare_inr REAL NOT NULL,
                    seat_availability TEXT NOT NULL,
                    available_seats_count INTEGER,
                    booking_url TEXT,
                    is_overnight INTEGER NOT NULL DEFAULT 0,
                    is_synthetic INTEGER NOT NULL DEFAULT 1,
                    data_label TEXT NOT NULL,
                    FOREIGN KEY (origin_code) REFERENCES locations(code),
                    FOREIGN KEY (destination_code) REFERENCES locations(code)
                );
                """
            )
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_services_od ON transport_services(origin_code, destination_code);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_services_dept ON transport_services(departure_time);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_services_mode ON transport_services(mode);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_services_fare ON transport_services(fare_inr);")

            # 3. Disruption Events Table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS disruptions (
                    event_id TEXT PRIMARY KEY,
                    mode TEXT NOT NULL,
                    disruption_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    source_reference TEXT NOT NULL,
                    operator TEXT NOT NULL,
                    affected_origin TEXT NOT NULL,
                    affected_destination TEXT NOT NULL,
                    affected_stations_json TEXT NOT NULL,
                    delay_minutes INTEGER NOT NULL,
                    is_cancelled INTEGER NOT NULL,
                    headline TEXT NOT NULL,
                    description TEXT NOT NULL,
                    reported_at TEXT NOT NULL,
                    valid_until TEXT,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    is_synthetic INTEGER NOT NULL DEFAULT 1,
                    data_label TEXT NOT NULL
                );
                """
            )
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_disruptions_active ON disruptions(is_active);")

            # 4. User Journeys Table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS user_journeys (
                    journey_id TEXT PRIMARY KEY,
                    passenger_name TEXT NOT NULL,
                    passenger_email TEXT NOT NULL,
                    booked_service_id TEXT NOT NULL,
                    booking_status TEXT NOT NULL,
                    booking_reference TEXT NOT NULL,
                    booked_fare_inr REAL NOT NULL,
                    created_at TEXT NOT NULL,
                    is_synthetic INTEGER NOT NULL DEFAULT 1,
                    FOREIGN KEY (booked_service_id) REFERENCES transport_services(service_id)
                );
                """
            )

            # 5. Monitoring & Recovery Audit Log
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS monitoring_logs (
                    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    details_json TEXT NOT NULL
                );
                """
            )

            conn.commit()

    # -------------------------------------------------------------------------
    # Location Operations
    # -------------------------------------------------------------------------

    def save_location(self, loc: Location) -> None:
        """Inserts or updates a transit hub location."""
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO locations (code, name, city, state, latitude, longitude, location_type)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (loc.code, loc.name, loc.city, loc.state, loc.latitude, loc.longitude, loc.location_type),
            )
            conn.commit()

    def get_location(self, code: str) -> Optional[Location]:
        """Retrieves a single location by code."""
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM locations WHERE code = ?", (code,)).fetchone()
            if not row:
                return None
            return Location(
                code=row["code"],
                name=row["name"],
                city=row["city"],
                state=row["state"],
                latitude=row["latitude"],
                longitude=row["longitude"],
                location_type=row["location_type"],
            )

    def find_locations_by_city(self, city_name: str) -> List[Location]:
        """Returns all stations/stops located in or near the given city."""
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM locations WHERE LOWER(city) = LOWER(?) OR LOWER(name) LIKE LOWER(?)",
                (city_name, f"%{city_name}%"),
            ).fetchall()
            return [
                Location(
                    code=r["code"],
                    name=r["name"],
                    city=r["city"],
                    state=r["state"],
                    latitude=r["latitude"],
                    longitude=r["longitude"],
                    location_type=r["location_type"],
                )
                for r in rows
            ]

    def list_all_locations(self) -> List[Location]:
        """Lists all registered transit hubs."""
        with self.get_connection() as conn:
            rows = conn.execute("SELECT * FROM locations ORDER BY city, name").fetchall()
            return [
                Location(
                    code=r["code"],
                    name=r["name"],
                    city=r["city"],
                    state=r["state"],
                    latitude=r["latitude"],
                    longitude=r["longitude"],
                    location_type=r["location_type"],
                )
                for r in rows
            ]

    # -------------------------------------------------------------------------
    # Transport Service Operations
    # -------------------------------------------------------------------------

    def save_service(self, service: TransportService) -> None:
        """Inserts or updates an individual transport service."""
        self.save_services([service])

    def save_services(self, services: List[TransportService]) -> None:
        """Bulk inserts transport services within a single transaction."""
        if not services:
            return

        records = [
            (
                s.service_id,
                s.mode.value,
                s.provider,
                s.service_number,
                s.origin.code,
                s.destination.code,
                s.departure_time.isoformat(),
                s.arrival_time.isoformat(),
                s.duration_minutes,
                s.distance_km,
                s.fare_inr,
                s.seat_availability.value,
                s.available_seats_count,
                s.booking_url,
                1 if s.is_overnight else 0,
                1 if s.is_synthetic else 0,
                s.data_label,
            )
            for s in services
        ]

        with self.get_connection() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO transport_services (
                    service_id, mode, provider, service_number, origin_code, destination_code,
                    departure_time, arrival_time, duration_minutes, distance_km, fare_inr,
                    seat_availability, available_seats_count, booking_url, is_overnight,
                    is_synthetic, data_label
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                records,
            )
            conn.commit()

    def get_service_by_id(self, service_id: str) -> Optional[TransportService]:
        """Fetches a transport service by ID."""
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM transport_services WHERE service_id = ?", (service_id,)).fetchone()
            if not row:
                return None
            return self._row_to_service(row)

    def query_services(
        self,
        origin_codes: Optional[List[str]] = None,
        destination_codes: Optional[List[str]] = None,
        mode: Optional[TransportMode] = None,
        earliest_departure: Optional[datetime] = None,
        latest_arrival: Optional[datetime] = None,
        max_fare_inr: Optional[float] = None,
        available_only: bool = False,
    ) -> List[TransportService]:
        """Filtered search for transport services."""
        query = "SELECT * FROM transport_services WHERE 1=1"
        params: List[Any] = []

        if origin_codes:
            placeholders = ",".join("?" for _ in origin_codes)
            query += f" AND origin_code IN ({placeholders})"
            params.extend(origin_codes)

        if destination_codes:
            placeholders = ",".join("?" for _ in destination_codes)
            query += f" AND destination_code IN ({placeholders})"
            params.extend(destination_codes)

        if mode:
            query += " AND mode = ?"
            params.append(mode.value)

        if earliest_departure:
            query += " AND departure_time >= ?"
            params.append(earliest_departure.isoformat())

        if latest_arrival:
            query += " AND arrival_time <= ?"
            params.append(latest_arrival.isoformat())

        if max_fare_inr is not None:
            query += " AND fare_inr <= ?"
            params.append(max_fare_inr)

        if available_only:
            query += " AND seat_availability IN ('AVAILABLE', 'FEW_SEATS', 'ON_DEMAND')"

        query += " ORDER BY departure_time ASC"

        with self.get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_service(r) for r in rows if r]

    def _row_to_service(self, row: sqlite3.Row) -> TransportService:
        """Converts an SQLite row to a typed TransportService."""
        orig = self.get_location(row["origin_code"])
        dest = self.get_location(row["destination_code"])
        return TransportService(
            service_id=row["service_id"],
            mode=TransportMode(row["mode"]),
            provider=row["provider"],
            service_number=row["service_number"],
            origin=orig,
            destination=dest,
            departure_time=datetime.fromisoformat(row["departure_time"]),
            arrival_time=datetime.fromisoformat(row["arrival_time"]),
            duration_minutes=row["duration_minutes"],
            distance_km=row["distance_km"],
            fare_inr=row["fare_inr"],
            seat_availability=SeatAvailabilityStatus(row["seat_availability"]),
            available_seats_count=row["available_seats_count"],
            booking_url=row["booking_url"],
            is_overnight=bool(row["is_overnight"]),
            is_synthetic=bool(row["is_synthetic"]),
            data_label=row["data_label"],
        )

    # -------------------------------------------------------------------------
    # Disruption Operations
    # -------------------------------------------------------------------------

    def save_disruption(self, disruption: DisruptionEvent, is_active: bool = True) -> None:
        """Saves a disruption incident."""
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO disruptions (
                    event_id, mode, disruption_type, severity, source_reference, operator,
                    affected_origin, affected_destination, affected_stations_json,
                    delay_minutes, is_cancelled, headline, description,
                    reported_at, valid_until, is_active, is_synthetic, data_label
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    disruption.event_id,
                    disruption.mode.value,
                    disruption.disruption_type.value,
                    disruption.severity.value,
                    disruption.source_reference,
                    disruption.operator,
                    disruption.affected_origin,
                    disruption.affected_destination,
                    json.dumps(disruption.affected_stations),
                    disruption.delay_minutes,
                    1 if disruption.is_cancelled else 0,
                    disruption.headline,
                    disruption.description,
                    disruption.reported_at.isoformat(),
                    disruption.valid_until.isoformat() if disruption.valid_until else None,
                    1 if is_active else 0,
                    1 if disruption.is_synthetic else 0,
                    disruption.data_label,
                ),
            )
            conn.commit()

    def get_active_disruptions(
        self,
        mode: Optional[TransportMode] = None,
        station_or_city: Optional[str] = None,
    ) -> List[DisruptionEvent]:
        """Returns all currently active disruptions."""
        query = "SELECT * FROM disruptions WHERE is_active = 1"
        params: List[Any] = []

        if mode:
            query += " AND mode = ?"
            params.append(mode.value)

        with self.get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            events: List[DisruptionEvent] = []
            for r in rows:
                affected_stations = json.loads(r["affected_stations_json"])
                if station_or_city:
                    target = station_or_city.upper()
                    if (
                        target not in [s.upper() for s in affected_stations]
                        and target != r["affected_origin"].upper()
                        and target != r["affected_destination"].upper()
                    ):
                        continue

                events.append(
                    DisruptionEvent(
                        event_id=r["event_id"],
                        mode=TransportMode(r["mode"]),
                        disruption_type=DisruptionType(r["disruption_type"]),
                        severity=DisruptionSeverity(r["severity"]),
                        source_reference=r["source_reference"],
                        operator=r["operator"],
                        affected_origin=r["affected_origin"],
                        affected_destination=r["affected_destination"],
                        affected_stations=affected_stations,
                        delay_minutes=r["delay_minutes"],
                        is_cancelled=bool(r["is_cancelled"]),
                        headline=r["headline"],
                        description=r["description"],
                        reported_at=datetime.fromisoformat(r["reported_at"]),
                        valid_until=datetime.fromisoformat(r["valid_until"]) if r["valid_until"] else None,
                        is_synthetic=bool(r["is_synthetic"]),
                        data_label=r["data_label"],
                    )
                )
            return events

    # -------------------------------------------------------------------------
    # User Journey Operations
    # -------------------------------------------------------------------------

    def save_user_journey(self, journey: UserJourney) -> None:
        """Stores a passenger booked journey."""
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO user_journeys (
                    journey_id, passenger_name, passenger_email, booked_service_id,
                    booking_status, booking_reference, booked_fare_inr, created_at, is_synthetic
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    journey.journey_id,
                    journey.passenger_name,
                    journey.passenger_email,
                    journey.booked_service.service_id,
                    journey.booking_status.value,
                    journey.booking_reference,
                    journey.booked_fare_inr,
                    journey.created_at.isoformat(),
                    1 if journey.is_synthetic else 0,
                ),
            )
            conn.commit()

    def get_user_journey(self, journey_id: str) -> Optional[UserJourney]:
        """Loads a user journey by journey_id."""
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM user_journeys WHERE journey_id = ?", (journey_id,)).fetchone()
            if not row:
                return None
            service = self.get_service_by_id(row["booked_service_id"])
            if not service:
                return None
            return UserJourney(
                journey_id=row["journey_id"],
                passenger_name=row["passenger_name"],
                passenger_email=row["passenger_email"],
                booked_service=service,
                booking_status=BookingStatus(row["booking_status"]),
                booking_reference=row["booking_reference"],
                booked_fare_inr=row["booked_fare_inr"],
                created_at=datetime.fromisoformat(row["created_at"]),
                is_synthetic=bool(row["is_synthetic"]),
            )

    # -------------------------------------------------------------------------
    # Monitoring Event Log
    # -------------------------------------------------------------------------

    def log_monitoring_event(self, event_type: str, details: Dict[str, Any]) -> None:
        """Logs monitoring actions for recovery auditing."""
        with self.get_connection() as conn:
            conn.execute(
                "INSERT INTO monitoring_logs (timestamp, event_type, details_json) VALUES (?, ?, ?)",
                (datetime.now(IST).isoformat(), event_type, json.dumps(details)),
            )
            conn.commit()
