"""
Railway Customer Support Agent — LangGraph + Postgres (Supabase) + Pinecone
==========================================================================
Stack: Python, LangChain (@tool + bind_tools), LangGraph, ChatGroq,
       Pinecone + HuggingFace embeddings (refund-policy RAG),
       Postgres via Supabase (bookings data + LangGraph checkpointer).

Requires DATABASE_URL, MOTHERDUCK_TOKEN (optional/unused), PINECONE_API_KEY,
and GROQ_API_KEY env vars.
"""

import os
import random
import re
import time
from datetime import date, timedelta
from pathlib import Path
import pandas as pd
from typing import Annotated, Any, Optional

import psycopg2
import psycopg2.errors
from dotenv import load_dotenv

from langchain_core.tools import tool
from langchain_core.messages import SystemMessage, ToolMessage
from langchain_groq import ChatGroq

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings

# Pinecone Integration
from pinecone import Pinecone, ServerlessSpec
from langchain_pinecone import Pinecone as PineconeVectorStore

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.types import interrupt, Command
from typing_extensions import TypedDict

# Load .env locally
load_dotenv()

# ----------------------------------------------------------------------
# 1. LOAD REFERENCE DATA (plain CSVs — read-only)
# ----------------------------------------------------------------------
DATA_DIR = Path(__file__).resolve().parent / "data"

stations_df = pd.read_csv(DATA_DIR / "stations.csv")
trains_df = pd.read_csv(DATA_DIR / "trains.csv")
schedules_df = pd.read_csv(DATA_DIR / "schedules.csv")

# ----------------------------------------------------------------------
# 2. BOOKING CONFIG
# ----------------------------------------------------------------------
BOOKING_WINDOW_START = date(2026, 7, 22)
BOOKING_WINDOW_END = date(2026, 9, 30)

NUM_COACHES = {"1A": 3, "2A": 3, "3A": 3, "SL": 3, "CC": 3, "EC": 2}
CLASS_CAPACITY = {"1A": 18, "2A": 46, "3A": 64, "SL": 72, "CC": 78, "EC": 56}

BERTH_CYCLE = [
    "Lower",
    "Middle",
    "Upper",
    "Lower",
    "Middle",
    "Upper",
    "Side Lower",
    "Side Upper",
]
VALID_BERTH_PREFS = {"lower", "middle", "upper", "side lower", "side upper"}

# ----------------------------------------------------------------------
# 3. POSTGRES (SUPABASE) CONNECTIONS
# ----------------------------------------------------------------------
DATABASE_URL = os.environ["DATABASE_URL"]  # raises loudly if missing — fail fast


class _SqliteStyleConn:
    """Shim so SQLite-style ? placeholders and conn.execute(...)
    calls work seamlessly against Postgres via psycopg2."""

    def __init__(self, dsn):
        self._dsn = dsn
        self._conn = psycopg2.connect(dsn)
        self._conn.autocommit = True  # avoid idle-in-transaction on reads

    def _ensure_connected(self):
        """Reconnect if the underlying connection was dropped."""
        try:
            if self._conn.closed != 0:
                self._conn = psycopg2.connect(self._dsn)
                self._conn.autocommit = True
        except Exception:
            self._conn = psycopg2.connect(self._dsn)
            self._conn.autocommit = True

    def execute(self, query, params=()) -> "Any":
        q_strip = query.strip().upper()
        if q_strip in ("BEGIN IMMEDIATE", "BEGIN TRANSACTION", "BEGIN"):
            self._conn.autocommit = False  # enter explicit transaction
            return self

        query = query.replace("?", "%s").replace("date('now')", "CURRENT_DATE")
        self._ensure_connected()
        try:
            cur = self._conn.cursor()
            cur.execute(query, params)
            return cur
        except Exception:
            # rollback and retry once with a fresh connection
            try:
                self._conn.rollback()
            except Exception:
                pass
            try:
                self._conn = psycopg2.connect(self._dsn)
                self._conn.autocommit = True
                cur = self._conn.cursor()
                cur.execute(query, params)
                return cur
            except Exception:
                raise

    def fetchone(self):
        return None

    def fetchall(self):
        return []

    def commit(self):
        self._conn.commit()
        self._conn.autocommit = True  # back to autocommit after explicit txn

    def rollback(self):
        self._conn.rollback()
        self._conn.autocommit = True  # back to autocommit after explicit txn


bookings_conn = _SqliteStyleConn(DATABASE_URL)

# PostgresSaver manages LangGraph thread checkpoints in Supabase
checkpointer_cm = PostgresSaver.from_conn_string(DATABASE_URL)
checkpointer = checkpointer_cm.__enter__()
checkpointer.setup()  # auto-creates checkpoint tables on first run

# ----------------------------------------------------------------------
# 3b. BUILD (OR LOAD) THE POLICY VECTOR STORE (PINECONE)
# ----------------------------------------------------------------------
POLICY_PDF_PATH = DATA_DIR / "refund_cancellation_policy.pdf"

PINECONE_API_KEY = os.environ["PINECONE_API_KEY"]
pc = Pinecone(api_key=PINECONE_API_KEY)

index_name = "railway-refund-policy"

if index_name not in pc.list_indexes().names():
    print(f"Creating Pinecone index '{index_name}'...")
    pc.create_index(
        name=index_name,
        dimension=384,
        metric="cosine",
        spec=ServerlessSpec(cloud="aws", region="us-east-1"),
    )
    while not pc.describe_index(index_name).status.ready:
        time.sleep(1)

pinecone_index = pc.Index(index_name)
embedding_model = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)
policy_vectorstore = PineconeVectorStore(
    index=pinecone_index, embedding=embedding_model
)

if pinecone_index.describe_index_stats()["total_vector_count"] == 0:
    print("Uploading refund policy documents to Pinecone...")
    pdf_pages = PyPDFLoader(str(POLICY_PDF_PATH)).load()
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    policy_chunks = text_splitter.split_documents(pdf_pages)
    policy_vectorstore.add_documents(policy_chunks)
    print("Upload complete!")


# ----------------------------------------------------------------------
# 4. SEAT-MAP & DATABASE HELPERS
# ----------------------------------------------------------------------
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
        m = re.match(rf"{re.escape(coach_name)}-(\d+)$", sb)
        if m:
            out.add(int(m.group(1)))
    return out


def _find_confirmed_seat(train_number, journey_date, travel_class, berth_pref):
    n_coaches = NUM_COACHES.get(travel_class, 3)
    seats_per_coach = CLASS_CAPACITY.get(travel_class, 64) // n_coaches
    fallback = None
    for c in range(1, n_coaches + 1):
        coach_name = f"{travel_class}{c}"
        occupied = _occupied_seat_indices(train_number, journey_date, coach_name)
        for idx in range(1, seats_per_coach + 1):
            if idx in occupied:
                continue
            berth = BERTH_CYCLE[(idx - 1) % 8]
            seat_berth = f"{coach_name}-{idx}"
            if berth_pref is None or berth.lower() == berth_pref.lower():
                return coach_name, seat_berth, berth, True
            if fallback is None:
                fallback = (coach_name, seat_berth, berth)
    if fallback:
        return fallback[0], fallback[1], fallback[2], False
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


# ----------------------------------------------------------------------
# 5. TOOLS
# ----------------------------------------------------------------------
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
def search_refund_policy(query: str) -> str:
    """Search the refund/cancellation policy document using Pinecone RAG."""
    results = policy_vectorstore.similarity_search(query, k=2)
    if not results:
        return "No relevant policy information found. Try rephrasing your question."
    return "\n\n---\n\n".join(r.page_content.strip() for r in results)


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

    capacity = CLASS_CAPACITY[travel_class]
    confirmed = bookings_conn.execute(
        """SELECT COUNT(*) FROM bookings
           WHERE train_number = ? AND journey_date = ? AND class = ?
                 AND current_status = 'CNF'""",
        (train_number, journey_date, travel_class),
    ).fetchone()[0]
    rac_taken = bookings_conn.execute(
        """SELECT COUNT(*) FROM bookings
           WHERE train_number = ? AND journey_date = ? AND class = ?
                 AND current_status = 'RAC'""",
        (train_number, journey_date, travel_class),
    ).fetchone()[0]
    wl_count = bookings_conn.execute(
        """SELECT COUNT(*) FROM bookings
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


@tool
def book_ticket(
    passenger_name: str,
    train_number: str,
    journey_date: str,
    travel_class: str,
    berth_preference: Optional[str] = None,
    num_passengers: int = 1,
    age: Optional[int] = None,
    gender: Optional[str] = None,
) -> str:
    """Book a new ticket with automatic fallback to RAC or Waitlist."""
    date_error = _validate_journey_date(journey_date)
    if date_error:
        return date_error

    travel_class = travel_class.strip().upper()
    if travel_class not in CLASS_CAPACITY:
        return f"Unknown class '{travel_class}'. Valid classes: {', '.join(CLASS_CAPACITY)}."

    if (
        berth_preference is not None
        and berth_preference.strip().lower() not in VALID_BERTH_PREFS
    ):
        return f"Unknown berth preference '{berth_preference}'. Valid options: Lower, Middle, Upper, Side Lower, Side Upper."

    train_row = trains_df[trains_df["train_number"] == int(train_number)]
    if train_row.empty:
        return f"Train number {train_number} not found."
    train_name = train_row.iloc[0]["train_name"]
    source_code = train_row.iloc[0]["source_code"]
    destination_code = train_row.iloc[0]["destination_code"]

    bookings_conn.execute("BEGIN TRANSACTION")
    try:
        seat = _find_confirmed_seat(
            train_number, journey_date, travel_class, berth_preference
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
                0,
                age,
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
def cancel_ticket(pnr_number: str) -> str:
    """Cancel an existing booking by PNR number with automatic cascading promotions."""
    pnr_number = pnr_number.strip()

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


@tool
def file_complaint(category: str, description: str) -> str:
    """File a customer complaint."""
    raise NotImplementedError("Handled by complaint_approval_node instead.")


TOOLS = [
    get_pnr_status,
    search_trains,
    get_train_schedule,
    search_refund_policy,
    check_seat_availability,
    book_ticket,
    cancel_ticket,
    file_complaint,
]

# ----------------------------------------------------------------------
# 6. LLM (ChatGroq) + bind_tools
# ----------------------------------------------------------------------
llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)
llm_with_tools = llm.bind_tools(TOOLS)

SYSTEM_PROMPT = f"""You are a helpful Indian Railways customer support assistant,
behaving like the IRCTC booking system. You can check PNR status, search trains,
get train schedules, look up refund/cancellation policy, check seat availability,
book new tickets, cancel tickets, and file complaints.

Bookings are only open for journey dates from {BOOKING_WINDOW_START.isoformat()}
through {BOOKING_WINDOW_END.isoformat()}. If a user asks about a date outside
this window, tell them clearly instead of guessing.

Before booking, confirm train number, journey date, and class with the user,
and ask if they have a berth preference (Lower/Middle/Upper/Side Lower/Side
Upper) — it's optional but worth asking, like IRCTC does.
Before cancelling, confirm the PNR number with the user.
Use the tools available to answer accurately — never guess PNR status,
schedules, seat availability, or policy details.
If a query is ambiguous, ask a brief clarifying question before choosing a tool.
Always confirm complaint details with the user in your own words before
calling file_complaint, since that tool requires a human approval step."""


# ----------------------------------------------------------------------
# 7. STATE + GRAPH
# ----------------------------------------------------------------------
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]


def agent_node(state: AgentState):
    system_message = SystemMessage(content=SYSTEM_PROMPT)
    messages = [system_message, *state["messages"]]
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}


def complaint_approval_node(state: AgentState):
    last_message = state["messages"][-1]
    tool_call = last_message.tool_calls[0]
    category = tool_call["args"]["category"]
    description = tool_call["args"]["description"]

    decision = interrupt(
        {
            "type": "approval",
            "reason": "Agent wants to file a complaint on your behalf.",
            "category": category,
            "description": description,
            "instruction": "Approve this complaint? yes/no",
        }
    )

    if decision["approved"] == "no":
        result_text = "Complaint was not approved, so it was not filed."
    else:
        ticket_number = random.randint(10000, 99999)
        ticket_id = f"TCK-{ticket_number}"
        result_text = (
            f"Complaint filed successfully. Ticket ID: {ticket_id}. "
            f"Category: {category}. Description: {description}."
        )

    tool_message = ToolMessage(content=result_text, tool_call_id=tool_call["id"])
    return {"messages": [tool_message]}


def route_after_agent(state: AgentState):
    last_message = state["messages"][-1]
    tool_calls = last_message.tool_calls

    if not tool_calls:
        return END
    if tool_calls[0]["name"] == "file_complaint":
        return "complaint_approval"
    return "tools"


graph_builder = StateGraph(AgentState)
graph_builder.add_node("agent", agent_node)
graph_builder.add_node("tools", ToolNode(TOOLS))
graph_builder.add_node("complaint_approval", complaint_approval_node)

graph_builder.add_edge(START, "agent")
graph_builder.add_conditional_edges(
    "agent",
    route_after_agent,
    {"tools": "tools", "complaint_approval": "complaint_approval", END: END},
)
graph_builder.add_edge("tools", "agent")
graph_builder.add_edge("complaint_approval", "agent")

graph = graph_builder.compile(checkpointer=checkpointer)


def retrieve_all_threads():
    all_threads = set()
    for checkpoint in checkpointer.list(None):
        all_threads.add(checkpoint.config["configurable"]["thread_id"])  # type: ignore[typeddict-item]
    return list(all_threads)


# ----------------------------------------------------------------------
# 8. INTERACTIVE CHAT TERMINAL
# ----------------------------------------------------------------------
if __name__ == "__main__":
    print("🚂 Welcome to the Railway Support Agent! Type 'exit' to quit.\n")

    # Static thread ID for local testing
    config = {"configurable": {"thread_id": "terminal_session_1"}}

    while True:
        user_input = input("You: ")
        if user_input.strip().lower() in ["exit", "quit", "q"]:
            print("Goodbye!")
            break

        # Invoke the graph with input
        result = graph.invoke({"messages": [("user", user_input)]}, config=config)  # type: ignore[arg-type]

        # Handle complaint approval interrupts
        if "__interrupt__" in result:
            interrupt_data = result["__interrupt__"][0].value
            print(f"\n[System Pause: {interrupt_data['reason']}]")
            print(f"Complaint Category: {interrupt_data['category']}")
            print(f"Complaint Details: {interrupt_data['description']}")

            approval = input(f"{interrupt_data['instruction']} ")
            resume_status = "yes" if approval.strip().lower() == "yes" else "no"

            # Resume graph execution
            result = graph.invoke(
                Command(resume={"approved": resume_status}), config=config  # type: ignore[arg-type]
            )

        # Output agent response
        print(f"Agent: {result['messages'][-1].content}\n")
