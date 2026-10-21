from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Protocol

from research_council.schemas.models import Schema, utcnow


class TraceEvent(Schema):
    run_id: str
    agent_id: str = "workflow"
    event: str
    status: str
    latency: float | None = None
    error_type: str | None = None
    provider: str | None = None
    model: str | None = None
    start: datetime | None = None
    end: datetime | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost: float | None = None
    retry: int = 0


class TraceSink(Protocol):
    def emit(self, event: TraceEvent) -> None: ...


class ConsoleTraceSink:
    def emit(self, event: TraceEvent) -> None:
        print(json.dumps({"time": utcnow().isoformat(), **event.model_dump(mode="json")}))


class JSONLTraceSink:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, event: TraceEvent) -> None:
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(
                json.dumps({"time": utcnow().isoformat(), **event.model_dump(mode="json")}) + "\n"
            )
