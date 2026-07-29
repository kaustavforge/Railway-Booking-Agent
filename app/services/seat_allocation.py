"""
Seat-map & database helpers for booking allocation.
"""

import re
from datetime import date
from typing import Optional

from app.config.settings import (
    BOOKING_WINDOW_START,
    BOOKING_WINDOW_END,
    NUM_COACHES,
    CLASS_CAPACITY,
    BERTH_CYCLE,
)
from app.database.connection import bookings_conn


def _validate_journey_date(journey_date: str) -> Optional[str]:
    try:
        jd = date.fromisoformat(journey_date.strip())
    except ValueError:
        return "journey_date must be in YYYY-MM-DD format."
    if jd < BOOKING_WINDOW_START:
        return (
            f"Bookings open from {BOOKING_WINDOW_START.isoformat()} onward "
            f"(tomorrow) — {journey_date} has already passed or is today."
        )
    if jd > BOOKING_WINDOW_END:
        return f"Bookings are only open up to {BOOKING_WINDOW_END.isoformat()} in this system."
    return None


def _occupied_seat_indices(train_number, journey_date, coach_name):
    rows = bookings_conn.execute(
        """SELECT seat_berth FROM bookings
           WHERE train_number = ? AND journey_date = ? AND coach = ?
                 AND current_status = 'CNF'""",
        (train_number, journey_date, coach_name),
    ).fetchall()
    out = set()
    for (sb,) in rows:
        # Family bookings store multiple seats in one field, for example
        # "2A1-3, 2A1-4".  Parse every seat so none can be allocated twice.
        for seat in str(sb or "").split(","):
            m = re.match(rf"\s*{re.escape(coach_name)}-(\d+)\s*$", seat)
            if m:
                out.add(int(m.group(1)))
    return out


def _find_confirmed_seat(train_number, journey_date, travel_class, berth_pref, count=1):
    n_coaches = NUM_COACHES.get(travel_class, 3)
    seats_per_coach = CLASS_CAPACITY.get(travel_class, 64) // n_coaches
    
    pref_list = []
    if berth_pref:
        pref_list = [p.strip().lower() for p in str(berth_pref).replace("/", ",").replace("&", ",").replace("and", ",").split(",") if p.strip()]
    
    allocated = []
    pref_match = True
    
    # First pass: try to match requested berth preferences if provided
    if pref_list:
        for c in range(1, n_coaches + 1):
            coach_name = f"{travel_class}{c}"
            occupied = _occupied_seat_indices(train_number, journey_date, coach_name)
            for idx in range(1, seats_per_coach + 1):
                if idx in occupied:
                    continue
                berth = BERTH_CYCLE[(idx - 1) % 8]
                seat_berth = f"{coach_name}-{idx}"
                
                needed_pref = pref_list[len(allocated)] if len(allocated) < len(pref_list) else None
                if needed_pref and needed_pref not in berth.lower():
                    continue
                    
                allocated.append((coach_name, seat_berth, berth))
                if len(allocated) == count:
                    break
            if len(allocated) == count:
                break

    # Second pass fallback: if preference match didn't find enough seats, allocate any available seats
    if len(allocated) < count:
        pref_match = False
        allocated = []
        for c in range(1, n_coaches + 1):
            coach_name = f"{travel_class}{c}"
            occupied = _occupied_seat_indices(train_number, journey_date, coach_name)
            for idx in range(1, seats_per_coach + 1):
                if idx in occupied:
                    continue
                berth = BERTH_CYCLE[(idx - 1) % 8]
                seat_berth = f"{coach_name}-{idx}"
                allocated.append((coach_name, seat_berth, berth))
                if len(allocated) == count:
                    break
            if len(allocated) == count:
                break

    if len(allocated) == count:
        coaches = ", ".join(list(dict.fromkeys([a[0] for a in allocated])))
        seats = ", ".join([a[1] for a in allocated])
        berths = ", ".join([a[2] for a in allocated])
        return coaches, seats, berths, pref_match
    return None


def _rac_slot_limit(travel_class):
    capacity = CLASS_CAPACITY.get(travel_class, 64)
    return max(4, capacity // 8)


def _find_rac_slot(train_number, journey_date, travel_class):
    rows = bookings_conn.execute(
        """SELECT seat_berth FROM bookings
           WHERE train_number = ? AND journey_date = ? AND class = ?
                 AND current_status = 'RAC'""",
        (train_number, journey_date, travel_class),
    ).fetchall()
    occupancy = {}
    for (sb,) in rows:
        occupancy[sb] = occupancy.get(sb, 0) + 1
    for i in range(1, _rac_slot_limit(travel_class) + 1):
        label = f"RAC {i}"
        if occupancy.get(label, 0) < 2:
            return label
    return None


def _next_wl_label(train_number, journey_date, travel_class):
    count = bookings_conn.execute(
        """SELECT COUNT(*) FROM bookings
           WHERE train_number = ? AND journey_date = ? AND class = ?
                 AND current_status = 'WL'""",
        (train_number, journey_date, travel_class),
    ).fetchone()[0]
    return f"WL {count + 1}"


def _row_as_dict(row):
    cols = [
        d[0]
        for d in bookings_conn.execute("SELECT * FROM bookings LIMIT 0").description
    ]
    return dict(zip(cols, row))
