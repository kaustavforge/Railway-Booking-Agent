"""
PNR Status tool.
"""

from langchain_core.tools import tool

from app.database.connection import bookings_conn
from app.services.seat_allocation import _row_as_dict


@tool
def get_pnr_status(pnr_number: str) -> str:
    """Look up the booking status for a given 10-digit PNR number."""
    pnr_number = pnr_number.strip()
    row = bookings_conn.execute(
        "SELECT * FROM bookings WHERE pnr_number = ?", (pnr_number,)
    ).fetchone()
    if row is None:
        return f"No booking found for PNR {pnr_number}. Please double-check the number."
    r = _row_as_dict(row)
    coach = r["coach"] or "-"
    return (
        f"PNR {pnr_number}: {r['passenger_name']}, Train {r['train_number']} "
        f"({r['train_name']}), {r['source_code']} -> {r['destination_code']}, "
        f"Journey date {r['journey_date']}, Class {r['class']}, "
        f"Status: {r['current_status']}, Coach/Seat: {coach} / {r['seat_berth']} "
        f"({r['berth_type'] or '-'}), Passengers: {r['num_passengers']}, Fare: INR {r['fare_inr']}."
    )
