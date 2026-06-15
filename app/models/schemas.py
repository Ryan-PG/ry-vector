from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class UserRecord:
    id: int
    username: str
    email: str
    password_hash: str
    created_at: str


@dataclass(slots=True)
class DocumentRecord:
    id: int
    user_id: int
    filename: str
    original_filename: str
    stored_path: str
    mime_type: str
    checksum: str
    status: str
    chunk_count: int
    preview_text: str | None
    created_at: str
    updated_at: str
    deleted_at: str | None


@dataclass(slots=True)
class ChatSessionRecord:
    id: int
    user_id: int
    title: str
    document_scope: str | None
    created_at: str
    updated_at: str


@dataclass(slots=True)
class ChatMessageRecord:
    id: int
    session_id: int
    user_id: int
    role: str
    content: str
    citations: str | None
    created_at: str


@dataclass(slots=True)
class ExtractedSegment:
    text: str
    source_ref: str
    page_number: int | None = None
    sheet_name: str | None = None


@dataclass(slots=True)
class ChunkRecord:
    text: str
    chunk_index: int
    source_ref: str | None = None
    page_number: int | None = None
    sheet_name: str | None = None


@dataclass(slots=True)
class SearchResult:
    score: float
    text_chunk: str
    document_id: int
    filename: str
    user_id: int
    chunk_index: int
    timestamp: str
    source_ref: str | None = None
    page_number: int | None = None
    sheet_name: str | None = None


@dataclass(slots=True)
class RetrievedContext:
    text: str
    citation: str
    document_id: int
    filename: str
    chunk_index: int
    score: float
    source_ref: str | None = None


@dataclass(slots=True)
class Citation:
    filename: str
    chunk_index: int
    document_id: int
    score: float

