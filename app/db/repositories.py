from __future__ import annotations

import json
from typing import Any, Iterable

from passlib.context import CryptContext

from app.db.database import get_connection
from app.models.schemas import (
    ChatMessageRecord,
    ChatSessionRecord,
    DocumentRecord,
    UserRecord,
)
from app.utils.files import now_utc_iso


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)


def _row_to_user(row) -> UserRecord:
    return UserRecord(
        id=row["id"],
        username=row["username"],
        email=row["email"],
        password_hash=row["password_hash"],
        created_at=row["created_at"],
    )


def _row_to_document(row) -> DocumentRecord:
    return DocumentRecord(
        id=row["id"],
        user_id=row["user_id"],
        filename=row["filename"],
        original_filename=row["original_filename"],
        stored_path=row["stored_path"],
        mime_type=row["mime_type"],
        checksum=row["checksum"],
        status=row["status"],
        chunk_count=row["chunk_count"],
        preview_text=row["preview_text"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        deleted_at=row["deleted_at"],
    )


def _row_to_chat_session(row) -> ChatSessionRecord:
    return ChatSessionRecord(
        id=row["id"],
        user_id=row["user_id"],
        title=row["title"],
        document_scope=row["document_scope"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _row_to_chat_message(row) -> ChatMessageRecord:
    return ChatMessageRecord(
        id=row["id"],
        session_id=row["session_id"],
        user_id=row["user_id"],
        role=row["role"],
        content=row["content"],
        citations=row["citations"],
        created_at=row["created_at"],
    )


def create_user(username: str, email: str, password: str) -> UserRecord:
    with get_connection() as conn:
        created_at = now_utc_iso()
        cursor = conn.execute(
            """
            INSERT INTO users (username, email, password_hash, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (username.strip(), email.strip().lower(), hash_password(password), created_at),
        )
        row = conn.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return _row_to_user(row)


def get_user_by_username_or_email(identifier: str) -> UserRecord | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ? OR email = ?",
            (identifier.strip(), identifier.strip().lower()),
        ).fetchone()
        return _row_to_user(row) if row else None


def get_user_by_id(user_id: int) -> UserRecord | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return _row_to_user(row) if row else None


def authenticate_user(identifier: str, password: str) -> UserRecord | None:
    user = get_user_by_username_or_email(identifier)
    if not user:
        return None
    return user if verify_password(password, user.password_hash) else None


def list_documents(user_id: int, include_deleted: bool = False) -> list[DocumentRecord]:
    with get_connection() as conn:
        query = "SELECT * FROM documents WHERE user_id = ?"
        params: list[Any] = [user_id]
        if not include_deleted:
            query += " AND status != 'deleted'"
        query += " ORDER BY created_at DESC"
        rows = conn.execute(query, params).fetchall()
        return [_row_to_document(row) for row in rows]


def get_document(document_id: int, user_id: int) -> DocumentRecord | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM documents WHERE id = ? AND user_id = ?",
            (document_id, user_id),
        ).fetchone()
        return _row_to_document(row) if row else None


def get_document_by_checksum(user_id: int, checksum: str) -> DocumentRecord | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT * FROM documents
            WHERE user_id = ? AND checksum = ? AND status = 'ready'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (user_id, checksum),
        ).fetchone()
        return _row_to_document(row) if row else None


def create_document(
    user_id: int,
    filename: str,
    original_filename: str,
    stored_path: str,
    mime_type: str,
    checksum: str,
    status: str = "processing",
    preview_text: str | None = None,
) -> DocumentRecord:
    with get_connection() as conn:
        ts = now_utc_iso()
        cursor = conn.execute(
            """
            INSERT INTO documents
            (user_id, filename, original_filename, stored_path, mime_type, checksum, status, chunk_count, preview_text, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?)
            """,
            (user_id, filename, original_filename, stored_path, mime_type, checksum, status, preview_text, ts, ts),
        )
        row = conn.execute("SELECT * FROM documents WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return _row_to_document(row)


def update_document_status(document_id: int, user_id: int, status: str, chunk_count: int | None = None) -> None:
    with get_connection() as conn:
        ts = now_utc_iso()
        fields = ["status = ?", "updated_at = ?"]
        params: list[Any] = [status, ts]
        if chunk_count is not None:
            fields.insert(1, "chunk_count = ?")
            params.insert(1, chunk_count)
        params.extend([document_id, user_id])
        conn.execute(
            f"UPDATE documents SET {', '.join(fields)} WHERE id = ? AND user_id = ?",
            params,
        )


def update_document_preview(document_id: int, user_id: int, preview_text: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE documents
            SET preview_text = ?, updated_at = ?
            WHERE id = ? AND user_id = ?
            """,
            (preview_text, now_utc_iso(), document_id, user_id),
        )


def mark_document_deleted(document_id: int, user_id: int) -> None:
    with get_connection() as conn:
        ts = now_utc_iso()
        conn.execute(
            """
            UPDATE documents
            SET status = 'deleted', deleted_at = ?, updated_at = ?
            WHERE id = ? AND user_id = ?
            """,
            (ts, ts, document_id, user_id),
        )


def hard_delete_document(document_id: int, user_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM documents WHERE id = ? AND user_id = ?", (document_id, user_id))


def list_document_choices(user_id: int) -> list[dict[str, Any]]:
    return [
        {
            "id": doc.id,
            "label": doc.filename,
            "status": doc.status,
            "chunk_count": doc.chunk_count,
        }
        for doc in list_documents(user_id)
    ]


def validate_document_ids(user_id: int, document_ids: Iterable[int] | None) -> list[int] | None:
    if not document_ids:
        return None
    requested = [int(document_id) for document_id in document_ids]
    placeholders = ",".join("?" for _ in requested)
    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT id FROM documents
            WHERE user_id = ? AND status = 'ready' AND id IN ({placeholders})
            """,
            [user_id, *requested],
        ).fetchall()
    allowed = {row["id"] for row in rows}
    missing = [document_id for document_id in requested if document_id not in allowed]
    if missing:
        raise ValueError("One or more selected documents are not owned by this user or are not ready")
    return requested


def create_chat_session(user_id: int, title: str, document_scope: list[int] | None = None) -> ChatSessionRecord:
    validated_scope = validate_document_ids(user_id, document_scope) or []
    with get_connection() as conn:
        ts = now_utc_iso()
        scope_json = json.dumps(validated_scope)
        cursor = conn.execute(
            """
            INSERT INTO chat_sessions (user_id, title, document_scope, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, title.strip() or "New chat", scope_json, ts, ts),
        )
        row = conn.execute("SELECT * FROM chat_sessions WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return _row_to_chat_session(row)


def update_chat_session_scope(session_id: int, user_id: int, document_scope: list[int] | None) -> None:
    validated_scope = validate_document_ids(user_id, document_scope) or []
    with get_connection() as conn:
        ts = now_utc_iso()
        conn.execute(
            """
            UPDATE chat_sessions
            SET document_scope = ?, updated_at = ?
            WHERE id = ? AND user_id = ?
            """,
            (json.dumps(validated_scope), ts, session_id, user_id),
        )


def get_chat_session(session_id: int, user_id: int) -> ChatSessionRecord | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM chat_sessions WHERE id = ? AND user_id = ?",
            (session_id, user_id),
        ).fetchone()
        return _row_to_chat_session(row) if row else None


def list_chat_sessions(user_id: int) -> list[ChatSessionRecord]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM chat_sessions WHERE user_id = ? ORDER BY updated_at DESC, id DESC",
            (user_id,),
        ).fetchall()
        return [_row_to_chat_session(row) for row in rows]


def add_chat_message(
    session_id: int,
    user_id: int,
    role: str,
    content: str,
    citations: list[dict[str, Any]] | None = None,
) -> ChatMessageRecord:
    with get_connection() as conn:
        session = conn.execute(
            "SELECT id FROM chat_sessions WHERE id = ? AND user_id = ?",
            (session_id, user_id),
        ).fetchone()
        if not session:
            raise ValueError("Chat session not found for this user")
        ts = now_utc_iso()
        cursor = conn.execute(
            """
            INSERT INTO chat_messages (session_id, user_id, role, content, citations, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (session_id, user_id, role, content, json.dumps(citations) if citations else None, ts),
        )
        conn.execute(
            "UPDATE chat_sessions SET updated_at = ? WHERE id = ? AND user_id = ?",
            (ts, session_id, user_id),
        )
        row = conn.execute("SELECT * FROM chat_messages WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return _row_to_chat_message(row)


def list_chat_messages(session_id: int, user_id: int) -> list[ChatMessageRecord]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM chat_messages
            WHERE session_id = ? AND user_id = ?
            ORDER BY id ASC
            """,
            (session_id, user_id),
        ).fetchall()
        return [_row_to_chat_message(row) for row in rows]


def delete_chat_session(session_id: int, user_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM chat_sessions WHERE id = ? AND user_id = ?", (session_id, user_id))


def user_stats(user_id: int) -> dict[str, int]:
    with get_connection() as conn:
        docs = conn.execute(
            "SELECT COUNT(*) AS count FROM documents WHERE user_id = ? AND status != 'deleted'",
            (user_id,),
        ).fetchone()["count"]
        chunks = conn.execute(
            "SELECT COALESCE(SUM(chunk_count), 0) AS count FROM documents WHERE user_id = ? AND status != 'deleted'",
            (user_id,),
        ).fetchone()["count"]
        sessions = conn.execute(
            "SELECT COUNT(*) AS count FROM chat_sessions WHERE user_id = ?",
            (user_id,),
        ).fetchone()["count"]
        messages = conn.execute(
            "SELECT COUNT(*) AS count FROM chat_messages WHERE user_id = ?",
            (user_id,),
        ).fetchone()["count"]
        return {"documents": docs, "chunks": chunks, "sessions": sessions, "messages": messages}


def export_chat_session(session_id: int, user_id: int) -> dict[str, Any]:
    session = get_chat_session(session_id, user_id)
    if not session:
        raise ValueError("Chat session not found")
    messages = list_chat_messages(session_id, user_id)
    return {
        "session": session,
        "messages": messages,
    }
