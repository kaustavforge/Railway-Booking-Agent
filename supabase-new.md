# Supabase Auth and Chat History Setup

This project uses Supabase Auth for email/password accounts and Supabase Postgres for chat history, LangGraph checkpoints, bookings, and tickets.

## 1. Enable email authentication

In Supabase Dashboard:

1. Open **Authentication → Sign In / Providers**.
2. Keep **Allow new users to sign up** enabled.
3. Keep the **Email** provider enabled.
4. For local testing, **Confirm email** may be disabled. Enable it for production if you want users to verify their email.
5. Keep anonymous sign-ins disabled because this app uses email accounts.

## 2. Create the user chat tables

Open **SQL Editor**, paste and run:

```sql
-- Use the complete file from the repository:
-- supabase_chat_schema.sql
```

This creates:

- `public.conversations`: one conversation owner and LangGraph thread ID
- `public.chat_messages`: visible user and assistant messages
- indexes for history loading
- Row Level Security enabled on both tables

The FastAPI server accesses these tables through `DATABASE_URL`; the browser does not use the service-role key.

## 3. Family booking schema migration

Run this once if family tickets should store multiple ages in one PNR:

```sql
-- Complete file: supabase_family_booking_migration.sql
ALTER TABLE public.bookings
  ALTER COLUMN age TYPE TEXT USING age::TEXT;
```

This keeps a solo age as `26` and allows family ages such as `26, 50`.

The same migration adds `bookings.user_id`, which protects PNR details,
ticket downloads, and cancellations. To attach existing bookings to your own
account, run this only for records that belong to you:

```sql
UPDATE public.bookings
SET user_id = (SELECT id FROM auth.users WHERE email = 'your-login-email@example.com')
WHERE user_id IS NULL;
```

## 4. Copy Supabase API values

Open **Project Settings → API** and copy:

- Project URL, for example `https://your-project.supabase.co`
- Publishable/anon key

Never copy the `service_role` or secret key into frontend code or GitHub.

Set the frontend values in `frontend/js/config.js`:

```js
window.RAILBOT_API_BASE = "http://localhost:8000";
window.RAILBOT_SUPABASE_URL = "https://your-project.supabase.co";
window.RAILBOT_SUPABASE_ANON_KEY = "your-publishable-key";
```

The publishable key is intended for browser use. It is safe only when database access is protected by authentication/RLS and server ownership checks.

## 5. Local FastAPI environment

Keep these values in the root `.env` file. Do not commit `.env`:

```env
DATABASE_URL=your-supabase-postgres-connection-string
PINECONE_API_KEY=your-pinecone-key
GROQ_API_KEY=your-groq-key
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-publishable-key
FRONTEND_ORIGINS=http://localhost:3000,http://localhost:5500,http://127.0.0.1:5500,null
```

`null` is only for the current local `file:///frontend/index.html` testing. Do not use it in production.

Start the backend from the project root:

```powershell
uvicorn app.api.main:app --reload
```

Then open the frontend in the same browser used for old chats. The first login creates or restores a Supabase Auth session. Old `session_*` chats can be migrated only while their old browser session IDs are still available.

## 6. How authorization works

1. Supabase JavaScript Auth signs the user in and stores a session in that browser.
2. The frontend obtains the Supabase access token.
3. API requests send `Authorization: Bearer <access-token>`.
4. FastAPI calls Supabase Auth to validate the token and obtain the trusted user ID.
5. Conversations are stored with that user ID.
6. History and deletion queries require that same user ID, so another account cannot read or delete the conversation.
7. LangGraph continues using its thread ID for agent context; the conversation tables provide the account-owned visible history.

## 7. Recover old chats

Old chats were created with unowned IDs such as `session_xxxxx`. If those IDs are still present in the old browser, the app can migrate them after login.

If automatic recovery does not find them, check Supabase:

```sql
SELECT DISTINCT thread_id
FROM checkpoints
WHERE thread_id LIKE 'session_%'
ORDER BY thread_id;
```

Only assign old threads to your account if they are all yours:

```sql
INSERT INTO public.conversations (id, user_id, langgraph_thread_id, title)
SELECT gen_random_uuid(), u.id, c.thread_id, 'Recovered chat'
FROM (
  SELECT DISTINCT thread_id
  FROM checkpoints
  WHERE thread_id LIKE 'session_%'
) c
CROSS JOIN auth.users u
WHERE u.email = 'your-login-email@example.com'
ON CONFLICT (langgraph_thread_id) DO NOTHING;
```

## 8. Deployment values

For Render, set the backend secrets in the Render Environment page:

```env
DATABASE_URL=...
PINECONE_API_KEY=...
GROQ_API_KEY=...
SUPABASE_URL=...
SUPABASE_ANON_KEY=...
FRONTEND_ORIGINS=https://your-vercel-site.vercel.app
```

For Vercel, update `frontend/js/config.js` so `RAILBOT_API_BASE` is the Render public URL. Do not use `localhost` after deployment.

After changing environment variables, redeploy the service. Test with two different email accounts: each account must see only its own history.
