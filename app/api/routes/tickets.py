"""
PDF ticket generation endpoint.
"""

import os
import tempfile

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse

from app.database.connection import bookings_conn
from app.services.pdf_generator import generate_irctc_ticket_pdf, fetch_booking_for_pdf
from app.api.auth import current_user_id

router = APIRouter()


@router.get("/api/download-ticket/{pnr}")
def download_ticket(pnr: str, user_id: str = Depends(current_user_id)):
    """Generates an IRCTC-style PDF for a given PNR and returns the file."""
    try:
        # Fetch data mapped to the dictionary format expected by the PDF script
        owner = bookings_conn.execute("SELECT 1 FROM bookings WHERE pnr_number=%s AND user_id=%s", (pnr, user_id)).fetchone()
        if not owner:
            raise HTTPException(status_code=404, detail="Booking not found")
        booking_data = fetch_booking_for_pdf(pnr, bookings_conn=bookings_conn)

        # Define output path (cross-platform temp directory)
        output_path = os.path.join(tempfile.gettempdir(), f"ticket_{pnr}.pdf")

        # Generate the PDF
        generate_irctc_ticket_pdf(booking_data, output_pdf_path=output_path)

        # Serve the file directly to the browser
        return FileResponse(
            path=output_path,
            filename=f"ERS_Ticket_{pnr}.pdf",
            media_type="application/pdf",
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Could not generate ticket")
