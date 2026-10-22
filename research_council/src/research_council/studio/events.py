from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from research_council.studio.service import StudioService


def events(service: StudioService, identity: UUID) -> list[dict[str, Any]]:
    snapshot = service.snapshot(identity)
    journal = service.store.list("event")
    known = {item["key"] for item in journal}

    def emit(key: str, event: str, value: dict[str, Any]) -> None:
        key = str(identity) + ":" + key
        if key in known:
            return
        known.add(key)
        item = {
            "id": len(journal) + 1,
            "key": key,
            "run_id": str(identity),
            "event": event,
            "data": value,
        }
        service.store.put("event", key, item)
        journal.append(item)

    for row in snapshot["executions"]:
        emit(
            row["execution_id"] + ":start",
            "agent_started",
            {"agent": row["agent_id"], "at": row["start_time"]},
        )
        if row["status"] != "RUNNING":
            emit(
                row["execution_id"] + ":end",
                "agent_completed" if row["status"] == "SUCCESS" else "agent_failed",
                {"agent": row["agent_id"], "status": row["status"], "at": row["end_time"]},
            )
    state = snapshot["state"]
    for field, event, idfield in [
        ("candidates", "paper_found", "paper_id"),
        ("evidence", "evidence_created", "evidence_id"),
        ("claims", "claim_created", "claim_id"),
        ("gaps", "gap_created", "gap_id"),
        ("novelty_candidates", "novelty_created", "candidate_id"),
        ("reviews", "review_completed", "review_id"),
    ]:
        for item in state[field]:
            row = item["paper"] if field == "candidates" else item
            key = str(row[idfield]) + ":" + str(row.get("revision", ""))
            emit(key, event, {"id": row[idfield], "revision": row.get("revision")})
    if state["pending_approval"]:
        emit(
            "approval:" + state["pending_approval"] + ":" + str(snapshot["run"]["stage"]),
            "human_review_required",
            {"point": state["pending_approval"]},
        )
    for gate in state["gates"]:
        if not gate["passed"]:
            emit(
                gate["gate_id"], "gate_blocked", {"gate": gate["gate"], "reasons": gate["reasons"]}
            )
    spent = sum(row["estimated_cost"] or 0 for row in snapshot["models"])
    budget = snapshot["run"]["budget_usd"]
    for threshold in (50, 75, 90):
        if budget and spent / budget * 100 >= threshold:
            emit("budget:" + str(threshold), "budget_warning", {"threshold": threshold})
    if snapshot["run"]["status"] == "COMPLETED":
        emit("completed", "workflow_completed", {"status": "COMPLETED"})
    return [item for item in journal if item["run_id"] == str(identity)]


def encode_event(event: dict[str, Any]) -> str:
    return f"id: {event['id']}\nevent: {event['event']}\ndata: {json.dumps(event['data'])}\n\n"
