"""Synthetic timetable and travel dataset generator.

Generates realistic multimodal transport network data across rail, coach/bus,
road/cabs, and regional air shuttles with realistic prices, speeds, and stops.
"""

from datetime import datetime, timedelta, timezone
from typing import List, Optional

from routerescue.data.database import DatabaseManager
from routerescue.data.synthetic_corridors import (
    LOCATIONS,
    get_default_disruption_scenarios,
)
from routerescue.schemas.common import (
    DataVerificationStatus,
    OptimizationPriority,
    TransportMode,
)
from routerescue.schemas.travel import (
    Journey,
    Location,
    PassengerProfile,
    TravelSegment,
)


def generate_synthetic_segments(
    base_time: Optional[datetime] = None,
    num_days: int = 2,
) -> List[TravelSegment]:
    """
    Generates realistic multimodal travel segments across London, Birmingham,
    Manchester, Leeds, and Liverpool corridors over the specified days.
    """
    if base_time is None:
        base_time = datetime.now(timezone.utc).replace(hour=6, minute=0, second=0, microsecond=0)

    segments: List[TravelSegment] = []
    seg_counter = 1000

    # Modal Route Templates (origin_code, dest_code, mode, operator, service_prefix, duration_min, dist_km, base_price, interval_min, co2_kg)
    templates = [
        # --- High Frequency Intercity Rail ---
        ("EUS", "BHM", TransportMode.TRAIN, "London Northwestern", "LNWR", 95, 182.0, 24.50, 30, 6.2),
        ("EUS", "BHM", TransportMode.TRAIN, "Avanti West Coast", "VT", 82, 182.0, 36.00, 30, 6.0),
        ("BHM", "EUS", TransportMode.TRAIN, "Avanti West Coast", "VT", 82, 182.0, 36.00, 30, 6.0),
        ("BHM", "MAN", TransportMode.TRAIN, "CrossCountry", "XC", 92, 138.0, 28.50, 30, 5.8),
        ("MAN", "BHM", TransportMode.TRAIN, "CrossCountry", "XC", 92, 138.0, 28.50, 30, 5.8),
        ("EUS", "MAN", TransportMode.TRAIN, "Avanti West Coast", "VT", 128, 305.0, 58.00, 20, 11.2),
        ("MAN", "EUS", TransportMode.TRAIN, "Avanti West Coast", "VT", 128, 305.0, 58.00, 20, 11.2),
        ("KGX", "LDS", TransportMode.TRAIN, "LNER", "GR", 132, 298.0, 48.00, 30, 9.8),
        ("LDS", "KGX", TransportMode.TRAIN, "LNER", "GR", 132, 298.0, 48.00, 30, 9.8),
        ("LDS", "MAN", TransportMode.TRAIN, "TransPennine Express", "TP", 55, 68.0, 16.50, 20, 2.8),
        ("MAN", "LDS", TransportMode.TRAIN, "TransPennine Express", "TP", 55, 68.0, 16.50, 20, 2.8),
        ("MAN", "LIV", TransportMode.TRAIN, "Northern Rail", "NT", 44, 52.0, 9.50, 30, 2.1),
        ("LIV", "MAN", TransportMode.TRAIN, "Northern Rail", "NT", 44, 52.0, 9.50, 30, 2.1),

        # --- Intercity Coach / Bus ---
        ("VIC", "BCS", TransportMode.BUS, "National Express", "NX401", 165, 192.0, 12.50, 60, 4.1),
        ("BCS", "VIC", TransportMode.BUS, "National Express", "NX402", 165, 192.0, 12.50, 60, 4.1),
        ("BCS", "MCS", TransportMode.BUS, "National Express", "NX310", 140, 142.0, 14.00, 60, 3.8),
        ("MCS", "BCS", TransportMode.BUS, "National Express", "NX311", 140, 142.0, 14.00, 60, 3.8),
        ("VIC", "MCS", TransportMode.BUS, "Megabus", "M11", 265, 320.0, 18.00, 120, 6.9),
        ("MCS", "VIC", TransportMode.BUS, "FlixBus", "FL02", 270, 320.0, 19.50, 120, 6.7),
        ("LDS", "MCS", TransportMode.BUS, "National Express", "NX220", 75, 72.0, 8.50, 60, 2.2),

        # --- Intra-City Transfer Cabs & Shuttles ---
        ("EUS", "VIC", TransportMode.CAB, "RouteRescue Partner Cab", "CAB-LDN", 25, 6.5, 22.00, 15, 2.1),
        ("VIC", "EUS", TransportMode.CAB, "RouteRescue Partner Cab", "CAB-LDN", 25, 6.5, 22.00, 15, 2.1),
        ("BHM", "BCS", TransportMode.CAB, "City Cabs Birmingham", "CAB-BHM", 10, 2.1, 9.00, 10, 0.8),
        ("BCS", "BHM", TransportMode.CAB, "City Cabs Birmingham", "CAB-BHM", 10, 2.1, 9.00, 10, 0.8),
        ("MAN", "MCS", TransportMode.CAB, "Manchester Taxis", "CAB-MAN", 8, 1.8, 8.50, 10, 0.6),
        ("MCS", "MAN", TransportMode.CAB, "Manchester Taxis", "CAB-MAN", 8, 1.8, 8.50, 10, 0.6),
        ("EUS", "KGX", TransportMode.WALK, "Pedestrian Walkway", "WALK-01", 12, 0.9, 0.00, 5, 0.0),
        ("KGX", "EUS", TransportMode.WALK, "Pedestrian Walkway", "WALK-01", 12, 0.9, 0.00, 5, 0.0),

        # --- Emergency Highway Long-Distance Cabs ---
        ("EUS", "BHM", TransportMode.CAB, "Executive Highway Transfer", "CAB-EX-EB", 145, 195.0, 185.00, 30, 38.0),
        ("BHM", "MAN", TransportMode.CAB, "Executive Highway Transfer", "CAB-EX-BM", 110, 145.0, 140.00, 30, 28.5),
        ("LDS", "MAN", TransportMode.CAB, "Yorkshire Intercity Cab", "CAB-LM", 65, 72.0, 85.00, 20, 15.0),

        # --- Domestic Air Shuttles ---
        ("LHR", "MAN_AIR", TransportMode.FLIGHT, "British Airways", "BA1386", 60, 290.0, 95.00, 180, 52.0),
        ("MAN_AIR", "LHR", TransportMode.FLIGHT, "British Airways", "BA1387", 60, 290.0, 95.00, 180, 52.0),
    ]

    for day in range(num_days):
        current_day_start = base_time + timedelta(days=day)

        for (
            orig_code,
            dest_code,
            mode,
            operator,
            prefix,
            dur_min,
            dist_km,
            price,
            interval_min,
            co2,
        ) in templates:
            orig = LOCATIONS[orig_code]
            dest = LOCATIONS[dest_code]

            # Generate departures from 06:00 to 22:30
            day_cursor = current_day_start.replace(hour=6, minute=0)
            day_end = current_day_start.replace(hour=22, minute=30)

            while day_cursor <= day_end:
                dept_time = day_cursor
                arr_time = dept_time + timedelta(minutes=dur_min)
                seg_counter += 1

                # Realistic seat count variation
                seats = None
                if mode in (TransportMode.TRAIN, TransportMode.BUS, TransportMode.FLIGHT):
                    seats = 15 + (seg_counter % 65)

                segments.append(
                    TravelSegment(
                        segment_id=f"SEG-{mode.value[:2]}-{seg_counter}",
                        mode=mode,
                        operator=operator,
                        service_number=f"{prefix}-{seg_counter % 900 + 100}",
                        origin=orig,
                        destination=dest,
                        departure_time=dept_time,
                        arrival_time=arr_time,
                        duration_minutes=dur_min,
                        distance_km=dist_km,
                        price_gbp=price,
                        seats_available=seats,
                        verification_status=DataVerificationStatus.SIMULATED_ESTIMATE,
                        verification_source=f"Synthetic {mode.value.capitalize()} Service Matrix v1.0",
                        confidence_score=0.98 if mode == TransportMode.TRAIN else 0.92,
                        co2_kg=co2,
                    )
                )

                day_cursor += timedelta(minutes=interval_min)

    return segments


def seed_database(db: Optional[DatabaseManager] = None) -> None:
    """Initializes tables and loads core locations, timetables, disruptions, and sample passengers."""
    if db is None:
        db = DatabaseManager()

    db.init_db()

    # 1. Seed Locations
    for loc in LOCATIONS.values():
        db.save_location(loc)

    # 2. Seed Timetable Segments
    now = datetime.now(timezone.utc)
    segments = generate_synthetic_segments(base_time=now - timedelta(hours=2), num_days=2)
    db.save_segments(segments)

    # 3. Seed Disruptions
    disruptions = get_default_disruption_scenarios(base_time=now)
    for d in disruptions:
        db.save_disruption(d, is_active=True)

    # 4. Seed Stranded Passenger Example: Sarah Jenkins (London Euston -> Manchester Piccadilly)
    orig = LOCATIONS["EUS"]
    dest = LOCATIONS["MAN"]

    # Original cancelled train journey
    orig_train_seg = TravelSegment(
        segment_id="SEG-ORIG-CANCELLED-001",
        mode=TransportMode.TRAIN,
        operator="Avanti West Coast",
        service_number="VT-3901",
        origin=orig,
        destination=dest,
        departure_time=now + timedelta(minutes=20),
        arrival_time=now + timedelta(minutes=148),
        duration_minutes=128,
        distance_km=305.0,
        price_gbp=68.00,
        seats_available=0,
        verification_status=DataVerificationStatus.SIMULATED_ESTIMATE,
        verification_source="Avanti West Coast Scheduled Feed",
        confidence_score=1.0,
        co2_kg=11.2,
    )
    original_journey = Journey(
        journey_id="JOURNEY-SARAH-ORIGINAL",
        origin=orig,
        destination=dest,
        segments=[orig_train_seg],
        total_price_gbp=68.00,
        total_duration_minutes=128,
        total_transfers=0,
        departure_time=orig_train_seg.departure_time,
        arrival_time=orig_train_seg.arrival_time,
        verification_status=DataVerificationStatus.SIMULATED_ESTIMATE,
        feasibility_score=0.0,
        notes=["Cancelled due to emergency overhead wire damage near Rugby."],
    )

    sample_passenger = PassengerProfile(
        user_id="USR-PASSENGER-7712",
        name="Sarah Jenkins",
        email="sarah.jenkins@example.co.uk",
        current_location=orig,
        intended_destination=dest,
        budget_gbp=140.00,
        arrival_deadline=now + timedelta(hours=5),
        max_transfers=2,
        priority=OptimizationPriority.BALANCED,
        requires_step_free_access=False,
        original_journey=original_journey,
    )
    db.save_passenger_profile(sample_passenger)


if __name__ == "__main__":
    db = DatabaseManager()
    seed_database(db)
    print("Database successfully seeded with synthetic travel network.")
