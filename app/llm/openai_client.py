from __future__ import annotations

from collections.abc import Iterator

from openai import OpenAI

from app.config import Settings, get_settings


class OpenAIChatClient:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        if not self.settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
        kwargs = {"api_key": self.settings.openai_api_key}
        if self.settings.openai_base_url:
            kwargs["base_url"] = self.settings.openai_base_url
        self.client = OpenAI(**kwargs)
        self.model = self.settings.chat_model

    def generate(self, messages: list[dict[str, str]]) -> str:
        response = self.client.chat.completions.create(model=self.model, messages=messages)
        return response.choices[0].message.content or ""

    def stream(self, messages: list[dict[str, str]]) -> Iterator[str]:
        response = self.client.chat.completions.create(model=self.model, messages=messages, stream=True)
        for event in response:
            delta = event.choices[0].delta.content
            if delta:
                yield delta

