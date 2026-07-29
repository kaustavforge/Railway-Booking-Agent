import sqlite3
import psycopg2
import psycopg2.extras
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    print("Error: DATABASE_URL not found in .env file.")
    exit(1)

print("Connecting to Supabase Postgres...")
pg_conn = psycopg2.connect(DATABASE_URL)
pg_cur = pg_conn.cursor()

# --- STEP 1: CREATE TABLE & INDEXES ---
print("Setting up table schema and partial unique index...")

pg_cur.execute("""
CREATE TABLE IF NOT EXISTS bookings (
    pnr_number       TEXT PRIMARY KEY,
    passenger_name   TEXT NOT NULL,
    train_number     INTEGER NOT NULL,
    train_name       TEXT NOT NULL,
    source_code      TEXT NOT NULL,
    destination_code TEXT NOT NULL,
    journey_date     TEXT NOT NULL,
    class            TEXT NOT NULL,
    booking_status   TEXT NOT NULL,
    current_status   TEXT NOT NULL,
    coach            TEXT,
    seat_berth       TEXT,
    berth_type       TEXT,
    num_passengers   INTEGER NOT NULL,
    fare_inr         INTEGER NOT NULL,
    booking_date     TEXT NOT NULL,
    age              INTEGER,
    gender           TEXT
);
""")

# Index for fast availability lookups
pg_cur.execute("""
CREATE INDEX IF NOT EXISTS idx_train_date_class 
ON bookings (train_number, journey_date, class);
""")

# Partial unique index: Prevents two CNF tickets on the same seat,
# while allowing multiple cancelled (CAN), waitlisted (WL), or RAC records.
pg_cur.execute("""
CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_confirmed_seat 
ON bookings (train_number, journey_date, coach, seat_berth) 
WHERE current_status = 'CNF';
""")

pg_conn.commit()
print("Schema and indexes verified successfully.")

# --- STEP 2: MIGRATE LOCAL DATA ---
local_db_path = Path(__file__).resolve().parent / "data" / "pnr_bookings.db"

if local_db_path.exists():
    print(f"Reading local data from {local_db_path}...")
    sqlite_conn = sqlite3.connect(local_db_path)
    sqlite_cur = sqlite_conn.cursor()

    sqlite_cur.execute("SELECT * FROM bookings")
    rows = sqlite_cur.fetchall()
    columns = [d[0] for d in sqlite_cur.description]
    print(f"Found {len(rows)} local rows.")

    if rows:
        col_names = ", ".join(columns)
        placeholders = ", ".join(["%s"] * len(columns))

        insert_sql = f"""
        INSERT INTO bookings ({col_names})
        VALUES ({placeholders})
        ON CONFLICT (pnr_number) DO UPDATE SET
            age = EXCLUDED.age,
            gender = EXCLUDED.gender;
        """

        psycopg2.extras.execute_batch(pg_cur, insert_sql, rows)
        pg_conn.commit()
        print("Data migration complete!")

    sqlite_conn.close()
else:
    print(f"No local database found at {local_db_path}. Table initialized empty.")

pg_cur.close()
pg_conn.close()
