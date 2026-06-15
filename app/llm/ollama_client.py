from __future__ import annotations

from collections.abc import Iterator
import json

import requests

from app.config import Settings, get_settings


class OllamaChatClient:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.base_url = self.settings.ollama_base_url.rstrip("/")
        self.model = self.settings.ollama_chat_model

    def generate(self, messages: list[dict[str, str]]) -> str:
        response = requests.post(
            f"{self.base_url}/api/chat",
            json={"model": self.model, "messages": messages, "stream": False},
            timeout=300,
        )
        response.raise_for_status()
        data = response.json()
        return (data.get("message") or {}).get("content", "")

    def stream(self, messages: list[dict[str, str]]) -> Iterator[str]:
        response = requests.post(
            f"{self.base_url}/api/chat",
            json={"model": self.model, "messages": messages, "stream": True},
            timeout=300,
            stream=True,
        )
        response.raise_for_status()
        for line in response.iter_lines(decode_unicode=True):
            if not line:
                continue
            data = json.loads(line)
            content = (data.get("message") or {}).get("content")
            if content:
                yield content
            if data.get("done"):
                break

