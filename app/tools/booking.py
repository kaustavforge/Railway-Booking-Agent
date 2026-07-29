"""
Booking and cancellation tools.
"""

import random
import re
from typing import Optional, Union

import psycopg2
import psycopg2.errors
from langchain_core.tools import tool

from app.config.settings import (
    trains_df,
    CLASS_CAPACITY,
    VALID_BERTH_PREFS,
)
from app.database.connection import bookings_conn
from app.services.seat_allocation import (
    _validate_journey_date,
    _find_confirmed_seat,
    _find_rac_slot,
    _next_wl_label,
    _row_as_dict,
)


def _calculate_ticket_fare(train_number, travel_class, source_code, destination_code, num_passengers=1):
    """
    Calculates realistic ticket fare based on train number, class, 
    and station distance (or historical database averages).
    """
    try:
        cur = bookings_conn.execute(
            """SELECT AVG(fare_inr::numeric / GREATEST(num_passengers, 1))
               FROM bookings WHERE train_number = ? AND class = ? AND fare_inr > 0""",
            (int(train_number), travel_class)
        )
        row = cur.fetchone()
        if row and row[0] and row[0] > 0:
            base_fare = round(float(row[0]))
            return int(base_fare * max(1, num_passengers))
    except Exception:
        pass

    try:
        from app.services.pdf_generator import _estimate_distance_km
        dist = _estimate_distance_km(source_code, destination_code)
        if not dist:
            dist = 1000
        
        rates = {
            "1A": 3.2,
            "2A": 2.0,
            "3A": 1.35,
            "SL": 0.55,
            "EC": 1.4,
            "CC": 0.85
        }
        rate = rates.get(travel_class.upper(), 1.0)
        base_fare = round(max(300, dist * rate))
        return int(base_fare * max(1, num_passengers))
    except Exception:
        return int(1500 * max(1, num_passengers))


def _as_bool(value) -> bool:
    """Normalize model-emitted boolean values (some providers emit strings)."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y"}
    return bool(value)


@tool
def book_ticket(
    passenger_name: str,
    train_number: str,
    journey_date: str,
    travel_class: str,
    berth_preference: Optional[str] = None,
    num_passengers: Union[int, str] = 1,
    age: Optional[Union[int, str]] = None,
    gender: Optional[str] = None,
    confirmed: Union[bool, str] = False,
) -> str:
    """Book exactly one PNR ticket. For a family/group, call this tool ONCE: pass every
    passenger name as a comma-separated string, set num_passengers to the total, and pass
    comma-separated ages, genders, and berth preferences in the same passenger order.
    Never call this tool once per family member. The returned fare is the combined fare for
    the whole PNR and the ticket PDF contains all named passengers."""
    if not _as_bool(confirmed):
        return "Booking is ready but requires explicit user confirmation first."

    try:
        num_passengers = int(str(num_passengers).strip())
    except Exception:
        num_passengers = 1
    if not 1 <= num_passengers <= 10:
        return "Passenger count must be between 1 and 10."

    if not passenger_name or len(str(passenger_name).strip()) > 500:
        return "Please provide valid passenger name(s)."

    date_error = _validate_journey_date(journey_date)
    if date_error:
        return date_error

    travel_class = travel_class.strip().upper()
    if travel_class not in CLASS_CAPACITY:
        return f"Unknown class '{travel_class}'. Valid classes: {', '.join(CLASS_CAPACITY)}."

    if berth_preference is not None:
        user_prefs = [p.strip().lower() for p in str(berth_preference).replace("/", ",").replace("&", ",").replace("and", ",").split(",") if p.strip()]
        for p in user_prefs:
            if p not in VALID_BERTH_PREFS:
                return f"Unknown berth preference '{p}'. Valid options: Lower, Middle, Upper, Side Lower, Side Upper."

    train_row = trains_df[trains_df["train_number"] == int(train_number)]
    if train_row.empty:
        return f"Train number {train_number} not found."
    train_name = train_row.iloc[0]["train_name"]
    source_code = train_row.iloc[0]["source_code"]
    destination_code = train_row.iloc[0]["destination_code"]

    stored_age = None
    if age is not None:
        try:
            age_values = [value.strip() for value in str(age).split(",") if value.strip()]
            if age_values and all(value.isdigit() for value in age_values):
                stored_age = ", ".join(age_values)
        except Exception:
            stored_age = None

    bookings_conn.execute("BEGIN TRANSACTION")
    try:
        seat = _find_confirmed_seat(
            train_number, journey_date, travel_class, berth_preference, count=num_passengers
        )
        preference_note = ""
        if seat:
            coach, seat_berth, berth, pref_honored = seat
            status = "CNF"
            if berth_preference and not pref_honored:
                preference_note = f" (your preferred {berth_preference} berth wasn't free — assigned {berth} instead)"
        else:
            rac_label = _find_rac_slot(train_number, journey_date, travel_class)
            if rac_label:
                coach, seat_berth, berth, status = (
                    None,
                    rac_label,
                    "Side Lower (shared)",
                    "RAC",
                )
            else:
                coach, seat_berth, berth, status = (
                    None,
                    _next_wl_label(train_number, journey_date, travel_class),
                    None,
                    "WL",
                )

        calculated_fare = _calculate_ticket_fare(
            train_number, travel_class, source_code, destination_code, num_passengers
        )

        pnr_number = str(random.randint(1_000_000_000, 9_999_999_999))
        bookings_conn.execute(
            """INSERT INTO bookings
               (pnr_number, passenger_name, train_number, train_name,
                source_code, destination_code, journey_date, class,
                booking_status, current_status, coach, seat_berth,
                berth_type, num_passengers, fare_inr, booking_date,
                age, gender)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?, date('now'),?,?)""",
            (
                pnr_number,
                passenger_name,
                train_number,
                train_name,
                source_code,
                destination_code,
                journey_date,
                travel_class,
                status,
                status,
                coach,
                seat_berth,
                berth,
                num_passengers,
                calculated_fare,
                stored_age,
                gender,
            ),
        )
        bookings_conn.commit()
    except (psycopg2.errors.UniqueViolation, psycopg2.IntegrityError):
        bookings_conn.rollback()
        return "That seat was just booked by someone else — please try again."
    except Exception:
        bookings_conn.rollback()
        raise

    route = f"{source_code} -> {destination_code}"
    if status == "CNF":
        return (
            f"Booked! PNR {pnr_number}, {train_name} ({train_number}), {route}, "
            f"{journey_date}, Class {travel_class}, Seat {seat_berth} ({berth}), "
            f"Status: Confirmed.{preference_note}"
        )
    if status == "RAC":
        return (
            f"Booked! PNR {pnr_number}, {train_name} ({train_number}), {route}, "
            f"{journey_date}, Class {travel_class} — no confirmed seats left, "
            f"Status: RAC ({seat_berth})."
        )
    return (
        f"Booked! PNR {pnr_number}, {train_name} ({train_number}), {route}, "
        f"{journey_date}, Class {travel_class} is full, Status: Waitlisted ({seat_berth})."
    )


@tool
def cancel_ticket(pnr_number: str, confirmed: Union[bool, str] = False) -> str:
    """Cancel an existing booking by PNR number with automatic cascading promotions."""
    if not _as_bool(confirmed):
        return "Cancellation requires explicit user confirmation first."
    pnr_number = pnr_number.strip()
    if not re.fullmatch(r"\d{10}", pnr_number):
        return "PNR must be exactly 10 digits."

    bookings_conn.execute("BEGIN TRANSACTION")
    try:
        row = bookings_conn.execute(
            "SELECT * FROM bookings WHERE pnr_number = ?", (pnr_number,)
        ).fetchone()
        if row is None:
            bookings_conn.rollback()
            return f"No booking found for PNR {pnr_number}."

        r = _row_as_dict(row)
        if r["current_status"] == "CAN":
            bookings_conn.rollback()
            return f"PNR {pnr_number} is already cancelled."

        was_confirmed = r["current_status"] == "CNF"
        freed_coach, freed_seat = r["coach"], r["seat_berth"]
        train_number, journey_date, travel_class = (
            r["train_number"],
            r["journey_date"],
            r["class"],
        )

        bookings_conn.execute(
            "UPDATE bookings SET current_status = 'CAN', booking_status = 'CAN' WHERE pnr_number = ?",
            (pnr_number,),
        )

        notes = []
        if was_confirmed:
            next_rac = bookings_conn.execute(
                """SELECT pnr_number, seat_berth FROM bookings
                   WHERE train_number = ? AND journey_date = ? AND class = ?
                         AND current_status = 'RAC'
                   ORDER BY booking_date ASC, seat_berth ASC LIMIT 1""",
                (train_number, journey_date, travel_class),
            ).fetchone()
            if next_rac:
                promoted_pnr, old_rac_slot = next_rac
                bookings_conn.execute(
                    """UPDATE bookings SET current_status = 'CNF', booking_status = 'CNF',
                       coach = ?, seat_berth = ? WHERE pnr_number = ?""",
                    (freed_coach, freed_seat, promoted_pnr),
                )
                notes.append(
                    f"PNR {promoted_pnr} promoted from RAC to Confirmed, seat {freed_seat}."
                )

                next_wl = bookings_conn.execute(
                    """SELECT pnr_number FROM bookings
                       WHERE train_number = ? AND journey_date = ? AND class = ?
                             AND current_status = 'WL'
                       ORDER BY seat_berth ASC LIMIT 1""",
                    (train_number, journey_date, travel_class),
                ).fetchone()
                if next_wl:
                    bookings_conn.execute(
                        """UPDATE bookings SET current_status = 'RAC', booking_status = 'RAC',
                           coach = NULL, seat_berth = ? WHERE pnr_number = ?""",
                        (old_rac_slot, next_wl[0]),
                    )
                    notes.append(
                        f"PNR {next_wl[0]} promoted from Waitlist to RAC, slot {old_rac_slot}."
                    )

        bookings_conn.commit()
    except Exception:
        bookings_conn.rollback()
        raise

    suffix = " " + " ".join(notes) if notes else ""
    return f"PNR {pnr_number} has been cancelled.{suffix}"
