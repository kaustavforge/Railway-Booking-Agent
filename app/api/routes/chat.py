"""
Chat and complaint approval endpoints.
"""

import datetime
import json
import re
import uuid
import time
from collections import defaultdict, deque

from fastapi import APIRouter, HTTPException, Depends
from langchain_core.messages import HumanMessage
from langgraph.types import Command

from app.agent.graph import graph
from app.api.schemas import ChatRequest, ApprovalRequest
from app.api.auth import current_user_id

router = APIRouter()
_request_times: dict[str, deque[float]] = defaultdict(deque)


def enforce_rate_limit(user_id: str, limit: int = 30, window: int = 60) -> None:
    now = time.monotonic()
    recent = _request_times[user_id]
    while recent and now - recent[0] > window:
        recent.popleft()
    if len(recent) >= limit:
        raise HTTPException(429, "Too many requests. Please wait a moment and try again.")
    recent.append(now)


def ensure_thread_belongs_to_client(thread_id: str, client_id: str) -> None:
    """Keep anonymous browser sessions isolated from one another.

    This is intentionally a lightweight ownership check.  Replace the client id
    with a verified Supabase Auth user id when authentication is added.
    """
    if not client_id or not thread_id.startswith(f"anon_{client_id}_"):
        raise HTTPException(status_code=403, detail="This chat belongs to another browser session")


@router.post("/api/chat")
def chat_endpoint(request: ChatRequest, user_id: str = Depends(current_user_id)):
    """Sends a message to the LangGraph agent and returns the response."""
    from app.database.connection import bookings_conn
    enforce_rate_limit(user_id)
    pnr_match = re.search(r"\b\d{10}\b", request.message)
    if pnr_match and re.search(r"\b(cancel|cancellation)\b", request.message, re.IGNORECASE):
        booking_owner = bookings_conn.execute("SELECT user_id FROM bookings WHERE pnr_number=%s", (pnr_match.group(0),)).fetchone()
        if not booking_owner or str(booking_owner[0]) != user_id:
            raise HTTPException(403, "You can only cancel your own booking.")
    row = bookings_conn.execute("SELECT user_id FROM conversations WHERE langgraph_thread_id=%s", (request.thread_id,)).fetchone()
    if row and str(row[0]) != user_id: raise HTTPException(403, "Conversation belongs to another account")
    if not row:
        bookings_conn.execute("INSERT INTO conversations (id, user_id, langgraph_thread_id, title) VALUES (%s,%s,%s,%s)", (str(uuid.uuid4()), user_id, request.thread_id, request.message[:28]))
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
        response = result["messages"][-1].content
        # Attribute any newly generated PNRs to the authenticated account.
        for pnr in set(re.findall(r"\b\d{10}\b", str(response))):
            bookings_conn.execute("UPDATE bookings SET user_id=%s WHERE pnr_number=%s AND user_id IS NULL", (user_id, pnr))
        bookings_conn.execute("INSERT INTO chat_messages (conversation_id, role, content) SELECT id, %s, %s FROM conversations WHERE langgraph_thread_id=%s", ("user", request.message, request.thread_id))
        bookings_conn.execute("INSERT INTO chat_messages (conversation_id, role, content) SELECT id, %s, %s FROM conversations WHERE langgraph_thread_id=%s", ("assistant", response, request.thread_id))
        bookings_conn.execute("UPDATE conversations SET updated_at=now() WHERE langgraph_thread_id=%s", (request.thread_id,))
        return {"status": "success", "agent_response": response}
    except Exception as e:
        import traceback
        print("!!! ERROR IN CHAT ENDPOINT !!!")
        traceback.print_exc()
        err_str = str(e)
        # Groq occasionally rejects an otherwise valid tool call with a
        # `tool_use_failed` 400.  Recover route-search calls from the function
        # arguments it returned instead of showing the user a server error.
        if "tool_use_failed" in err_str and "search_trains" in err_str:
            match = re.search(r"<function=search_trains\((\{.*?\})\)</function>", err_str, re.DOTALL)
            if match:
                try:
                    from app.tools.trains import search_trains
                    arguments = json.loads(match.group(1))
                    response = search_trains.invoke(arguments)
                    if re.search(r"\b(book|booking|ticket)\b", request.message, re.IGNORECASE):
                        train_match = re.search(r"Train\s+(\d+)\s+\(([^)]+)\)", response)
                        class_match = re.search(r"(?:class|classes?)\s*(?:is|:|=)?\s*(1A|2A|3A|SL|CC|EC)", request.message, re.IGNORECASE)
                        selected_train = (
                            f"{train_match.group(2)} ({train_match.group(1)})"
                            if train_match else "the selected train"
                        )
                        selected_class = class_match.group(1).upper() if class_match else "your selected class"
                        natural_date = re.search(
                            r"\b(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December),?\s+(\d{4})\b",
                            request.message,
                            re.IGNORECASE,
                        )
                        if natural_date:
                            day, month_name, year = natural_date.groups()
                            journey_date = datetime.datetime.strptime(
                                f"{day} {month_name} {year}", "%d %B %Y"
                            ).date().isoformat()
                            response += (
                                f"\n\nI understood your booking details: {selected_train}, {selected_class}, journey date {journey_date}, "
                                "with the stated passenger and berth preferences. Please reply **Confirm booking** to create the ticket."
                            )
                        else:
                            response += (
                                f"\n\nI found {selected_train}. I have noted {selected_class} and the passenger/berth preferences. "
                                "Please provide the journey date in YYYY-MM-DD format and confirm this train, then I can continue with the booking."
                            )
                    return {"status": "success", "agent_response": response}
                except Exception:
                    pass
        if "Rate limit reached" in err_str or "429" in err_str:
            from app.tools.pnr import get_pnr_status
            pnr_match = re.search(r'\b\d{10}\b', request.message)
            if pnr_match:
                pnr_res = get_pnr_status.invoke({"pnr_number": pnr_match.group(0)})
                return {"status": "success", "agent_response": pnr_res}
            return {
                "status": "success",
                "agent_response": "The AI model is temporarily rate limited on tokens per day. Please try again in 1 minute or check your PNR."
            }
        raise HTTPException(status_code=500, detail="The assistant could not complete that request. Please try again.")


@router.post("/api/approve-complaint")
def approve_complaint(request: ApprovalRequest):
    """Resumes the LangGraph agent after a human approval decision."""
    ensure_thread_belongs_to_client(request.thread_id, request.client_id)
    config = {"configurable": {"thread_id": request.thread_id}}

    # Translate boolean to the "yes"/"no" expected by your graph logic
    decision = "yes" if request.approved else "no"

    try:
        # Resume the graph by passing the command
        result = graph.invoke(Command(resume={"approved": decision}), config=config)

        return {"status": "success", "agent_response": result["messages"][-1].content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
