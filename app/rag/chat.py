from __future__ import annotations

from collections.abc import Iterator, Sequence

from app.config import Settings, get_settings
from app.llm.router import ChatClient, get_chat_client
from app.models.schemas import RetrievedContext
from app.rag.retrieval import results_to_context, search_documents


SYSTEM_PROMPT = "You are a helpful assistant. Answer ONLY from context."


def build_rag_messages(query: str, contexts: list[RetrievedContext]) -> list[dict[str, str]]:
    context_text = "\n\n".join(
        f"[{item.citation} | score={item.score:.4f}]\n{item.text}" for item in contexts
    )
    user_prompt = (
        "Context:\n"
        f"{context_text or 'No relevant context found.'}\n\n"
        f"Question:\n{query}\n\n"
        "Answer using only the context above. Include citation markers like [filename#chunk-3] "
        "for the facts you use. If the context does not contain the answer, say you do not know."
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]


def format_citations(contexts: list[RetrievedContext]) -> list[dict[str, object]]:
    seen: set[tuple[int, int]] = set()
    citations: list[dict[str, object]] = []
    for item in contexts:
        key = (item.document_id, item.chunk_index)
        if key in seen:
            continue
        seen.add(key)
        citations.append(
            {
                "filename": item.filename,
                "document_id": item.document_id,
                "chunk_index": item.chunk_index,
                "score": round(item.score, 6),
                "citation": item.citation,
            }
        )
    return citations


def answer_question(
    user_id: int,
    query: str,
    top_k: int,
    document_ids: Sequence[int] | None = None,
    settings: Settings | None = None,
    chat_client: ChatClient | None = None,
) -> tuple[str, list[dict[str, object]], list[RetrievedContext]]:
    settings = settings or get_settings()
    results = search_documents(user_id=user_id, query=query, top_k=top_k, document_ids=document_ids)
    contexts = results_to_context(results)
    client = chat_client or get_chat_client(settings)
    answer = client.generate(build_rag_messages(query, contexts))
    return answer, format_citations(contexts), contexts


def stream_answer_question(
    user_id: int,
    query: str,
    top_k: int,
    document_ids: Sequence[int] | None = None,
    settings: Settings | None = None,
    chat_client: ChatClient | None = None,
) -> tuple[Iterator[str], list[dict[str, object]], list[RetrievedContext]]:
    settings = settings or get_settings()
    results = search_documents(user_id=user_id, query=query, top_k=top_k, document_ids=document_ids)
    contexts = results_to_context(results)
    client = chat_client or get_chat_client(settings)
    return client.stream(build_rag_messages(query, contexts)), format_citations(contexts), contexts

