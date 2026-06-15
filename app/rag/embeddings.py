from __future__ import annotations

from typing import Protocol

import requests
from openai import OpenAI

from app.config import Settings, get_settings


class EmbeddingProvider(Protocol):
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        ...

    def embed_query(self, text: str) -> list[float]:
        ...


class OpenAIEmbeddingProvider:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        if not self.settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
        kwargs = {"api_key": self.settings.openai_api_key}
        if self.settings.openai_base_url:
            kwargs["base_url"] = self.settings.openai_base_url
        self.client = OpenAI(**kwargs)
        self.model = self.settings.embedding_model

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        response = self.client.embeddings.create(model=self.model, input=texts)
        return [item.embedding for item in response.data]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_texts([text])[0]


class OllamaEmbeddingProvider:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.base_url = self.settings.ollama_base_url.rstrip("/")
        self.model = self.settings.ollama_embedding_model

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        response = requests.post(
            f"{self.base_url}/api/embeddings",
            json={"model": self.model, "prompt": text},
            timeout=120,
        )
        response.raise_for_status()
        data = response.json()
        embedding = data.get("embedding")
        if not embedding:
            raise ValueError("Ollama did not return an embedding")
        return embedding


def get_embedding_provider(settings: Settings | None = None) -> EmbeddingProvider:
    settings = settings or get_settings()
    if settings.llm_provider == "openai":
        return OpenAIEmbeddingProvider(settings)
    if settings.llm_provider == "ollama":
        return OllamaEmbeddingProvider(settings)
    raise ValueError(f"Unsupported LLM_PROVIDER: {settings.llm_provider}")

