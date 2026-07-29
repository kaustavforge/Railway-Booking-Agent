"""
FastAPI application entry point.
"""

import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import chat, pnr, history, tickets

# Load local CORS configuration before the middleware is created.
load_dotenv()

app = FastAPI(title="RailBot AI API")

# Configure CORS so your frontend can communicate with this backend
frontend_origins = [
    origin.strip()
    for origin in os.getenv("FRONTEND_ORIGINS", "http://localhost:3000,http://localhost:5500,http://127.0.0.1:5500").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=frontend_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register route modules
app.include_router(chat.router)
app.include_router(pnr.router)
app.include_router(history.router)
app.include_router(tickets.router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
