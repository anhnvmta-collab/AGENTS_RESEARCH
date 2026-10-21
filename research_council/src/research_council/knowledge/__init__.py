from __future__ import annotations

import math
from typing import Protocol
from uuid import UUID


class VectorStore(Protocol):
    def upsert(self, identity: UUID, vector: list[float]) -> None: ...
    def search(self, vector: list[float], limit: int = 5) -> list[tuple[UUID, float]]: ...


class InMemoryVectorStore:
    def __init__(self) -> None:
        self.vectors: dict[UUID, list[float]] = {}
        self.dimension: int | None = None

    def _validate(self, vector: list[float]) -> None:
        if not vector or not all(math.isfinite(item) for item in vector):
            raise ValueError("Vector must be non-empty and finite")
        if self.dimension is not None and len(vector) != self.dimension:
            raise ValueError("Vector dimensions do not match")

    def upsert(self, identity: UUID, vector: list[float]) -> None:
        self._validate(vector)
        self.dimension = len(vector)
        self.vectors[identity] = list(vector)

    def search(self, vector: list[float], limit: int = 5) -> list[tuple[UUID, float]]:
        self._validate(vector)
        norm = math.sqrt(sum(item * item for item in vector))
        output = []
        for identity, other in self.vectors.items():
            other_norm = math.sqrt(sum(item * item for item in other))
            similarity = (
                sum(a * b for a, b in zip(vector, other, strict=True)) / (norm * other_norm)
                if norm and other_norm
                else 0.0
            )
            output.append((identity, similarity))
        return sorted(output, key=lambda item: item[1], reverse=True)[: max(0, limit)]
