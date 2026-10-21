from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from typing import TypeVar

from research_council import agents
from research_council.agents.base import BaseResearchAgent
from research_council.agents.contracts import (
    AnalysisInput,
    AuditInput,
    AuditsOutput,
    CandidatesOutput,
    ExperimentInput,
    GapInput,
    GapsOutput,
    JudgmentInput,
    MathOutput,
    NoveltyInput,
    NoveltyOutput,
    PaperInput,
    PlanInput,
    QuestionInput,
    ReadingInput,
    ReadingOutput,
    SearchInput,
    SynthesisInput,
)
from research_council.core.config import Settings
from research_council.core.context import independent_review
from research_council.core.gates import PublicationReadinessGate, SourceIntegrityGate
from research_council.core.orchestration.engine import (
    Concurrency,
    Stage,
    WorkflowEngine,
    parallel_map,
)
from research_council.core.orchestration.novelty import NoveltyLoop
from research_council.core.orchestration.state import WorkflowState
from research_council.core.routing import ModelRouter
from research_council.core.tracing import TraceSink
from research_council.repositories.store import SQLRepository
from research_council.schemas.models import (
    Gap,
    GapType,
    HardwareAssessment,
    LiteratureRow,
    Mode,
    NoveltyCandidate,
    NoveltyDecision,
    Paper,
    PaperCandidate,
    PaperScore,
    PriorArtReport,
    ResearchKnowledgeMap,
    ResearchPlan,
    ResearchRun,
    ReviewerReport,
    Schema,
    SearchQuery,
    VerificationStatus,
    utcnow,
)
from research_council.tools.discovery import PaperDeduplicator
from research_council.tools.registry import ToolRegistry

T = TypeVar("T", bound=Schema)


class ResearchPipeline:
    """Application coordinator; domain reasoning remains in agents and policies."""

    def __init__(
        self,
        repository: SQLRepository,
        settings: Settings,
        router: ModelRouter,
        tools: ToolRegistry,
        trace: TraceSink | None = None,
    ) -> None:
        self.repository, self.settings, self.router, self.tools, self.trace = (
            repository,
            settings,
            router,
            tools,
            trace,
        )
        self.concurrency = Concurrency(settings)

    def agent(self, agent_type: type[BaseResearchAgent]) -> BaseResearchAgent:
        return agent_type(self.router, self.tools, self.trace)

    async def safe(self, work: Awaitable[T], default: T, state: WorkflowState, role: str) -> T:
        try:
            return await work
        except Exception as exc:
            state.warnings.append(f"{role} incomplete: {type(exc).__name__}")
            return default

    async def call(self, agent_type: type[BaseResearchAgent], value: Schema) -> Schema:
        return await self.concurrency.agent(lambda: self.agent(agent_type).run(value))

    def stages(self, mode: Mode) -> list[Stage]:
        if mode == Mode.QUICK:
            return [
                Stage("plan", self.plan),
                Stage("synthesis", self.synthesis, ("after_plan", "before_final_report")),
            ]
        stages = [
            Stage("plan", self.plan),
            Stage(
                "discovery",
                self.discovery,
                ("after_plan",)
                + (("before_expensive_deep",) if mode in (Mode.DEEP, Mode.NOVELTY) else ()),
            ),
            Stage("analysis", self.analysis),
        ]
        if mode in (Mode.DEEP, Mode.NOVELTY, Mode.AUDIT):
            stages.append(Stage("gaps", self.gaps))
        if mode in (Mode.NOVELTY, Mode.AUDIT):
            stages.append(Stage("novelty", self.novelty, ("after_gaps",)))
        if mode in (Mode.DEEP, Mode.NOVELTY):
            stages.append(
                Stage(
                    "experiments",
                    self.experiments,
                    ("after_gaps", "before_accepting_novelty")
                    if mode == Mode.NOVELTY
                    else ("after_gaps",),
                )
            )
        stages += [
            Stage("audit", self.audit),
            Stage("synthesis", self.synthesis, ("before_final_report",)),
        ]
        return stages

    def engine(self, mode: Mode) -> WorkflowEngine:
        return WorkflowEngine(self.repository, self.settings, self.stages(mode), self.trace)

    async def plan(self, run: ResearchRun, state: WorkflowState) -> WorkflowState:
        value = QuestionInput(
            task="Create a bounded evidence-acquisition research plan.",
            question=run.question,
            mode=run.mode,
        )
        state.plan = ResearchPlan.model_validate(
            await self.safe(
                self.call(agents.ResearchPlanner, value),
                ResearchPlan(
                    objective=run.question.topic, tasks=["Acquire and verify source evidence"]
                ),
                state,
                "ResearchPlanner",
            )
        )
        if run.provenance != "live":
            state.limitations.append(
                "Offline execution; no real literature findings are established."
            )
        if run.provenance == "fixture":
            state.limitations.append(
                "SYNTHETIC FIXTURES ONLY — publications and extracted statements are artificial test data."
            )
        return state

    async def discovery(self, run: ResearchRun, state: WorkflowState) -> WorkflowState:
        value = PlanInput(
            task="Prepare complementary perspectives and search strategies.",
            question=run.question,
            mode=run.mode,
            plan=state.plan,
        )
        results = await asyncio.gather(
            self.call(agents.PerspectiveGenerator, value),
            self.call(agents.QueryPlanner, value),
            return_exceptions=True,
        )
        from research_council.agents.contracts import PerspectivesOutput, QueriesOutput

        if isinstance(results[0], PerspectivesOutput):
            state.perspectives = results[0].perspectives
        else:
            state.warnings.append(f"PerspectiveGenerator incomplete: {type(results[0]).__name__}")
        state.queries = results[1].queries if isinstance(results[1], QueriesOutput) else []
        if not state.queries:
            state.queries = [
                SearchQuery(text=run.question.topic, strategy="broad"),
                SearchQuery(text=f"{run.question.topic} FPGA real-time", strategy="hardware"),
            ]
        state.queries = state.queries[: self.settings.research.max_queries]
        await self._discover_queries(state, state.queries)
        seeds = [candidate.paper for candidate in state.candidates[:2]]
        if seeds:
            citation_tasks = [
                self.call(
                    agents.CitationScout,
                    SearchInput(
                        task="Explore citation chains", seed_papers=seeds, direction=direction
                    ),
                )
                for direction in ("backward", "forward", "author", "related")
            ]
            citations = await asyncio.gather(*citation_tasks, return_exceptions=True)
            for result in citations:
                if isinstance(result, CandidatesOutput):
                    state.candidates.extend(result.candidates)
                    state.warnings.extend(result.failures)
                    state.search_history.extend(result.attempts)
                else:
                    state.warnings.append(f"Citation scout incomplete: {type(result).__name__}")
        state.candidates = self._canonicalize(state.candidates)
        # Keep component scores and never make citation count the sole criterion.
        from research_council.agents.contracts import ScoresOutput, TriageInput

        scored = await self.safe(
            self.call(
                agents.PaperTriage,
                TriageInput(
                    task="Score each paper by independent components",
                    question=run.question,
                    mode=run.mode,
                    candidates=[
                        item.model_copy(update={"paper": self._metadata_only(item.paper)})
                        for item in state.candidates
                    ],
                ),
            ),
            ScoresOutput(),
            state,
            "PaperTriage",
        )
        scores = {item.paper_id: item for item in ScoresOutput.model_validate(scored).scores}
        words = set(run.question.topic.lower().split())
        for item in state.candidates:
            score = scores.get(item.paper.paper_id)
            if score is None:
                overlap = len(words & set(item.paper.metadata.title.lower().split())) / max(
                    1, len(words)
                )
                score = PaperScore(
                    paper_id=item.paper.paper_id,
                    relevance=overlap,
                    freshness=max(0, 1 - (utcnow().year - item.paper.metadata.year) / 20)
                    if item.paper.metadata.year
                    else 0,
                    rationale="Deterministic title overlap/freshness fallback; other components unknown.",
                )
            item.score = score
        state.candidates.sort(key=lambda item: item.score.total if item.score else 0, reverse=True)
        state.candidates = state.candidates[: self.settings.research.max_core_papers]
        state.gates.append(
            SourceIntegrityGate().evaluate([item.paper for item in state.candidates])
        )
        return state

    async def _discover_queries(self, state: WorkflowState, queries: list[SearchQuery]) -> None:
        # The IEEE-compatible branch queries compliant indexed metadata, not IEEE scraping.
        broad = SearchInput(task="Broad metadata discovery", queries=queries)
        ieee = SearchInput(
            task="IEEE-compatible indexed metadata discovery",
            queries=[
                SearchQuery(
                    text=query.text + " IEEE",
                    strategy=query.strategy,
                    adapter=query.adapter,
                    iteration=query.iteration,
                )
                for query in queries[:2]
            ],
        )
        local = SearchInput(
            task="Read local document collection", local_paths=self.settings.search.local_documents
        )
        state.queries.extend(ieee.queries)
        results = await asyncio.gather(
            self.call(agents.PaperScout, broad),
            self.call(agents.PaperScout, ieee),
            self.call(agents.LocalDocumentScout, local),
            return_exceptions=True,
        )
        for result in results:
            if isinstance(result, CandidatesOutput):
                state.candidates.extend(result.candidates)
                state.warnings.extend(result.failures)
                state.search_history.extend(result.attempts)
            else:
                state.warnings.append(f"Discovery branch failed: {type(result).__name__}")
        state.candidates = self._canonicalize(state.candidates)

    def _canonicalize(self, candidates: list[PaperCandidate]) -> list[PaperCandidate]:
        library = self.repository.list_all("papers", Paper)
        for item in candidates:
            match = next(
                (paper for paper in library if PaperDeduplicator.same(paper, item.paper)), None
            )
            if match:
                item.paper.paper_id = match.paper_id
                if match.source_text:
                    # Reuse the stored source snapshot so existing evidence remains reproducible.
                    item.paper = match.model_copy(deep=True)
        return PaperDeduplicator().deduplicate(candidates)[
            : self.settings.research.max_core_papers * 10
        ]

    @staticmethod
    def _metadata_only(paper: Paper) -> Paper:
        copy = paper.model_copy(deep=True)
        copy.source_text, copy.page_texts = None, {}
        copy.metadata.abstract = None
        return copy

    async def analysis(self, run: ResearchRun, state: WorkflowState) -> WorkflowState:
        done = {row.paper_id for row in state.matrix}
        papers = [
            item.paper
            for item in state.candidates
            if item.paper.paper_id not in done
            and SourceIntegrityGate().evaluate([item.paper]).passed
        ]

        async def read(paper: Paper) -> ReadingOutput:
            return ReadingOutput.model_validate(
                await self.call(
                    agents.DeepReader,
                    ReadingInput(
                        task="Extract only source-grounded evidence and structured fields.",
                        paper=paper,
                    ),
                )
            )

        papers = papers[: max(0, self.settings.research.max_core_papers - len(done))]
        results = await parallel_map(papers, read, self.concurrency.paper_reads)
        for paper, result in zip(papers, results, strict=True):
            if isinstance(result, ReadingOutput):
                state.evidence.extend(result.evidence)
                state.claims.extend(result.claims)
                state.limitations.extend(result.limitations)
                state.matrix.append(
                    LiteratureRow(
                        paper_id=paper.paper_id,
                        fields={item.field: item.value for item in result.extractions},
                        evidence_ids=[item.evidence_id for item in result.evidence],
                    )
                )
            else:
                state.warnings.append(f"DeepReader:{paper.paper_id}:{type(result).__name__}")
        if run.mode in (Mode.DEEP, Mode.NOVELTY, Mode.AUDIT):
            value = self._analysis_input(run, state)
            results2 = await asyncio.gather(
                self.call(agents.MathDSPAnalyst, value),
                self.call(agents.HardwareArchitect, value),
                return_exceptions=True,
            )
            if isinstance(results2[0], MathOutput):
                state.claims.extend(results2[0].claims)
                state.limitations.extend(results2[0].unknowns)
            if isinstance(results2[1], HardwareAssessment):
                state.hardware = [results2[1]]
            for result2 in results2:
                if isinstance(result2, BaseException):
                    state.warnings.append(f"Analysis incomplete: {type(result2).__name__}")
        return state

    def _analysis_input(self, run: ResearchRun, state: WorkflowState) -> AnalysisInput:
        return AnalysisInput(
            task="Analyze grounded source evidence; identify unknowns.",
            question=run.question,
            mode=run.mode,
            papers=[self._metadata_only(item.paper) for item in state.candidates],
            evidence=state.evidence,
            claims=state.claims,
        )

    async def gaps(self, run: ResearchRun, state: WorkflowState) -> WorkflowState:
        if state.evidence:
            value = GapInput(
                **self._analysis_input(run, state).model_dump(),
                matrix=state.matrix,
                search_scope=f"Run {run.run_id}; {len(state.queries)} logged queries; {len(state.candidates)} candidate records; failures={len(state.warnings)}.",
            )
            result = await self.safe(
                self.call(agents.GapMiner, value), GapsOutput(), state, "GapMiner"
            )
            merged_gaps = {gap.gap_id: gap for gap in state.gaps}
            merged_gaps.update({gap.gap_id: gap for gap in GapsOutput.model_validate(result).gaps})
            state.gaps = list(merged_gaps.values())
        if run.mode == Mode.AUDIT and run.question.audit_claim and state.evidence:
            state.gaps = [
                Gap(
                    gap_type=GapType.THEORETICAL,
                    evidence_ids=[item.evidence_id for item in state.evidence],
                    limitation="User-supplied claim requires independent prior-art audit.",
                    consequence="Novelty has not been established.",
                    opportunity=run.question.audit_claim,
                    search_scope=f"Audit run {run.run_id}",
                )
            ]
        if run.mode == Mode.AUDIT and not run.question.audit_claim:
            state.limitations.append(
                "AUDIT requires an explicit --claim for contribution-specific adversarial review."
            )
        state.knowledge_map = ResearchKnowledgeMap(
            topic=run.question.topic,
            subtopics=[
                ResearchKnowledgeMap(topic=perspective.name) for perspective in state.perspectives
            ],
            paper_ids=[item.paper.paper_id for item in state.candidates],
            claim_ids=[item.claim_id for item in state.claims],
            gap_ids=[item.gap_id for item in state.gaps],
            coverage_score=0,
        )
        return state

    async def novelty(self, run: ResearchRun, state: WorkflowState) -> WorkflowState:
        operations = PipelineNoveltyOperations(self, run)

        async def checkpoint(current: WorkflowState) -> None:
            self.repository.checkpoint(run, {"state": current})

        if run.mode == Mode.AUDIT and not run.question.audit_claim:
            return state
        return await NoveltyLoop(
            operations,
            max_iterations=self.settings.research.max_novelty_iterations,
            minimum_evidence=self.settings.research.min_novelty_evidence,
            execution_records=lambda: self.repository.list_model_executions(run.run_id),
        ).run(state, checkpoint)

    async def experiments(self, run: ResearchRun, state: WorkflowState) -> WorkflowState:
        passed = {
            (gate.candidate_id, gate.candidate_revision)
            for gate in state.gates
            if gate.gate == 2 and gate.passed
        }
        latest = {
            identity: max(
                item.revision for item in state.novelty_candidates if item.candidate_id == identity
            )
            for identity in {item.candidate_id for item in state.novelty_candidates}
        }
        survivors = [
            item
            for item in state.novelty_candidates
            if (item.candidate_id, item.revision) in passed
            and item.revision == latest[item.candidate_id]
            and any(
                decision.candidate_id == item.candidate_id
                and decision.revision == item.revision
                and decision.verdict == "SURVIVE"
                for decision in state.decisions
            )
        ]
        if run.mode == Mode.NOVELTY and not survivors:
            state.limitations.append(
                "Experiment/paper design awaits a contribution that survives Gate 2."
            )
            return state
        if not state.gaps:
            return state
        value = ExperimentInput(
            **self._analysis_input(run, state).model_dump(),
            gaps=state.gaps,
            candidates=survivors,
            hardware=state.hardware,
        )
        from research_council.schemas.models import ExperimentPlan

        result = await self.safe(
            self.call(agents.ExperimentDesigner, value),
            ExperimentPlan(),
            state,
            "ExperimentDesigner",
        )
        state.experiments = [ExperimentPlan.model_validate(result)]
        from research_council.agents.contracts import PaperOutline

        outline = await self.safe(
            self.call(
                agents.PaperArchitect,
                PaperInput(
                    task="Create an evidence-scoped IEEE paper roadmap",
                    experiments=state.experiments,
                    claims=state.claims,
                    limitations=state.limitations,
                ),
            ),
            PaperOutline(),
            state,
            "PaperArchitect",
        )
        state.outline = PaperOutline.model_validate(outline)
        return state

    async def audit(self, run: ResearchRun, state: WorkflowState) -> WorkflowState:
        value = AuditInput(
            task="Independently audit citation metadata and evidence consistency",
            papers=[item.paper for item in state.candidates],
            claims=state.claims,
            evidence=state.evidence,
        )
        result = await self.safe(
            self.call(agents.CitationAuditor, value), AuditsOutput(), state, "CitationAuditor"
        )
        state.audits = AuditsOutput.model_validate(result).audits
        state.limitations.append(
            "Automatic quotation/metadata checks do not replace scientific entailment review."
        )
        gate = PublicationReadinessGate().evaluate(
            value.papers,
            state.claims,
            state.evidence,
            state.audits,
            state.experiments,
            state.limitations,
            conflicts=state.conflicts,
            outline=state.outline,
            novelty_candidates=[
                item
                for item in state.novelty_candidates
                if any(
                    decision.candidate_id == item.candidate_id
                    and decision.revision == item.revision
                    and decision.verdict == "SURVIVE"
                    for decision in state.decisions
                )
            ],
        )
        if run.mode in (Mode.NOVELTY, Mode.AUDIT) and not any(
            item.gate == 2 and item.passed for item in state.gates
        ):
            gate.passed = False
            gate.reasons.append("No contribution survived the independent novelty gate.")
        state.gates.append(gate)
        return state

    async def synthesis(self, run: ResearchRun, state: WorkflowState) -> WorkflowState:
        verified = [
            claim
            for claim in state.claims
            if claim.verification_status == VerificationStatus.VERIFIED
        ]
        evidence_ids = {identity for claim in verified for identity in claim.evidence_ids}
        from research_council.agents.contracts import SynthesisOutput

        value = SynthesisInput(
            task="Select and order audited conclusions without adding facts",
            verified_claims=verified,
            evidence=[item for item in state.evidence if item.evidence_id in evidence_ids],
            audits=state.audits,
            gates=state.gates,
            limitations=state.limitations,
        )
        output = await self.safe(
            self.call(agents.FinalSynthesizer, value), SynthesisOutput(), state, "FinalSynthesizer"
        )
        state.synthesis = SynthesisOutput.model_validate(output)
        state.warnings = list(dict.fromkeys(state.warnings))
        state.limitations = list(dict.fromkeys(state.limitations))
        return state


class PipelineNoveltyOperations:
    def __init__(self, pipeline: ResearchPipeline, run: ResearchRun) -> None:
        self.pipeline, self.run = pipeline, run

    async def generate(self, state: WorkflowState, iteration: int) -> list[NoveltyCandidate]:
        if not state.gaps:
            return []
        value = NoveltyInput(
            task="Propose testable contributions from evidence; revise against prior risks",
            question=self.run.question,
            mode=self.run.mode,
            gaps=state.gaps,
            evidence=state.evidence,
            previous_candidates=state.novelty_candidates[-5:],
            required_changes=[
                risk for decision in state.decisions[-5:] for risk in decision.remaining_risks
            ],
        )
        result = await self.pipeline.safe(
            self.pipeline.call(agents.NoveltyGenerator, value),
            NoveltyOutput(),
            state,
            "NoveltyGenerator",
        )
        candidates = NoveltyOutput.model_validate(result).candidates[:3]
        for candidate in candidates:
            candidate.revision = iteration
            if self.run.mode == Mode.AUDIT and self.run.question.audit_claim:
                candidate.normalized_claim = self.run.question.audit_claim
        return candidates

    async def prior_art(self, candidate: NoveltyCandidate, state: WorkflowState) -> PriorArtReport:
        result = await self.pipeline.call(
            agents.PriorArtHunter, independent_review(candidate, state.evidence)
        )
        return PriorArtReport.model_validate(result)

    async def review(self, candidate: NoveltyCandidate, state: WorkflowState) -> ReviewerReport:
        return ReviewerReport.model_validate(
            await self.pipeline.call(
                agents.ReviewerTwo, independent_review(candidate, state.evidence)
            )
        )

    async def judge(
        self,
        candidate: NoveltyCandidate,
        prior_art: PriorArtReport,
        review: ReviewerReport,
        state: WorkflowState,
    ) -> NoveltyDecision:
        state.candidates = self.pipeline._canonicalize(
            state.candidates + prior_art.discovered_candidates
        )
        state.search_history.extend(prior_art.search_attempts)
        existing_query_ids = {query.query_id for query in state.queries}
        for attempt in prior_art.search_attempts:
            if attempt.query and attempt.query.query_id not in existing_query_ids:
                state.queries.append(attempt.query)
                existing_query_ids.add(attempt.query.query_id)
        value = JudgmentInput(
            task="Decide novelty without averaging scores",
            candidate=candidate,
            evidence=[
                item for item in state.evidence if item.evidence_id in candidate.evidence_ids
            ],
            prior_art=prior_art.model_copy(update={"discovered_candidates": []}),
            review=review,
        )
        default = NoveltyDecision(
            candidate_id=candidate.candidate_id,
            revision=candidate.revision,
            remaining_risks=["Judgment incomplete."],
        )
        return NoveltyDecision.model_validate(
            await self.pipeline.safe(
                self.pipeline.call(agents.NoveltyJudge, value), default, state, "NoveltyJudge"
            )
        )

    async def targeted_search(self, queries: list[str], state: WorkflowState) -> WorkflowState:
        targeted = [
            SearchQuery(text=text, strategy="targeted", iteration=state.novelty_iteration)
            for text in queries[: self.pipeline.settings.research.max_queries]
        ]
        state.queries.extend(targeted)
        await self.pipeline._discover_queries(state, targeted)
        state = await self.pipeline.analysis(self.run, state)
        return await self.pipeline.gaps(self.run, state)
