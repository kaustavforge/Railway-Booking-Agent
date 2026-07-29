Here is a `README.md` template based on the exact steps we just went through. You can copy and paste this into a `README.md` file in your project folder so you have a perfect reference for the future!

---

# Supabase Setup Guide for Python Agents

This guide outlines the steps to connect a Python-based LangGraph/LangChain agent to a Supabase PostgreSQL database for persistent storage and memory.

## Step 1: Get Your Connection String

1. Log in to your [Supabase Dashboard](https://www.google.com/search?q=https://supabase.com/dashboard) and select your project.
2. Click the **Connect** button at the top of the page.
3. In the connection menu, select the **Direct** tab (underneath it, it says "Connection string").
4. Under the "Connection Method" section, ensure **Direct connection** is selected.
5. In the dark grey box, locate the URI connection string. It will look something like this:
`postgresql://postgres:[YOUR-PASSWORD]@db.yourprojectref.supabase.co:5432/postgres`
6. Click **Copy prompt** or manually copy that exact string.

## Step 2: Configure Environment Variables

1. In the root directory of your project, create a file named `.env`.
2. Paste the connection string you copied into the file, assigning it to the `DATABASE_URL` variable.
3. **Important:** Replace the literal text `[YOUR-PASSWORD]` (including the square brackets) with your actual database password.

**Example `.env` file:**

```env
# Database connection
DATABASE_URL=postgresql://postgres:mySuperSecretPassword123@db.uzgqsycnqwfskdlphsao.supabase.co:5432/postgres

# Other API Keys
PINECONE_API_KEY=your_pinecone_key_here
GROQ_API_KEY=your_groq_key_here

```

## Step 3: Run Database Migrations

Before running the main application, you must initialize the database schema (tables, unique indexes, etc.) and set up any required vector database indexes (like Pinecone).

Run the migration script in your terminal:

```bash
python migrate_to_supabase.py

```

*Wait for the terminal to confirm that the tables were successfully created and the vector data (if applicable) was uploaded.*

## Step 4: Run the Agent

Once the database is configured and the migration is complete, you can start the main application.

Run the agent script:

```bash
python railway_agent_prototype.py

```

## Troubleshooting

* **Authentication Errors:** Double-check your `.env` file. Ensure there are no brackets `[]` around your password and no spaces around the `=` sign.
* **Special Characters in Password:** If your database password has special characters (like `@`, `#`, or `/`), you may need to percent-encode them in the connection string.