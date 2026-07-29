"""
Train search and schedule tools.
"""

import pandas as pd
from langchain_core.tools import tool

from app.config.settings import trains_df, schedules_df, CLASS_CAPACITY, NUM_COACHES
from app.database.connection import bookings_conn
from app.services.seat_allocation import (
    _validate_journey_date,
    _rac_slot_limit,
)


@tool
def search_trains(source_code: str, destination_code: str) -> str:
    """Search for trains between two station codes (e.g. HWH, NDLS, MAS)."""
    source_code, destination_code = (
        source_code.strip().upper(),
        destination_code.strip().upper(),
    )
    matches = trains_df[
        (trains_df["source_code"] == source_code)
        & (trains_df["destination_code"] == destination_code)
    ]
    if matches.empty:
        return f"No direct trains found from {source_code} to {destination_code} in this dataset."
    lines = []
    for _, t in matches.iterrows():
        lines.append(
            f"Train {t['train_number']} ({t['train_name']}) — "
            f"Classes: {t['classes_available']}, Runs: {t['days_of_run']}, "
            f"Avg delay: {t['avg_delay_minutes']} min."
        )
    return "\n".join(lines)


@tool
def get_train_schedule(train_number: str) -> str:
    """Get the full stop-by-stop schedule for a given train number."""
    stops = schedules_df[schedules_df["train_number"] == int(train_number)].sort_values(
        "stop_sequence"
    )
    if stops.empty:
        return f"No schedule found for train number {train_number}."
    lines = []
    for _, s in stops.iterrows():
        arr = s["arrival"] if pd.notna(s["arrival"]) else "—"
        dep = s["departure"] if pd.notna(s["departure"]) else "—"
        lines.append(
            f"Day {s['day']}, Stop {s['stop_sequence']}: {s['station_name']} "
            f"({s['station_code']}) — Arr: {arr}, Dep: {dep}"
        )
    return "\n".join(lines)


@tool
def check_seat_availability(
    train_number: str, journey_date: str, travel_class: str
) -> str:
    """Check seat availability for a train on a given date and class."""
    date_error = _validate_journey_date(journey_date)
    if date_error:
        return date_error

    travel_class = travel_class.strip().upper()
    if travel_class not in CLASS_CAPACITY:
        return f"Unknown class '{travel_class}'. Valid classes: {', '.join(CLASS_CAPACITY)}."

    # Match the seat allocator: each class is divided across a whole number
    # of coaches, so 2A's configured 46 seats becomes 45 usable seats (3x15).
    capacity = (CLASS_CAPACITY[travel_class] // NUM_COACHES[travel_class]) * NUM_COACHES[travel_class]
    confirmed = bookings_conn.execute(
        """SELECT COALESCE(SUM(num_passengers), 0) FROM bookings
           WHERE train_number = ? AND journey_date = ? AND class = ?
                 AND current_status = 'CNF'""",
        (train_number, journey_date, travel_class),
    ).fetchone()[0]
    rac_taken = bookings_conn.execute(
        """SELECT COALESCE(SUM(num_passengers), 0) FROM bookings
           WHERE train_number = ? AND journey_date = ? AND class = ?
                 AND current_status = 'RAC'""",
        (train_number, journey_date, travel_class),
    ).fetchone()[0]
    wl_count = bookings_conn.execute(
        """SELECT COALESCE(SUM(num_passengers), 0) FROM bookings
           WHERE train_number = ? AND journey_date = ? AND class = ?
                 AND current_status = 'WL'""",
        (train_number, journey_date, travel_class),
    ).fetchone()[0]

    rac_capacity = _rac_slot_limit(travel_class) * 2
    if confirmed < capacity:
        return f"{travel_class}: AVAILABLE — {capacity - confirmed} confirmed seat(s) left."
    if rac_taken < rac_capacity:
        return f"{travel_class}: RAC {rac_taken + 1} — no confirmed seats left, RAC available."
    return f"{travel_class}: WL {wl_count + 1} — class is full, booking would be waitlisted."
