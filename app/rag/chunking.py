from __future__ import annotations

from app.models.schemas import ChunkRecord, ExtractedSegment
from app.utils.text import clean_text


def chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0:
        raise ValueError("overlap must be non-negative")
    if overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")

    cleaned = clean_text(text)
    if not cleaned:
        return []

    chunks: list[str] = []
    start = 0
    while start < len(cleaned):
        end = min(start + chunk_size, len(cleaned))
        chunk = cleaned[start:end].strip()

        if end < len(cleaned):
            split_at = max(chunk.rfind(". "), chunk.rfind("\n"), chunk.rfind(" "))
            if split_at > chunk_size * 0.6:
                end = start + split_at + 1
                chunk = cleaned[start:end].strip()

        if chunk:
            chunks.append(chunk)
        if end >= len(cleaned):
            break
        start = max(end - overlap, start + 1)

    return chunks


def chunk_segments(segments: list[ExtractedSegment], chunk_size: int, overlap: int) -> list[ChunkRecord]:
    all_chunks: list[ChunkRecord] = []
    for segment in segments:
        for text in chunk_text(segment.text, chunk_size, overlap):
            all_chunks.append(
                ChunkRecord(
                    text=text,
                    chunk_index=len(all_chunks),
                    source_ref=segment.source_ref,
                    page_number=segment.page_number,
                    sheet_name=segment.sheet_name,
                )
            )
    return all_chunks

