from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import os
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    llm_provider: str
    openai_api_key: str
    openai_base_url: str | None
    chat_model: str
    embedding_model: str
    ollama_base_url: str
    ollama_chat_model: str
    ollama_embedding_model: str
    chunk_size: int
    chunk_overlap: int
    top_k_default: int
    streaming_enabled: bool
    sqlite_path: str
    qdrant_host: str
    qdrant_port: int
    qdrant_collection_prefix: str

    @property
    def sqlite_parent(self) -> Path:
        return Path(self.sqlite_path).expanduser().resolve().parent


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        llm_provider=os.getenv("LLM_PROVIDER", "openai").strip().lower(),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        openai_base_url=os.getenv("OPENAI_BASE_URL") or None,
        chat_model=os.getenv("CHAT_MODEL", "gpt-4o-mini"),
        embedding_model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/"),
        ollama_chat_model=os.getenv("OLLAMA_CHAT_MODEL", "llama3"),
        ollama_embedding_model=os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text"),
        chunk_size=int(os.getenv("CHUNK_SIZE", "800")),
        chunk_overlap=int(os.getenv("CHUNK_OVERLAP", "120")),
        top_k_default=int(os.getenv("TOP_K_DEFAULT", "5")),
        streaming_enabled=_bool_env("STREAMING_ENABLED", True),
        sqlite_path=os.getenv("SQLITE_PATH", "./data/app.db"),
        qdrant_host=os.getenv("QDRANT_HOST", "localhost"),
        qdrant_port=int(os.getenv("QDRANT_PORT", "6333")),
        qdrant_collection_prefix=os.getenv("QDRANT_COLLECTION_PREFIX", "user_"),
    )
