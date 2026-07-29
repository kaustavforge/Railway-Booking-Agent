"""
PNR details endpoint.
"""

from fastapi import APIRouter, HTTPException, Depends

from app.database.connection import bookings_conn
from app.services.pdf_generator import fetch_booking_for_pdf
from app.api.auth import current_user_id

router = APIRouter()


@router.get("/api/pnr-details/{pnr}")
def pnr_details(pnr: str, user_id: str = Depends(current_user_id)):
    """Returns structured booking details for a given PNR from Supabase."""
    try:
        owner = bookings_conn.execute("SELECT 1 FROM bookings WHERE pnr_number=%s AND user_id=%s", (pnr, user_id)).fetchone()
        if not owner:
            raise HTTPException(status_code=404, detail="Booking not found")
        booking_data = fetch_booking_for_pdf(pnr, bookings_conn=bookings_conn)
        return {"status": "success", "data": booking_data}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Could not load booking details")
