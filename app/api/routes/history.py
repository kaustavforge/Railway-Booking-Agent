"""
Chat history endpoint.
"""

import datetime

from fastapi import APIRouter, HTTPException, Depends

from app.agent.graph import graph
from app.api.schemas import ChatHistoryResponse, HistoryMessage, LegacyMigrationRequest
from app.api.routes.chat import ensure_thread_belongs_to_client
from app.api.auth import current_user_id

router = APIRouter()


@router.get("/api/history/{thread_id}", response_model=ChatHistoryResponse)
def get_chat_history(thread_id: str, user_id: str = Depends(current_user_id)):
    """
    Fetches the conversation history for a specific thread_id from LangGraph.
    """
    try:
        from app.database.connection import bookings_conn
        owner = bookings_conn.execute("SELECT 1 FROM conversations WHERE langgraph_thread_id=%s AND user_id=%s", (thread_id, user_id)).fetchone()
        if not owner: raise HTTPException(404, "Conversation not found")
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


@router.get("/api/sessions")
def get_all_sessions(user_id: str = Depends(current_user_id)):
    """
    Fetches all distinct thread_ids and their titles from Supabase checkpoints.
    """
    try:
        from app.database.connection import bookings_conn
        # LangGraph checkpoint ids are time-sortable.  Use them for recovered
        # conversations so a bulk recovery does not make every old chat look new.
        rows = bookings_conn.execute(
            """SELECT c.langgraph_thread_id, c.title, c.updated_at,
                      MAX(cp.checkpoint_id::text) AS last_checkpoint
               FROM conversations c
               LEFT JOIN checkpoints cp ON cp.thread_id = c.langgraph_thread_id
               WHERE c.user_id=%s
               GROUP BY c.id, c.langgraph_thread_id, c.title, c.updated_at
               ORDER BY MAX(cp.checkpoint_id::text) DESC NULLS LAST, c.updated_at DESC
               LIMIT 25""",
            (user_id,),
        ).fetchall()

        sessions = []
        for row in rows:
            if not row or not row[0]:
                continue
            tid = str(row[0])
            cfg = {"configurable": {"thread_id": tid}}
            try:
                st = graph.get_state(cfg)
                if st and st.values and "messages" in st.values:
                    msgs = [m for m in st.values["messages"] if hasattr(m, 'type') and m.type in ("human", "ai") and m.content]
                    if msgs:
                        first_content = msgs[0].content
                        if isinstance(first_content, list):
                            first_text = "".join([i.get("text", "") if isinstance(i, dict) else str(i) for i in first_content])
                        else:
                            first_text = str(first_content)
                        first_text = first_text.strip()
                        if first_text:
                            title = first_text[:28] + ("..." if len(first_text) > 28 else "")
                            # Recovered records initially have a placeholder title.
                            # The first user message is the useful ChatGPT-style title.
                            sessions.append({"threadId": tid, "title": title, "updatedAt": row[2].isoformat() if row[2] else None, "sortKey": row[3]})
            except Exception as ex:
                print(f"Error state for {tid}: {ex}")
                continue

        return {"status": "success", "sessions": sessions}
    except Exception as e:
        import traceback
        print(f"Error fetching sessions: {e}")
        traceback.print_exc()
        return {"status": "error", "sessions": []}


@router.post("/api/history/migrate-legacy")
def migrate_legacy_sessions(request: LegacyMigrationRequest, user_id: str = Depends(current_user_id)):
    """One-time recovery for old session IDs found in this browser's localStorage."""
    from app.database.connection import bookings_conn
    import uuid

    migrated = 0
    for thread_id in set(request.thread_ids[:50]):
        if not thread_id.startswith("session_"):
            continue
        exists = bookings_conn.execute(
            "SELECT 1 FROM checkpoints WHERE thread_id=%s LIMIT 1", (thread_id,)
        ).fetchone()
        if not exists:
            continue
        bookings_conn.execute(
            """INSERT INTO conversations (id, user_id, langgraph_thread_id, title)
               VALUES (%s, %s, %s, %s) ON CONFLICT (langgraph_thread_id) DO NOTHING""",
            (str(uuid.uuid4()), user_id, thread_id, "Recovered chat"),
        )
        migrated += 1
    return {"status": "success", "migrated": migrated}


@router.delete("/api/conversations/{thread_id}")
def delete_conversation(thread_id: str, user_id: str = Depends(current_user_id)):
    """Permanently delete one signed-in user's visible chat and LangGraph state."""
    from app.database.connection import bookings_conn

    conversation = bookings_conn.execute(
        "SELECT id FROM conversations WHERE langgraph_thread_id=%s AND user_id=%s",
        (thread_id, user_id),
    ).fetchone()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Delete user-visible data first, then the agent checkpoints for this thread.
    bookings_conn.execute("DELETE FROM chat_messages WHERE conversation_id=%s", (conversation[0],))
    bookings_conn.execute("DELETE FROM conversations WHERE id=%s", (conversation[0],))
    bookings_conn.execute("DELETE FROM checkpoint_writes WHERE thread_id=%s", (thread_id,))
    bookings_conn.execute("DELETE FROM checkpoints WHERE thread_id=%s", (thread_id,))
    return {"status": "success"}
