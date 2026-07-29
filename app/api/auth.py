"""Supabase Auth verification for API requests."""
import os
import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from fastapi import Header, HTTPException

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")

def current_user_id(authorization: str | None = Header(default=None)) -> str:
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        raise HTTPException(500, "Supabase Auth is not configured")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Please sign in")
    request = Request(f"{SUPABASE_URL}/auth/v1/user", headers={
        "apikey": SUPABASE_ANON_KEY, "Authorization": authorization,
    })
    try:
        with urlopen(request, timeout=8) as response:
            return json.loads(response.read())["id"]
    except (HTTPError, KeyError, json.JSONDecodeError):
        raise HTTPException(401, "Your login session is invalid or expired")
