import os
import datetime
import tempfile
from typing import List, Optional

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from langgraph.types import Command
from langchain_core.messages import HumanMessage

# Import your compiled LangGraph agent and DB connection from your main script
# (Assuming your script is named railway_code_cloud.py, rename the import if needed)
from railway_code_cloud import graph, bookings_conn

# Import your PDF generation logic
# (Assuming you saved the PDF script as pdf_generator.py)
from pdf_generator import generate_irctc_ticket_pdf, fetch_booking_for_pdf

app = FastAPI(title="RailBot AI API")

# Configure CORS so your Stitch frontend can communicate with this backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace "*" with your Stitch UI domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------
# Pydantic Models for Type Validation
# ---------------------------------------------------------
class ChatRequest(BaseModel):
    message: str
    thread_id: str


class ApprovalRequest(BaseModel):
    thread_id: str
    approved: bool


class HistoryMessage(BaseModel):
    role: str
    content: str
    timestamp: str


class ChatHistoryResponse(BaseModel):
    thread_id: str
    messages: List[HistoryMessage]


# ---------------------------------------------------------
# 1. Core Chat Endpoint
# ---------------------------------------------------------
@app.post("/api/chat")
def chat_endpoint(request: ChatRequest):
    """Sends a message to the LangGraph agent and returns the response."""
    config = {"configurable": {"thread_id": request.thread_id}}

    # Generate the current UTC timestamp
    current_time = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # Create the human message and inject the timestamp into additional_kwargs
    user_msg = HumanMessage(
        content=request.message, additional_kwargs={"timestamp": current_time}
    )

    try:
        # Invoke the graph with the HumanMessage object instead of a raw tuple
        result = graph.invoke({"messages": [user_msg]}, config=config)

        # Check if the graph paused because a tool requires human approval
        if "__interrupt__" in result:
            interrupt_data = result["__interrupt__"][0].value
            return {
                "status": "requires_approval",
                "interrupt_data": interrupt_data,
                "agent_response": "I need your approval to proceed.",
            }

        # Normal execution complete
        return {"status": "success", "agent_response": result["messages"][-1].content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------
# 2. History Endpoint
# ---------------------------------------------------------
@app.get("/api/history/{thread_id}", response_model=ChatHistoryResponse)
def get_chat_history(thread_id: str):
    """
    Fetches the conversation history for a specific thread_id from LangGraph.
    """
    try:
        # Define the config with the thread_id
        config = {"configurable": {"thread_id": thread_id}}

        # Retrieve the latest state from the LangGraph checkpointer
        state_snapshot = graph.get_state(config)

        # If there is no state or no messages, the thread doesn't exist yet
        if (
            not state_snapshot
            or not state_snapshot.values
            or "messages" not in state_snapshot.values
        ):
            return ChatHistoryResponse(thread_id=thread_id, messages=[])

        # Extract and format the messages
        formatted_messages = []
        messages = state_snapshot.values.get("messages", [])

        for msg in messages:
            # Only include human and ai messages with actual content
            if msg.type not in ("human", "ai"):
                continue
            if not msg.content or not msg.content.strip():
                continue

            role = "user" if msg.type == "human" else "assistant"

            # Extract timestamp from additional_kwargs
            timestamp = msg.additional_kwargs.get(
                "timestamp", datetime.datetime.now(datetime.timezone.utc).isoformat()
            )

            formatted_messages.append(
                HistoryMessage(role=role, content=msg.content, timestamp=timestamp)
            )

        return ChatHistoryResponse(thread_id=thread_id, messages=formatted_messages)

    except Exception as e:
        print(f"Error fetching history for {thread_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch chat history")


# ---------------------------------------------------------
# 3. Human-in-the-Loop Approval Endpoint
# ---------------------------------------------------------
@app.post("/api/approve-complaint")
def approve_complaint(request: ApprovalRequest):
    """Resumes the LangGraph agent after a human approval decision."""
    config = {"configurable": {"thread_id": request.thread_id}}

    # Translate boolean to the "yes"/"no" expected by your graph logic
    decision = "yes" if request.approved else "no"

    try:
        # Resume the graph by passing the command
        result = graph.invoke(Command(resume={"approved": decision}), config=config)

        return {"status": "success", "agent_response": result["messages"][-1].content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------
# 4. PDF Ticket Generation Endpoint
# ---------------------------------------------------------
@app.get("/api/download-ticket/{pnr}")
def download_ticket(pnr: str):
    """Generates an IRCTC-style PDF for a given PNR and returns the file."""
    try:
        # Fetch data mapped to the dictionary format expected by the PDF script
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
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/pnr-details/{pnr}")
def pnr_details(pnr: str):
    """Returns structured booking details for a given PNR from Supabase."""
    try:
        booking_data = fetch_booking_for_pdf(pnr, bookings_conn=bookings_conn)
        return {"status": "success", "data": booking_data}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
