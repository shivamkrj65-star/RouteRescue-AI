"""SQLite Database Manager for RouteRescue AI.

Stores stations, synthetic timetables, active disruptions, passenger journeys,
recovery plans, and human-in-the-loop audit logs.
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from routerescue.config import settings
from routerescue.schemas.common import (
    BookingApprovalStatus,
    DataVerificationStatus,
    DisruptionSeverity,
    DisruptionType,
    OptimizationPriority,
    RecoveryStatus,
    TransportMode,
)
from routerescue.schemas.disruption import DisruptionEvent
from routerescue.schemas.messages import (
    RecoveryOption,
    RecoveryPlanResponse,
    UserApprovalActionRequest,
)
from routerescue.schemas.travel import Journey, Location, PassengerProfile, TravelSegment


class DatabaseManager:
    """Encapsulates SQLite database connection and query operations."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or settings.db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def get_connection(self) -> sqlite3.Connection:
        """Returns a configured SQLite connection with foreign keys enabled."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def init_db(self) -> None:
        """Initializes all necessary database tables and indices."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # 1. Locations
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS locations (
                    code TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    city TEXT NOT NULL,
                    latitude REAL NOT NULL,
                    longitude REAL NOT NULL,
                    location_type TEXT NOT NULL
                );
                """
            )

            # 2. Travel Segments (Timetables / Schedules / Feeds)
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS travel_segments (
                    segment_id TEXT PRIMARY KEY,
                    mode TEXT NOT NULL,
                    operator TEXT NOT NULL,
                    service_number TEXT NOT NULL,
                    origin_code TEXT NOT NULL,
                    destination_code TEXT NOT NULL,
                    departure_time TEXT NOT NULL,
                    arrival_time TEXT NOT NULL,
                    duration_minutes INTEGER NOT NULL,
                    distance_km REAL NOT NULL,
                    price_gbp REAL NOT NULL,
                    seats_available INTEGER,
                    verification_status TEXT NOT NULL,
                    verification_source TEXT NOT NULL,
                    confidence_score REAL NOT NULL,
                    co2_kg REAL,
                    FOREIGN KEY (origin_code) REFERENCES locations(code),
                    FOREIGN KEY (destination_code) REFERENCES locations(code)
                );
                """
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_segments_od ON travel_segments(origin_code, destination_code);"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_segments_dept ON travel_segments(departure_time);"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_segments_mode ON travel_segments(mode);"
            )

            # 3. Disruption Events
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
                    description TEXT NOT NULL,
                    verification_status TEXT NOT NULL,
                    reported_at TEXT NOT NULL,
                    valid_until TEXT,
                    is_active INTEGER DEFAULT 1
                );
                """
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_disruptions_active ON disruptions(is_active);"
            )

            # 4. Passengers and Stranded Profiles
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS passengers (
                    user_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL,
                    current_location_code TEXT NOT NULL,
                    intended_destination_code TEXT NOT NULL,
                    budget_gbp REAL NOT NULL,
                    arrival_deadline TEXT NOT NULL,
                    max_transfers INTEGER NOT NULL,
                    priority TEXT NOT NULL,
                    requires_step_free_access INTEGER NOT NULL,
                    original_journey_json TEXT,
                    FOREIGN KEY (current_location_code) REFERENCES locations(code),
                    FOREIGN KEY (intended_destination_code) REFERENCES locations(code)
                );
                """
            )

            # 5. Recovery Plans
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS recovery_plans (
                    recovery_id TEXT PRIMARY KEY,
                    passenger_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    recommended_options_json TEXT NOT NULL,
                    execution_time_ms REAL NOT NULL,
                    explanation TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (passenger_id) REFERENCES passengers(user_id)
                );
                """
            )

            # 6. Human-In-The-Loop Approval Audit Actions
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS approval_actions (
                    action_id TEXT PRIMARY KEY,
                    recovery_id TEXT NOT NULL,
                    option_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    user_notes TEXT,
                    action_timestamp TEXT NOT NULL,
                    is_booking_authorized INTEGER NOT NULL,
                    FOREIGN KEY (recovery_id) REFERENCES recovery_plans(recovery_id)
                );
                """
            )

            conn.commit()

    # -------------------------------------------------------------------------
    # Locations
    # -------------------------------------------------------------------------

    def save_location(self, loc: Location) -> None:
        """Inserts or updates a transit location."""
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO locations (code, name, city, latitude, longitude, location_type)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (loc.code, loc.name, loc.city, loc.latitude, loc.longitude, loc.location_type),
            )
            conn.commit()

    def get_location(self, code: str) -> Optional[Location]:
        """Retrieves a location by its code."""
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM locations WHERE code = ?", (code,)).fetchone()
            if not row:
                return None
            return Location(
                code=row["code"],
                name=row["name"],
                city=row["city"],
                latitude=row["latitude"],
                longitude=row["longitude"],
                location_type=row["location_type"],
            )

    def list_all_locations(self) -> List[Location]:
        """Retrieves all registered transit locations."""
        with self.get_connection() as conn:
            rows = conn.execute("SELECT * FROM locations ORDER BY city, name").fetchall()
            return [
                Location(
                    code=r["code"],
                    name=r["name"],
                    city=r["city"],
                    latitude=r["latitude"],
                    longitude=r["longitude"],
                    location_type=r["location_type"],
                )
                for r in rows
            ]

    # -------------------------------------------------------------------------
    # Travel Segments (Timetables)
    # -------------------------------------------------------------------------

    def save_segment(self, segment: TravelSegment) -> None:
        """Inserts or updates a travel segment."""
        self.save_segments([segment])

    def save_segments(self, segments: List[TravelSegment]) -> None:
        """Bulk inserts or updates multiple travel segments in a single transaction."""
        if not segments:
            return

        records = [
            (
                s.segment_id,
                s.mode.value if hasattr(s.mode, "value") else str(s.mode),
                s.operator,
                s.service_number,
                s.origin.code,
                s.destination.code,
                s.departure_time.isoformat(),
                s.arrival_time.isoformat(),
                s.duration_minutes,
                s.distance_km,
                s.price_gbp,
                s.seats_available,
                s.verification_status.value if hasattr(s.verification_status, "value") else str(s.verification_status),
                s.verification_source,
                s.confidence_score,
                s.co2_kg,
            )
            for s in segments
        ]

        with self.get_connection() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO travel_segments (
                    segment_id, mode, operator, service_number, origin_code, destination_code,
                    departure_time, arrival_time, duration_minutes, distance_km, price_gbp,
                    seats_available, verification_status, verification_source, confidence_score, co2_kg
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                records,
            )
            conn.commit()

    def query_segments(
        self,
        origin_code: Optional[str] = None,
        destination_code: Optional[str] = None,
        mode: Optional[TransportMode] = None,
        earliest_departure: Optional[datetime] = None,
        latest_arrival: Optional[datetime] = None,
        max_price_gbp: Optional[float] = None,
    ) -> List[TravelSegment]:
        """Queries travel segments with filtering options."""
        query = "SELECT s.* FROM travel_segments s WHERE 1=1"
        params: List[Any] = []

        if origin_code:
            query += " AND s.origin_code = ?"
            params.append(origin_code)

        if destination_code:
            query += " AND s.destination_code = ?"
            params.append(destination_code)

        if mode:
            query += " AND s.mode = ?"
            params.append(mode.value if hasattr(mode, "value") else str(mode))

        if earliest_departure:
            query += " AND s.departure_time >= ?"
            params.append(earliest_departure.isoformat())

        if latest_arrival:
            query += " AND s.arrival_time <= ?"
            params.append(latest_arrival.isoformat())

        if max_price_gbp is not None:
            query += " AND s.price_gbp <= ?"
            params.append(max_price_gbp)

        query += " ORDER BY s.departure_time ASC"

        with self.get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            results: List[TravelSegment] = []
            for r in rows:
                orig = self.get_location(r["origin_code"])
                dest = self.get_location(r["destination_code"])
                if not orig or not dest:
                    continue
                results.append(
                    TravelSegment(
                        segment_id=r["segment_id"],
                        mode=TransportMode(r["mode"]),
                        operator=r["operator"],
                        service_number=r["service_number"],
                        origin=orig,
                        destination=dest,
                        departure_time=datetime.fromisoformat(r["departure_time"]),
                        arrival_time=datetime.fromisoformat(r["arrival_time"]),
                        duration_minutes=r["duration_minutes"],
                        distance_km=r["distance_km"],
                        price_gbp=r["price_gbp"],
                        seats_available=r["seats_available"],
                        verification_status=DataVerificationStatus(r["verification_status"]),
                        verification_source=r["verification_source"],
                        confidence_score=r["confidence_score"],
                        co2_kg=r["co2_kg"],
                    )
                )
            return results

    # -------------------------------------------------------------------------
    # Disruptions
    # -------------------------------------------------------------------------

    def save_disruption(self, disruption: DisruptionEvent, is_active: bool = True) -> None:
        """Inserts or updates a disruption incident."""
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO disruptions (
                    event_id, mode, disruption_type, severity, source_reference, operator,
                    affected_origin, affected_destination, affected_stations_json,
                    delay_minutes, is_cancelled, description, verification_status,
                    reported_at, valid_until, is_active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    disruption.event_id,
                    disruption.mode.value if hasattr(disruption.mode, "value") else str(disruption.mode),
                    disruption.disruption_type.value if hasattr(disruption.disruption_type, "value") else str(disruption.disruption_type),
                    disruption.severity.value if hasattr(disruption.severity, "value") else str(disruption.severity),
                    disruption.source_reference,
                    disruption.operator,
                    disruption.affected_origin,
                    disruption.affected_destination,
                    json.dumps(disruption.affected_stations),
                    disruption.delay_minutes,
                    1 if disruption.is_cancelled else 0,
                    disruption.description,
                    disruption.verification_status.value if hasattr(disruption.verification_status, "value") else str(disruption.verification_status),
                    disruption.reported_at.isoformat(),
                    disruption.valid_until.isoformat() if disruption.valid_until else None,
                    1 if is_active else 0,
                ),
            )
            conn.commit()

    def get_active_disruptions(
        self,
        mode: Optional[TransportMode] = None,
        station_code: Optional[str] = None,
    ) -> List[DisruptionEvent]:
        """Retrieves currently active disruptions."""
        query = "SELECT * FROM disruptions WHERE is_active = 1"
        params: List[Any] = []

        if mode:
            query += " AND mode = ?"
            params.append(mode.value if hasattr(mode, "value") else str(mode))

        with self.get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            events: List[DisruptionEvent] = []
            for r in rows:
                affected_stations = json.loads(r["affected_stations_json"])
                if station_code and (
                    station_code not in affected_stations
                    and station_code != r["affected_origin"]
                    and station_code != r["affected_destination"]
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
                        description=r["description"],
                        verification_status=DataVerificationStatus(r["verification_status"]),
                        reported_at=datetime.fromisoformat(r["reported_at"]),
                        valid_until=datetime.fromisoformat(r["valid_until"]) if r["valid_until"] else None,
                    )
                )
            return events

    def get_disruption(self, event_id: str) -> Optional[DisruptionEvent]:
        """Gets a disruption by ID."""
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM disruptions WHERE event_id = ?", (event_id,)).fetchone()
            if not row:
                return None
            return DisruptionEvent(
                event_id=row["event_id"],
                mode=TransportMode(row["mode"]),
                disruption_type=DisruptionType(row["disruption_type"]),
                severity=DisruptionSeverity(row["severity"]),
                source_reference=row["source_reference"],
                operator=row["operator"],
                affected_origin=row["affected_origin"],
                affected_destination=row["affected_destination"],
                affected_stations=json.loads(row["affected_stations_json"]),
                delay_minutes=row["delay_minutes"],
                is_cancelled=bool(row["is_cancelled"]),
                description=row["description"],
                verification_status=DataVerificationStatus(row["verification_status"]),
                reported_at=datetime.fromisoformat(row["reported_at"]),
                valid_until=datetime.fromisoformat(row["valid_until"]) if row["valid_until"] else None,
            )

    # -------------------------------------------------------------------------
    # Passengers
    # -------------------------------------------------------------------------

    def save_passenger_profile(self, profile: PassengerProfile) -> None:
        """Stores or updates passenger profile."""
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO passengers (
                    user_id, name, email, current_location_code, intended_destination_code,
                    budget_gbp, arrival_deadline, max_transfers, priority, requires_step_free_access,
                    original_journey_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    profile.user_id,
                    profile.name,
                    profile.email,
                    profile.current_location.code,
                    profile.intended_destination.code,
                    profile.budget_gbp,
                    profile.arrival_deadline.isoformat(),
                    profile.max_transfers,
                    profile.priority.value if hasattr(profile.priority, "value") else str(profile.priority),
                    1 if profile.requires_step_free_access else 0,
                    profile.original_journey.model_dump_json() if profile.original_journey else None,
                ),
            )
            conn.commit()

    def get_passenger_profile(self, user_id: str) -> Optional[PassengerProfile]:
        """Loads a passenger profile by user_id."""
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM passengers WHERE user_id = ?", (user_id,)).fetchone()
            if not row:
                return None
            curr = self.get_location(row["current_location_code"])
            dest = self.get_location(row["intended_destination_code"])
            if not curr or not dest:
                return None

            orig_journey = None
            if row["original_journey_json"]:
                orig_journey = Journey.model_validate_json(row["original_journey_json"])

            return PassengerProfile(
                user_id=row["user_id"],
                name=row["name"],
                email=row["email"],
                current_location=curr,
                intended_destination=dest,
                budget_gbp=row["budget_gbp"],
                arrival_deadline=datetime.fromisoformat(row["arrival_deadline"]),
                max_transfers=row["max_transfers"],
                priority=OptimizationPriority(row["priority"]),
                requires_step_free_access=bool(row["requires_step_free_access"]),
                original_journey=orig_journey,
            )

    # -------------------------------------------------------------------------
    # Recovery Plans & Approval Actions
    # -------------------------------------------------------------------------

    def save_recovery_plan(self, plan: RecoveryPlanResponse) -> None:
        """Stores a generated recovery plan and its candidate options."""
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO recovery_plans (
                    recovery_id, passenger_id, status, recommended_options_json,
                    execution_time_ms, explanation, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    plan.recovery_id,
                    plan.passenger_id,
                    plan.status.value if hasattr(plan.status, "value") else str(plan.status),
                    json.dumps([json.loads(opt.model_dump_json()) for opt in plan.recommended_options]),
                    plan.execution_time_ms,
                    plan.explanation,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.commit()

    def get_recovery_plan(self, recovery_id: str) -> Optional[RecoveryPlanResponse]:
        """Retrieves a recovery plan by recovery_id."""
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM recovery_plans WHERE recovery_id = ?", (recovery_id,)).fetchone()
            if not row:
                return None
            raw_opts = json.loads(row["recommended_options_json"])
            options = [RecoveryOption.model_validate_json(json.dumps(o)) for o in raw_opts]
            return RecoveryPlanResponse(
                recovery_id=row["recovery_id"],
                passenger_id=row["passenger_id"],
                status=RecoveryStatus(row["status"]),
                recommended_options=options,
                execution_time_ms=row["execution_time_ms"],
                explanation=row["explanation"],
            )

    def record_approval_action(
        self,
        action: UserApprovalActionRequest,
        is_booking_authorized: bool,
    ) -> None:
        """
        Records human-in-the-loop decision to enforce that no action occurs
        without immutable approval auditing.
        """
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO approval_actions (
                    action_id, recovery_id, option_id, user_id, decision, user_notes,
                    action_timestamp, is_booking_authorized
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    action.action_id,
                    action.recovery_id,
                    action.option_id,
                    action.user_id,
                    action.decision.value if hasattr(action.decision, "value") else str(action.decision),
                    action.user_notes,
                    action.action_timestamp.isoformat(),
                    1 if is_booking_authorized else 0,
                ),
            )
            conn.commit()

    def get_approval_actions(self, recovery_id: str) -> List[Dict[str, Any]]:
        """Retrieves audit trail of actions for a given recovery plan."""
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM approval_actions WHERE recovery_id = ? ORDER BY action_timestamp DESC",
                (recovery_id,),
            ).fetchall()
            return [dict(r) for r in rows]
