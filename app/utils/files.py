from __future__ import annotations

import hashlib
import mimetypes
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Tuple


UPLOAD_ROOT = Path("data/uploads")


def ensure_upload_root() -> Path:
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    return UPLOAD_ROOT


def safe_filename(name: str) -> str:
    stem = Path(name).stem
    suffix = Path(name).suffix
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._-") or "document"
    return f"{stem}{suffix.lower()}"


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def file_checksum(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def save_upload_bytes(original_name: str, data: bytes, user_id: int) -> tuple[str, str, str]:
    root = ensure_upload_root() / f"user_{user_id}"
    root.mkdir(parents=True, exist_ok=True)
    filename = safe_filename(original_name)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    stored_name = f"{stamp}_{filename}"
    path = root / stored_name
    path.write_bytes(data)
    mime_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    return str(path), stored_name, mime_type


def read_text_file(path: str) -> str:
    return Path(path).read_text(encoding="utf-8", errors="ignore")

