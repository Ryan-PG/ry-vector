from __future__ import annotations

from collections.abc import Sequence

from app.models.schemas import RetrievedContext, SearchResult
from app.db import repositories as repo
from app.rag.embeddings import EmbeddingProvider, get_embedding_provider
from app.vectorstore.qdrant_client import UserVectorStore


def search_documents(
    user_id: int,
    query: str,
    top_k: int,
    document_ids: Sequence[int] | None = None,
    embedding_provider: EmbeddingProvider | None = None,
    vector_store: UserVectorStore | None = None,
) -> list[SearchResult]:
    validated_document_ids = repo.validate_document_ids(user_id, document_ids)
    provider = embedding_provider or get_embedding_provider()
    store = vector_store or UserVectorStore()
    query_vector = provider.embed_query(query)
    results = store.search(
        user_id=user_id,
        query_vector=query_vector,
        top_k=top_k,
        document_ids=validated_document_ids,
    )
    return sorted(results, key=lambda item: item.score, reverse=True)[:top_k]


def results_to_context(results: list[SearchResult]) -> list[RetrievedContext]:
    contexts: list[RetrievedContext] = []
    for result in results:
        citation = f"{result.filename}#chunk-{result.chunk_index}"
        contexts.append(
            RetrievedContext(
                text=result.text_chunk,
                citation=citation,
                document_id=result.document_id,
                filename=result.filename,
                chunk_index=result.chunk_index,
                score=result.score,
                source_ref=result.source_ref,
            )
        )
    return contexts
