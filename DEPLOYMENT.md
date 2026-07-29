# Deploying chat history safely

1. Deploy the FastAPI service to Render with the same `DATABASE_URL` that points to your Supabase Postgres database. The database, rather than Render's local filesystem, stores the chat checkpoints.
2. In Render, set `FRONTEND_ORIGINS` to your Vercel URL, for example `https://railbot.vercel.app`. Add comma-separated values if you use preview domains.
3. Before deploying `frontend` to Vercel, set `window.RAILBOT_API_BASE` in `frontend/js/config.js` to your Render public URL, for example `https://railbot-api.onrender.com`. Do not include a trailing slash.
4. Deploy the frontend. Open it once in each browser to create its anonymous browser identity.

The current app uses an anonymous browser identity to separate conversations. It persists chats in Supabase and restores them for the same browser and site origin. It does not provide account-based recovery across browsers, devices, or a local-to-Vercel move. Add Supabase Auth and use the verified user ID in the API if you need those capabilities.

Existing `session_*` conversations cannot safely be assigned to an anonymous browser because the old app saved no owner. They are intentionally excluded from the new history list so one visitor cannot see another visitor's conversations.
