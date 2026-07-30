# Rail Assist AI — Step-by-Step Implementation Guide

This guide describes a practical build order for recreating the project from an empty repository. Each phase produces a testable result before the next module is added.

## Phase 0 — Define the scope

Decide the first release capabilities:

- Train search and availability
- PNR lookup
- Policy/RAG answers
- Solo and family demo booking
- Cancellation and complaint approval
- Authenticated conversations
- Ticket PDF generation

Keep the first version simulated. Do not connect to real railway booking systems or store real payment information.

## Phase 1 — Create the repository and Python environment

Create this initial structure:

```text
project/
├── app/
│   ├── __init__.py
│   ├── api/
│   ├── agent/
│   ├── config/
│   ├── database/
│   ├── services/
│   └── tools/
├── data/
├── frontend/
├── requirements.txt
├── .env.example
└── .gitignore
```

Add `requirements.txt` with FastAPI, Uvicorn, Pydantic, LangChain, LangGraph, the Groq integration, database drivers, retrieval libraries, pandas, ReportLab, QRCode, and Pillow.

Create the virtual environment and install dependencies:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Phase 2 — Add configuration and railway data

Create:

- `app/config/settings.py` — environment loading, model settings, class capacities
- `data/trains.csv` — train number, name, source, destination, classes, running days
- `data/schedules.csv` — departure and arrival times, duration, next-day arrival
- `data/stations.csv` — station codes and names

Add `.env.example`:

```env
DATABASE_URL=your_supabase_session_pooler_connection_string
GROQ_API_KEY=
PINECONE_API_KEY=
SUPABASE_URL=
SUPABASE_ANON_KEY=
FRONTEND_ORIGINS=http://localhost:5500
```

Test that configuration loads without starting the full agent.

## Phase 3 — Build the FastAPI shell

Create:

- `app/api/main.py` — FastAPI application and CORS middleware
- `app/api/schemas.py` — request/response Pydantic models
- `app/api/auth.py` — Supabase access-token verification

Add a health endpoint such as `GET /health`, then run:

```bash
uvicorn app.api.main:app --reload --port 8000
```

Verify the Swagger page at `http://localhost:8000/docs`.

## Phase 4 — Add the database schema

Create:

- `app/database/connection.py` — PostgreSQL connection setup
- `supabase_chat_schema.sql` — conversations and chat messages
- `supabase_family_booking_migration.sql` — booking ownership, passenger count, and family-booking fields
- `scripts/migrate_to_supabase.py` — optional legacy SQLite import

Follow the setup order below. The optional SQLite import must happen before the family-booking migration because the import script creates the base `bookings` table.

### Supabase project setup

1. Create a project at [supabase.com](https://supabase.com).
2. Open **Connect → Database** and choose **Session pooler**. Copy the PostgreSQL connection string and put it in the backend `.env` as `DATABASE_URL`. The session pooler is recommended for Render because it provides an IPv4 connection path; the direct `db.<project>.supabase.co` host can fail on IPv6-unavailable services.
3. Open **SQL Editor** and run `supabase_chat_schema.sql` once.
4. If you have `pnr_bookings.db`, run `scripts/migrate_to_supabase.py` from the project root. If you do not have an old SQLite database, run the script anyway to create an empty base `bookings` table, or create that base table separately.
5. Run `supabase_family_booking_migration.sql` once. This adds the current family-booking fields and authenticated `user_id` ownership column.
6. Confirm these tables exist in **Table Editor**:

   - `conversations`
   - `chat_messages`
   - `bookings`
   - `checkpoints` and related LangGraph checkpoint tables, if used by the configured checkpointer

7. Do not upload a local SQLite database file to Supabase. The Python migration reads it and copies its rows into PostgreSQL; the `.db` file itself is not uploaded.
8. If the project contains local CSV/reference data, keep those files in the repository under `data/`; they are not database migrations.

Keep the completed connection string private. URL-encode special characters in the database password, use the same pooler URL in Render’s `DATABASE_URL`, and rotate the database password if it has been exposed.

### Supabase authentication setup

1. Open **Authentication → Sign In / Providers**.
2. Keep the **Email** provider enabled.
3. Enable or disable **Confirm email** according to your testing needs. For a portfolio demo, disabling it makes local testing easier; enable it for a real public deployment.
4. Add the Supabase project URL and publishable/anon key to the backend environment and `frontend/js/config.js`.
5. Use the publishable/anon key in the browser only. Never use the `service_role` or secret key in frontend code.
6. Configure **Authentication → URL Configuration** with the deployed Vercel URL as the Site URL. Add local URLs as redirect URLs if email confirmation is enabled.
7. The frontend signs users in with email/password and sends the resulting access token as `Authorization: Bearer <token>` to FastAPI.
8. FastAPI verifies the token, obtains the Supabase user ID, and uses that ID to filter conversations and bookings. A user must never be able to request another user’s chat or PNR by changing a URL.

### Database ownership and existing records

New bookings and conversations are assigned to the authenticated user automatically. Existing bookings created before authentication may have a null `user_id`; they must be assigned carefully through an approved migration or recreated for the signed-in test account before protected PNR details and downloads can access them.

### Migrating an existing `pnr_bookings.db` file

If you already have the old SQLite file `pnr_bookings.db`, use:

```text
scripts/migrate_to_supabase.py
```

That script connects to the Supabase PostgreSQL database using `DATABASE_URL`, creates/verifies the legacy `bookings` table and indexes, then copies rows from:

```text
scripts/data/pnr_bookings.db
```

Before running it:

1. Ensure the SQLite file is actually at `scripts/data/pnr_bookings.db` (or update the script’s `local_db_path` to your real location).
2. Ensure `DATABASE_URL` is present in `.env`.
3. Run `supabase_chat_schema.sql` first, then run this script to create/import the base `bookings` table, and finally run `supabase_family_booking_migration.sql` to add the current columns.
4. Run:

   ```bash
   python scripts/migrate_to_supabase.py
   ```

5. Verify the imported rows in Supabase Table Editor or with `SELECT COUNT(*) FROM public.bookings;`.

This is a one-time data migration. Do not upload the `.db` file to Vercel or Render, and do not commit it if it contains real personal data. After migration, the deployed FastAPI service reads and writes Supabase directly through `DATABASE_URL`.

## Phase 5 — Implement railway tools before the LLM

Create tools independently and test them with ordinary Python calls:

- `app/tools/trains.py` — train search and availability
- `app/tools/pnr.py` — PNR lookup
- `app/tools/policy.py` — policy retrieval
- `app/tools/booking.py` — booking and cancellation

Add service helpers:

- `app/services/seat_allocation.py` — confirmed, RAC, and waitlist allocation
- `app/services/date_utils.py` — date parsing and next-day arrival calculation

Each tool should validate its arguments, return predictable text/structured data, and never depend on the LLM to enforce business rules.

## Phase 6 — Add policy retrieval (RAG)

Create:

- `data/policies/` — railway policy documents
- `app/services/retrieval.py` — chunking, embeddings, and vector search
- `scripts/reindex_policies_fastembed.py` — explicit Pinecone reset and ingestion

Use FastEmbed rather than the heavier local Sentence Transformers/PyTorch stack. `app/config/settings.py` uses `BAAI/bge-small-en-v1.5`, which produces 384-dimensional vectors matching the dedicated Pinecone index. The dependency files include `fastembed` and no longer require `sentence-transformers`.

After changing embedding models, recreate and re-index the dedicated policy index:

```bash
python scripts/reindex_policies_fastembed.py --reset
```

This command is intentionally destructive for `railway-refund-policy`; never point it at an index containing unrelated data.

Test retrieval with questions such as refund rules, cancellation windows, and delay compensation. The assistant must say when a policy answer cannot be found. The current backend test retrieved two relevant chunks from six indexed policy vectors.

## Phase 7 — Build the LangGraph agent

Create:

- `app/agent/prompts.py` — system rules and safety instructions
- `app/agent/state.py` — graph state definitions
- `app/agent/nodes.py` — LLM and tool nodes
- `app/agent/graph.py` — graph construction and checkpointer configuration

Add explicit rules for:

- Confirmation before booking, cancellation, and complaints
- Ownership checks
- No availability claim without calling availability
- No invented PNR, fare, seat, or status
- Out-of-context refusal
- Prompt-injection resistance

Test the graph with mocked tool calls before connecting it to HTTP.

## Phase 8 — Add API routes

Create:

- `app/api/routes/chat.py` — authenticated chat and persistence
- `app/api/routes/history.py` — list, load, and delete conversations
- `app/api/routes/pnr.py` — owned PNR details
- `app/api/routes/tickets.py` — owned PDF download

Register every router in `app/api/main.py`. Use generic user-facing errors and keep stack traces in server logs only.

## Phase 9 — Generate ticket PDFs

Create:

- `app/services/pdf_generator.py`

Include one PNR for a family booking, all passengers, train details, journey dates/times, class, seats, fare, status, and a QR code. Test solo and family PDFs locally before connecting the download endpoint.

## Phase 10 — Build the frontend

Create:

- `frontend/index.html` — layout and chat interface
- `frontend/css/` — visual styling
- `frontend/js/config.js` — API and Supabase public configuration
- `frontend/js/auth.js` — sign-in, sign-up, and sign-out
- `frontend/js/app.js` — chat, sessions, history, deletion, and ticket download
- `frontend/js/tickets.js` — ticket-card rendering

Implement in this order:

1. Sign-in and sign-up
2. New conversation screen
3. Send/receive chat messages
4. Conversation history ordered newest first
5. Conversation deletion
6. PNR cards and authenticated PDF download

Use the Supabase publishable/anon key only. Never expose a secret/service-role key in browser code.

## Phase 11 — Test locally

Run these checks before deployment:

```bash
python -m compileall -q app
git diff --check
```

Manually test:

- New user sign-up and returning user sign-in
- A new chat opening without auto-loading an old conversation
- History ordering and deletion
- Train search and availability
- Policy/RAG questions
- Solo booking and family booking
- Confirmation refusal when confirmation is absent
- Cancellation ownership and confirmation
- Complaint human approval
- PNR lookup and ticket download
- Invalid dates, classes, PNRs, ages, and passenger counts
- Out-of-context personal questions

## Phase 12 — Deploy the backend to Render

Push the repository to GitHub, then create a Render Web Service.

```text
Build command: pip install -r requirements.txt
Start command: uvicorn app.api.main:app --host 0.0.0.0 --port $PORT
```

Add these Render environment variables:

```text
DATABASE_URL
GROQ_API_KEY
PINECONE_API_KEY
SUPABASE_URL
SUPABASE_ANON_KEY
FRONTEND_ORIGINS
```

Initially set `FRONTEND_ORIGINS` to your local frontend origin if needed. Set `PYTHON_VERSION=3.11.11` in Render and verify the deployed API at `/docs`.

## Phase 13 — Deploy the frontend to Vercel

1. Update `frontend/js/config.js` with the Render URL:

   ```javascript
   window.RAILBOT_API_BASE = "https://your-api.onrender.com";
   ```

2. Commit and push the change.
3. Import the repository into Vercel.
4. Set the Vercel Root Directory to `frontend`.
5. Use the **Other** framework preset with no build command.
6. Deploy the static frontend.

Finally, set Render’s `FRONTEND_ORIGINS` to the final Vercel URL and redeploy Render.

## Final production checklist

- `.env` is excluded from Git
- No service-role key appears in frontend files
- Supabase migrations are applied
- Render `/docs` opens successfully
- CORS allows only the required Vercel/local origins
- Authenticated users can see only their own chats and bookings
- Ticket downloads work from the deployed domain
- Render logs contain no leaked API keys or passwords
- README and deployment documentation are up to date
