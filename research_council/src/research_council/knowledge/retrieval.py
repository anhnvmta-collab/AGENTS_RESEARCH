from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from typing import Protocol
from uuid import uuid5

from research_council.schemas.models import Paper, PaperChunk, RankedChunk


def source_hash(paper: Paper) -> str:
    data = {"kind": paper.source_kind, "text": paper.source_text, "pages": paper.page_texts}
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class Chunker(Protocol):
    def chunk(self, paper: Paper) -> list[PaperChunk]: ...


class EvidenceRetriever(Protocol):
    def rank(self, query: str, chunks: list[PaperChunk], limit: int = 8) -> list[RankedChunk]: ...


class LocatedChunker:
    def __init__(self, size: int = 2500, overlap: int = 250) -> None:
        if not 1 <= size <= 8000 or not 0 <= overlap < size:
            raise ValueError("Invalid source chunk window")
        self.size, self.overlap = size, overlap

    def chunk(self, paper: Paper) -> list[PaperChunk]:
        digest = source_hash(paper)
        pages: list[tuple[int | None, str]] = [
            (page, text) for page, text in paper.page_texts.items()
        ] or [(None, paper.source_text or "")]
        chunks: list[PaperChunk] = []
        for page, text in pages:
            for start in range(0, len(text), self.size - self.overlap):
                end = min(len(text), start + self.size)
                value = text[start:end]
                if value.strip():
                    chunks.append(
                        PaperChunk(
                            chunk_id=uuid5(paper.paper_id, f"{digest}:{page}:{start}:{end}"),
                            paper_id=paper.paper_id,
                            page=page,
                            start_offset=start,
                            end_offset=end,
                            text=value,
                            source_sha256=digest,
                        )
                    )
                if end == len(text):
                    break
        return chunks


class LexicalEvidenceRetriever:
    """Deterministic TF/IDF-style ranking; no mandatory embedding service."""

    def rank(self, query: str, chunks: list[PaperChunk], limit: int = 8) -> list[RankedChunk]:
        terms = set(re.findall(r"\w+", query.casefold()))
        counters = [Counter(re.findall(r"\w+", chunk.text.casefold())) for chunk in chunks]
        frequencies = {term: sum(term in counter for counter in counters) for term in terms}
        ranked: list[RankedChunk] = []
        for chunk, counter in zip(chunks, counters, strict=True):
            score = sum(
                (1 + math.log(counter[term])) * math.log(1 + len(chunks) / (1 + frequencies[term]))
                for term in terms
                if counter[term]
            )
            ranked.append(RankedChunk(chunk=chunk, score=score))
        return sorted(
            ranked, key=lambda item: (-item.score, item.chunk.page or 0, item.chunk.start_offset)
        )[: max(0, limit)]
