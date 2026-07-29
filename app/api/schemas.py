"""
Pydantic request/response models.
"""

from typing import List
import re

from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    thread_id: str = Field(min_length=8, max_length=160)
    client_id: str = Field(min_length=8, max_length=100)

    @field_validator("message")
    @classmethod
    def clean_message(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("message cannot be empty")
        return value

    @field_validator("thread_id", "client_id")
    @classmethod
    def safe_identifiers(cls, value: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
            raise ValueError("invalid identifier")
        return value


class ApprovalRequest(BaseModel):
    thread_id: str = Field(min_length=8, max_length=160)
    approved: bool
    client_id: str = Field(min_length=8, max_length=100)


class HistoryMessage(BaseModel):
    role: str
    content: str
    timestamp: str


class ChatHistoryResponse(BaseModel):
    thread_id: str
    messages: List[HistoryMessage]


class LegacyMigrationRequest(BaseModel):
    thread_ids: List[str]
