from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Protocol

from research_council.core.gates import NoveltySurvivalGate
from research_council.core.orchestration.state import WorkflowState
from research_council.schemas.models import (
    NoveltyCandidate,
    NoveltyDecision,
    PriorArtReport,
    ReviewerReport,
)


class NoveltyOperations(Protocol):
    async def generate(self, state: WorkflowState, iteration: int) -> list[NoveltyCandidate]: ...
    async def prior_art(
        self, candidate: NoveltyCandidate, state: WorkflowState
    ) -> PriorArtReport: ...
    async def review(self, candidate: NoveltyCandidate, state: WorkflowState) -> ReviewerReport: ...
    async def judge(
        self,
        candidate: NoveltyCandidate,
        prior_art: PriorArtReport,
        review: ReviewerReport,
        state: WorkflowState,
    ) -> NoveltyDecision: ...
    async def targeted_search(self, queries: list[str], state: WorkflowState) -> WorkflowState: ...


class NoveltyLoop:
    def __init__(
        self, operations: NoveltyOperations, *, max_iterations: int = 3, minimum_evidence: int = 2
    ) -> None:
        if max_iterations < 1:
            raise ValueError("Novelty loop needs a positive bound")
        self.operations = operations
        self.max_iterations = max_iterations
        self.gate = NoveltySurvivalGate(minimum_evidence)

    async def run(
        self,
        state: WorkflowState,
        checkpoint: Callable[[WorkflowState], Awaitable[None]] | None = None,
    ) -> WorkflowState:
        if any(gate.gate == 2 and gate.passed for gate in state.gates):
            return state
        if state.pending_targeted_queries:
            state = await self.operations.targeted_search(state.pending_targeted_queries, state)
            state.pending_targeted_queries = []
            if checkpoint:
                await checkpoint(state)
        for index in range(state.novelty_iteration, self.max_iterations):
            candidates = await self.operations.generate(state, index + 1)
            if not candidates:
                state.limitations.append("No evidence-grounded novelty candidates were available.")
                break
            followups: list[str] = []
            survived = False
            for candidate in candidates:
                state.novelty_candidates.append(candidate)
                # Reviewer and hunter receive separately constructed restricted inputs.
                attack = await asyncio.gather(
                    self.operations.prior_art(candidate, state),
                    self.operations.review(candidate, state),
                    return_exceptions=True,
                )
                prior = (
                    attack[0]
                    if isinstance(attack[0], PriorArtReport)
                    else PriorArtReport(
                        candidate_id=candidate.candidate_id,
                        revision=candidate.revision,
                        search_failures=[type(attack[0]).__name__],
                    )
                )
                review = (
                    attack[1]
                    if isinstance(attack[1], ReviewerReport)
                    else ReviewerReport(
                        candidate_id=candidate.candidate_id, revision=candidate.revision
                    )
                )
                decision = await self.operations.judge(candidate, prior, review, state)
                if (
                    decision.candidate_id != candidate.candidate_id
                    or decision.revision != candidate.revision
                ):
                    raise ValueError("Novelty judgment candidate mismatch")
                gate = self.gate.evaluate(candidate, state.evidence, prior, review, decision)
                if decision.verdict == "SURVIVE" and not gate.passed:
                    decision.verdict = "REVISE"
                    decision.remaining_risks.extend(gate.reasons)
                state.prior_art.append(prior)
                state.reviews.append(review)
                state.decisions.append(decision)
                state.gates.append(gate)
                survived = survived or gate.passed
                followups.extend(decision.required_followup_searches or candidate.keywords)
            state.novelty_iteration = index + 1
            state.pending_targeted_queries = (
                list(dict.fromkeys(followups))
                if not survived and index + 1 < self.max_iterations
                else []
            )
            if checkpoint:
                await checkpoint(state)
            if survived:
                break
            if index + 1 < self.max_iterations:
                state = await self.operations.targeted_search(state.pending_targeted_queries, state)
                state.pending_targeted_queries = []
                if checkpoint:
                    await checkpoint(state)
        if state.novelty_iteration >= self.max_iterations:
            for decision in state.decisions:
                if decision.verdict == "REVISE":
                    decision.verdict = "UNRESOLVED"
                    decision.remaining_risks.append("Configured novelty iteration limit reached.")
        return state
