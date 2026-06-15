from __future__ import annotations

import re
from typing import Iterable


_WHITESPACE_RE = re.compile(r"\s+")


def clean_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _WHITESPACE_RE.sub(" ", text)
    return text.strip()


def normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def join_non_empty(parts: Iterable[str], separator: str = "\n") -> str:
    values = [part.strip() for part in parts if part and part.strip()]
    return separator.join(values)


def safe_excerpt(text: str, limit: int = 400) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."

