from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol

from app.config import Settings, get_settings
from app.llm.ollama_client import OllamaChatClient
from app.llm.openai_client import OpenAIChatClient


class ChatClient(Protocol):
    def generate(self, messages: list[dict[str, str]]) -> str:
        ...

    def stream(self, messages: list[dict[str, str]]) -> Iterator[str]:
        ...


def get_chat_client(settings: Settings | None = None) -> ChatClient:
    settings = settings or get_settings()
    if settings.llm_provider == "openai":
        return OpenAIChatClient(settings)
    if settings.llm_provider == "ollama":
        return OllamaChatClient(settings)
    raise ValueError(f"Unsupported LLM_PROVIDER: {settings.llm_provider}")
