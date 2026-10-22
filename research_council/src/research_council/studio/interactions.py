"""Typed advisory agent executions and human-approved workflow proposals."""

from __future__ import annotations

import hashlib
import json
from typing import Any, cast
from uuid import UUID, uuid4

from research_council import agents
from research_council.agents.base import BaseResearchAgent
from research_council.core.context import independent_review
from research_council.core.orchestration.engine import RunLease
from research_council.core.orchestration.state import WorkflowState
from research_council.core.runtime import Runtime, settings_for_run
from research_council.schemas.models import Schema, VerificationStatus, utcnow
from research_council.studio.models import Decision, Interaction
from research_council.studio.service import StudioService


def agent_class(name: str) -> type[BaseResearchAgent]:
    if name not in agents.__all__:
        raise KeyError("Unknown agent")
    return getattr(agents, name)  # type: ignore[no-any-return]


def typed_input(service: StudioService, name: str, request: Interaction) -> Schema:
    role = agent_class(name)
    run = service.repository.get_run(request.run_id)
    state = WorkflowState.model_validate(
        service.repository.artifacts(request.run_id).get("state", {})
    )
    if request.input is not None:
        # Reviewers always receive the engine's isolation projection, not generator persuasion.
        if name in {"ReviewerTwo", "PriorArtHunter", "NoveltyJudge", "FinalSynthesizer"}:
            raise ValueError("Independent roles use the checkpoint context")
        return cast(
            Schema, role.input_schema.model_validate({**request.input, "task": request.task})
        )
    context: dict[str, Any] = {
        **state.model_dump(mode="json"),
        "task": request.task,
        "question": run.question,
        "mode": run.mode,
        "papers": [item.paper for item in state.candidates],
        "seed_papers": [item.paper for item in state.candidates[:2]],
        "candidates": state.candidates if name == "PaperTriage" else state.novelty_candidates,
        "previous_candidates": state.novelty_candidates,
        "local_paths": settings_for_run(service.repository, request.run_id).search.local_documents,
        "verified_claims": [
            item for item in state.claims if item.verification_status == VerificationStatus.VERIFIED
        ],
    }
    if state.candidates:
        context["paper"] = state.candidates[0].paper
        context["chunks"] = [
            item for item in state.chunks if item.paper_id == state.candidates[0].paper.paper_id
        ]
    if state.novelty_candidates:
        candidate = state.novelty_candidates[-1]
        if name in {"ReviewerTwo", "PriorArtHunter"}:
            projected = independent_review(candidate, state.evidence)
            projected.task = request.task
            return projected
        context["candidate"] = candidate
        context["prior_art"] = next(
            (
                item
                for item in reversed(state.prior_art)
                if item.candidate_id == candidate.candidate_id
                and item.revision == candidate.revision
            ),
            None,
        )
        context["review"] = next(
            (
                item
                for item in reversed(state.reviews)
                if item.candidate_id == candidate.candidate_id
                and item.revision == candidate.revision
            ),
            None,
        )
        context["minimal_candidate"] = True
    return cast(
        Schema,
        role.input_schema.model_validate(
            {key: context[key] for key in role.input_schema.model_fields if key in context}
        ),
    )


def propose(service: StudioService, name: str, request: Interaction) -> dict[str, Any]:
    run = service.repository.get_run(request.run_id)
    if run.status != "PAUSED" or not service.repository.artifacts(request.run_id).get(
        "state", {}
    ).get("pending_approval"):
        raise ValueError("Canonical actions require a pending human review gate")
    value = typed_input(service, name, request)
    identity = str(uuid4())
    checkpoint = service.repository.artifacts(request.run_id).get("state", {})
    return service.store.put(
        "interaction",
        identity,
        {
            "id": identity,
            "run_id": str(request.run_id),
            "agent": name,
            "mode": "ACTION",
            "task": request.task,
            "input": value.model_dump(mode="json"),
            "status": "PROPOSED",
            "checkpoint_sha256": hashlib.sha256(
                json.dumps(checkpoint, sort_keys=True).encode()
            ).hexdigest(),
            "at": utcnow().isoformat(),
            "effect": "Execute this role, then restart canonical workflow from planning with the approved instruction; downstream state and approvals are invalidated.",
        },
    )


async def discuss(
    service: StudioService,
    name: str,
    request: Interaction,
    *,
    proposal: dict[str, Any] | None = None,
) -> dict[str, Any]:
    value = (
        agent_class(name).input_schema.model_validate(proposal["input"])
        if proposal
        else typed_input(service, name, request)
    )
    identity = proposal["id"] if proposal else str(uuid4())
    record = proposal or {
        "id": identity,
        "run_id": str(request.run_id),
        "agent": name,
        "mode": "DISCUSSION",
        "task": request.task,
        "at": utcnow().isoformat(),
    }
    lease = RunLease(service.repository, request.run_id)
    lease.acquire()
    import asyncio

    heartbeat = asyncio.create_task(lease.heartbeat())
    try:
        run = service.repository.get_run(request.run_id)
        settings = settings_for_run(service.repository, request.run_id)
        async with Runtime(service.workspace, service.repository, settings, run) as pipeline:
            candidate = WorkflowState.model_validate(
                service.repository.artifacts(request.run_id).get("state", {})
            ).novelty_candidates
            avoid = (
                candidate[-1].generator_provider if name == "ReviewerTwo" and candidate else None
            )
            output = await pipeline.call(agent_class(name), value, avoid_provider=avoid)
        record.update(
            status="EXECUTED_ADVISORY",
            output=output.model_dump(mode="json"),
            canonical_mutation=False,
        )
        return service.store.put("interaction", identity, record)
    except Exception as exc:
        record.update(status="FAILED", error_type=type(exc).__name__, canonical_mutation=False)
        service.store.put("interaction", identity, record)
        raise
    finally:
        from contextlib import suppress

        heartbeat.cancel()
        with suppress(asyncio.CancelledError):
            await heartbeat
        lease.release()


async def approve_proposal(
    service: StudioService, identity: UUID, decision: Decision
) -> dict[str, Any]:
    record = service.store.get("interaction", str(identity))
    if record["mode"] != "ACTION" or record["status"] != "PROPOSED":
        raise ValueError("Proposal is not pending")
    record["decision"] = decision.model_dump(mode="json")
    if decision.action != "approve":
        record["status"] = "REJECTED" if decision.action == "reject" else "REVISION_REQUESTED"
        return service.store.put("interaction", str(identity), record)
    run_id = UUID(record["run_id"])
    checkpoint = service.repository.artifacts(run_id).get("state", {})
    if (
        hashlib.sha256(json.dumps(checkpoint, sort_keys=True).encode()).hexdigest()
        != record["checkpoint_sha256"]
    ):
        raise ValueError("Stale proposal; review the current checkpoint and propose again")
    record["status"] = "APPROVED"
    service.store.put("interaction", str(identity), record)
    result = await discuss(
        service, record["agent"], Interaction(run_id=run_id, task=record["task"]), proposal=record
    )
    run = service.repository.get_run(run_id)
    question = run.question.model_copy(deep=True)
    question.constraints.append(
        f"Approved researcher action for {record['agent']}: {record['task']}"
    )
    from research_council.core.orchestration.engine import WorkflowEngine

    WorkflowEngine(
        service.repository, settings_for_run(service.repository, run_id), []
    ).human_decision(run_id, "modify", modified_question=question)
    result.update(status="APPLIED_TO_WORKFLOW", canonical_mutation=True)
    return service.store.put("interaction", str(identity), result)
