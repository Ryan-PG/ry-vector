from __future__ import annotations

from pathlib import Path

from app.config import Settings, get_settings
from app.db import repositories as repo
from app.models.schemas import DocumentRecord
from app.rag.chunking import chunk_segments
from app.rag.document_loaders import SUPPORTED_EXTENSIONS, extract_segments
from app.rag.embeddings import EmbeddingProvider, get_embedding_provider
from app.utils.files import file_checksum, save_upload_bytes
from app.utils.text import safe_excerpt
from app.vectorstore.qdrant_client import UserVectorStore


BATCH_SIZE = 64


def supported_file_types() -> list[str]:
    return sorted(extension.lstrip(".") for extension in SUPPORTED_EXTENSIONS)


def ingest_upload(
    user_id: int,
    original_filename: str,
    file_bytes: bytes,
    settings: Settings | None = None,
    embedding_provider: EmbeddingProvider | None = None,
    vector_store: UserVectorStore | None = None,
    reembed_existing: bool = False,
) -> DocumentRecord:
    settings = settings or get_settings()
    extension = Path(original_filename).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {extension}")

    checksum = file_checksum(file_bytes)
    existing = repo.get_document_by_checksum(user_id, checksum)
    if existing and not reembed_existing:
        return existing

    stored_path, stored_name, mime_type = save_upload_bytes(original_filename, file_bytes, user_id)
    document = repo.create_document(
        user_id=user_id,
        filename=stored_name,
        original_filename=original_filename,
        stored_path=stored_path,
        mime_type=mime_type,
        checksum=checksum,
        status="processing",
    )

    try:
        segments = extract_segments(stored_path, original_filename)
        if not segments:
            raise ValueError("No extractable text found in document")
        chunks = chunk_segments(segments, settings.chunk_size, settings.chunk_overlap)
        if not chunks:
            raise ValueError("Document produced no chunks")

        provider = embedding_provider or get_embedding_provider(settings)
        store = vector_store or UserVectorStore(settings)

        embeddings: list[list[float]] = []
        for start in range(0, len(chunks), BATCH_SIZE):
            batch = chunks[start : start + BATCH_SIZE]
            embeddings.extend(provider.embed_texts([chunk.text for chunk in batch]))

        store.delete_document_vectors(user_id=user_id, document_id=document.id)
        store.upsert_chunks(
            user_id=user_id,
            document_id=document.id,
            filename=original_filename,
            chunks=chunks,
            embeddings=embeddings,
        )
        preview = safe_excerpt(" ".join(segment.text for segment in segments), limit=800)
        repo.update_document_status(document.id, user_id, "ready", chunk_count=len(chunks))
        repo.update_document_preview(document.id, user_id, preview)
        updated = repo.get_document(document.id, user_id)
        return updated or document
    except Exception:
        repo.update_document_status(document.id, user_id, "failed", chunk_count=0)
        raise


def delete_document(user_id: int, document_id: int, vector_store: UserVectorStore | None = None) -> None:
    document = repo.get_document(document_id, user_id)
    if not document:
        raise ValueError("Document not found")
    store = vector_store or UserVectorStore()
    store.delete_document_vectors(user_id=user_id, document_id=document_id)
    repo.mark_document_deleted(document_id, user_id)
