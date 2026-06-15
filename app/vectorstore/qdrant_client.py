from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from uuid import uuid4

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from app.config import Settings, get_settings
from app.models.schemas import ChunkRecord, SearchResult
from app.utils.files import now_utc_iso


class UserVectorStore:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.client = QdrantClient(host=self.settings.qdrant_host, port=self.settings.qdrant_port)
        self.prefix = self.settings.qdrant_collection_prefix

    def collection_name(self, user_id: int) -> str:
        return f"{self.prefix}{user_id}"

    def ensure_collection(self, user_id: int, vector_size: int) -> None:
        collection = self.collection_name(user_id)
        exists = self.client.collection_exists(collection)
        if exists:
            info = self.client.get_collection(collection)
            existing_size = info.config.params.vectors.size
            if existing_size != vector_size:
                raise ValueError(
                    f"Collection {collection} has vector size {existing_size}, expected {vector_size}. "
                    "Use a consistent embedding model per user collection."
                )
            return

        self.client.create_collection(
            collection_name=collection,
            vectors_config=qmodels.VectorParams(size=vector_size, distance=qmodels.Distance.COSINE),
        )
        self.client.create_payload_index(
            collection_name=collection,
            field_name="document_id",
            field_schema=qmodels.PayloadSchemaType.INTEGER,
        )
        self.client.create_payload_index(
            collection_name=collection,
            field_name="user_id",
            field_schema=qmodels.PayloadSchemaType.INTEGER,
        )

    def upsert_chunks(
        self,
        user_id: int,
        document_id: int,
        filename: str,
        chunks: Sequence[ChunkRecord],
        embeddings: Sequence[Sequence[float]],
    ) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings length mismatch")
        if not chunks:
            return
        vector_size = len(embeddings[0])
        self.ensure_collection(user_id, vector_size)
        timestamp = now_utc_iso()
        points = []
        for chunk, embedding in zip(chunks, embeddings):
            payload = {
                "text_chunk": chunk.text,
                "document_id": document_id,
                "filename": filename,
                "user_id": user_id,
                "chunk_index": chunk.chunk_index,
                "timestamp": timestamp,
                "source_ref": chunk.source_ref,
                "page_number": chunk.page_number,
                "sheet_name": chunk.sheet_name,
            }
            points.append(
                qmodels.PointStruct(
                    id=str(uuid4()),
                    vector=list(embedding),
                    payload=payload,
                )
            )
        self.client.upsert(collection_name=self.collection_name(user_id), points=points, wait=True)

    def search(
        self,
        user_id: int,
        query_vector: Sequence[float],
        top_k: int,
        document_ids: Sequence[int] | None = None,
    ) -> list[SearchResult]:
        collection = self.collection_name(user_id)
        if not self.client.collection_exists(collection):
            return []

        must_filters: list[qmodels.FieldCondition] = [
            qmodels.FieldCondition(key="user_id", match=qmodels.MatchValue(value=user_id))
        ]
        if document_ids:
            must_filters.append(
                qmodels.FieldCondition(key="document_id", match=qmodels.MatchAny(any=list(document_ids)))
            )
        query_filter = qmodels.Filter(must=must_filters)

        hits = self.client.search(
            collection_name=collection,
            query_vector=list(query_vector),
            query_filter=query_filter,
            limit=top_k,
            with_payload=True,
        )
        results: list[SearchResult] = []
        for hit in hits[:top_k]:
            payload: dict[str, Any] = hit.payload or {}
            results.append(
                SearchResult(
                    score=float(hit.score),
                    text_chunk=str(payload.get("text_chunk", "")),
                    document_id=int(payload.get("document_id", 0)),
                    filename=str(payload.get("filename", "")),
                    user_id=int(payload.get("user_id", 0)),
                    chunk_index=int(payload.get("chunk_index", 0)),
                    timestamp=str(payload.get("timestamp", "")),
                    source_ref=payload.get("source_ref"),
                    page_number=payload.get("page_number"),
                    sheet_name=payload.get("sheet_name"),
                )
            )
        return results

    def delete_document_vectors(self, user_id: int, document_id: int) -> None:
        collection = self.collection_name(user_id)
        if not self.client.collection_exists(collection):
            return
        self.client.delete(
            collection_name=collection,
            points_selector=qmodels.FilterSelector(
                filter=qmodels.Filter(
                    must=[
                        qmodels.FieldCondition(key="user_id", match=qmodels.MatchValue(value=user_id)),
                        qmodels.FieldCondition(key="document_id", match=qmodels.MatchValue(value=document_id)),
                    ]
                )
            ),
            wait=True,
        )

    def delete_user_collection(self, user_id: int) -> None:
        collection = self.collection_name(user_id)
        if self.client.collection_exists(collection):
            self.client.delete_collection(collection_name=collection)

