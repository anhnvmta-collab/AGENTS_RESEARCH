from __future__ import annotations

import json
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


class TraceSink(Protocol):
    def emit(self, event: TraceEvent) -> None: ...


class ConsoleTraceSink:
    def emit(self, event: TraceEvent) -> None:
        print(json.dumps({"time": utcnow().isoformat(), **event.model_dump()}))


class JSONLTraceSink:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, event: TraceEvent) -> None:
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"time": utcnow().isoformat(), **event.model_dump()}) + "\n")
