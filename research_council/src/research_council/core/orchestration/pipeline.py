from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from typing import TypeVar
from uuid import uuid5

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
from research_council.core.gates import SourceIntegrityGate, publication_gate, surviving_candidates
from research_council.core.integrity import citation_conflict_open, unresolved_conflict
from research_council.core.orchestration.engine import (
    Concurrency,
    Stage,
    WorkflowEngine,
    parallel_map,
)
from research_council.core.orchestration.novelty import NoveltyLoop
from research_council.core.orchestration.state import WorkflowState
from research_council.core.routing import ModelRouter
from research_council.core.saturation import SearchSaturationDetector
from research_council.core.tracing import TraceSink
from research_council.knowledge.mapping import build_knowledge_map
from research_council.knowledge.retrieval import LocatedChunker
from research_council.repositories.store import SQLRepository
from research_council.schemas.models import (
    ClaimType,
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
    ResearchClaim,
    ResearchPlan,
    ResearchRun,
    ReviewerReport,
    RiskLevel,
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

    async def call(
        self,
        agent_type: type[BaseResearchAgent],
        value: Schema,
        *,
        avoid_provider: str | None = None,
    ) -> Schema:
        agent = agent_type(self.router, self.tools, self.trace, avoid_provider=avoid_provider)
        if self.router.live_budget:
            self.router.live_budget.ensure_active()
        return await self.concurrency.agent(lambda: agent.run(value))

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
        stages = self.stages(mode)
        if self.router.live_budget:
            stages = [self._budgeted_stage(stage) for stage in stages]
        return WorkflowEngine(self.repository, self.settings, stages, self.trace)

    def _budgeted_stage(self, stage: Stage) -> Stage:
        async def execute(run: ResearchRun, state: WorkflowState) -> WorkflowState:
            ledger = self.router.live_budget
            if ledger:
                ledger.ensure_active()
            result = await stage.execute(run, state)
            self.repository.checkpoint(run, {"state": result})
            if ledger:
                ledger.ensure_active()
            return result

        return Stage(stage.name, execute, stage.approvals_before)

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
        before_papers = {item.paper.paper_id for item in state.candidates}
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
                    if self.settings.science_benchmark:
                        from research_council.validation.identity import (
                            retain_identity_observations,
                        )

                        retain_identity_observations(state.identity_observations, result.candidates)
                    state.candidates.extend(result.candidates)
                    state.warnings.extend(result.failures)
                    state.search_history.extend(result.attempts)
                    state.citation_observations.extend(result.citation_observations)
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
                    freshness=min(1, max(0, 1 - (utcnow().year - item.paper.metadata.year) / 20))
                    if item.paper.metadata.year
                    else 0,
                    rationale="Deterministic title overlap/freshness fallback; other components unknown.",
                )
            item.score = score
            item.aggregate_score = score.weighted_total(self.settings.triage.model_dump())
        state.candidates.sort(key=lambda item: item.aggregate_score or 0, reverse=True)
        state.core_paper_ids = [
            item.paper.paper_id
            for item in state.candidates
            if SourceIntegrityGate().evaluate([item.paper]).passed
        ][: self.settings.research.max_core_papers]
        if self.settings.science_benchmark:
            await self._science_core(state)
        state.gates.append(
            SourceIntegrityGate().evaluate(
                [
                    item.paper
                    for item in state.candidates
                    if item.paper.paper_id in state.core_paper_ids
                ]
            )
        )
        self.observe_search(state, before_papers, 0, 0)
        return state

    def observe_search(
        self, state: WorkflowState, before_papers: set, before_evidence: int, history_start: int
    ) -> None:
        attempts = state.search_history[history_start:]
        complete = bool(attempts) and all(attempt.status == "SUCCESS" for attempt in attempts)
        methods, prior_methods, citation_seeds, prior_seeds = set(), set(), set(), set()
        if self.settings.science_benchmark:
            from research_council.validation.coverage import observed_terms, vocabulary

            methods = observed_terms(
                " ".join(
                    f"{item.paper.metadata.title} {item.paper.metadata.abstract or ''}"
                    for item in state.candidates
                ),
                vocabulary("expected_method_families.yaml", "families"),
            )
            if state.saturation:
                prior_methods = set(state.saturation[-1].observed_method_families)
                prior_seeds = set(state.saturation[-1].citation_seed_ids)
            citation_seeds = {
                item.seed_paper_id
                for item in state.search_history
                if item.seed_paper_id
                and item.status == "SUCCESS"
                and item.operation in {"backward", "forward"}
            }
        signal = SearchSaturationDetector(
            self.settings.search.saturation_patience, self.settings.search.minimum_new_unique_rate
        ).observe(
            before_papers,
            {item.paper.paper_id for item in state.candidates},
            before_evidence,
            len(state.evidence),
            state.saturation,
            search_complete=complete,
            new_method_families=len(methods - prior_methods)
            if self.settings.science_benchmark
            else None,
            new_citation_clusters=len(citation_seeds - prior_seeds)
            if self.settings.science_benchmark
            else None,
        )
        if self.settings.science_benchmark:
            signal.queries = len({item.query.query_id for item in attempts if item.query})
            signal.papers_found = sum(
                item.result_count for item in attempts if item.status == "SUCCESS"
            )
            signal.new_core = len(
                set(state.core_paper_ids)
                - (set(state.saturation[-1].core_ids) if state.saturation else set())
            )
            signal.core_ids = state.core_paper_ids
            signal.observed_method_families = sorted(methods)
            signal.citation_seed_ids = sorted(citation_seeds, key=str)
            signal.reasons.append(
                "Method families are lexical proxies; citation clusters are distinct explored citation seeds. Saturation is under the configured search strategy only."
            )
        state.saturation.append(signal)

    async def _discover_queries(self, state: WorkflowState, queries: list[SearchQuery]) -> None:
        if state.saturation and state.saturation[-1].status == "SEARCH_SATURATED":
            state.warnings.append(
                "SEARCH_SATURATED: additional broad searches skipped; coverage remains scoped."
            )
            return
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
                if self.settings.science_benchmark:
                    from research_council.validation.identity import retain_identity_observations

                    retain_identity_observations(state.identity_observations, result.candidates)
                state.candidates.extend(result.candidates)
                state.warnings.extend(result.failures)
                state.search_history.extend(result.attempts)
                state.citation_observations.extend(result.citation_observations)
            else:
                state.warnings.append(f"Discovery branch failed: {type(result).__name__}")
        state.candidates = self._canonicalize(state.candidates)
        accepted = [
            item.paper.paper_id
            for item in state.candidates
            if SourceIntegrityGate().evaluate([item.paper]).passed
        ]
        state.core_paper_ids = list(dict.fromkeys(state.core_paper_ids + accepted))[
            : self.settings.research.max_core_papers
        ]
        if self.settings.science_benchmark:
            await self._science_core(state)

    async def _science_core(self, state: WorkflowState) -> None:
        from research_council.validation.coverage import vocabulary
        from research_council.validation.identity import IdentityInput, IdentityOutput
        from research_council.validation.triage import diverse_shortlist

        value = IdentityInput(
            papers=[item.paper for item in state.candidates],
            observations=state.identity_observations,
        )
        output = IdentityOutput.model_validate(
            await self.tools.invoke(
                "identity_verify", value, allowlist=frozenset({"identity_verify"})
            )
        )
        state.identity_audits.extend(output.audits)
        verified = {
            item.paper_id for item in output.audits if item.status == VerificationStatus.VERIFIED
        }
        # A retained identity contradiction is never cleared by a newer positive flag.
        verified -= {item.paper_id for item in state.identity_audits if item.conflicts}
        eligible = [
            item
            for item in state.candidates
            if item.paper.paper_id in verified
            and SourceIntegrityGate().evaluate([item.paper]).passed
        ]
        maximum = (
            min(
                self.settings.research.max_core_papers,
                self.router.live_budget.budget.max_core_papers,
            )
            if self.router.live_budget
            else self.settings.research.max_core_papers
        )
        shortlist = diverse_shortlist(
            eligible,
            maximum,
            vocabulary("expected_method_families.yaml", "families"),
            utcnow().year,
        )
        state.core_paper_ids, state.shortlist_reasons = (
            shortlist.paper_ids,
            shortlist.selection_reasons,
        )
        if self.router.live_budget:
            self.router.live_budget.select_core(len(state.core_paper_ids))

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
            and item.paper.paper_id in state.core_paper_ids
            and SourceIntegrityGate().evaluate([item.paper]).passed
        ]

        async def read(paper: Paper) -> ReadingOutput:
            if self.router.live_budget:
                self.router.live_budget.consume("deep_reads")
            chunks = LocatedChunker().chunk(paper)
            known_chunks = {chunk.chunk_id for chunk in state.chunks}
            state.chunks.extend(chunk for chunk in chunks if chunk.chunk_id not in known_chunks)
            return ReadingOutput.model_validate(
                await self.call(
                    agents.DeepReader,
                    ReadingInput(
                        task=f"{run.question.topic}. Extract algorithm, signal model, sampling, bandwidth, baselines, metrics, results, limitations and reproducibility from source evidence.",
                        paper=paper,
                        chunks=chunks,
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
            conflicts=state.conflicts,
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
        state.knowledge_map = build_knowledge_map(run.question.topic, state)
        if self.settings.science_benchmark:
            from research_council.validation.taxonomy import observed_taxonomy

            state.knowledge_map = observed_taxonomy(state)
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
        survivors = surviving_candidates(
            state,
            self.repository.list_model_executions(run.run_id),
            self.settings.research.min_novelty_evidence,
        )
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
        if self.settings.science_benchmark:
            from research_council.validation.disagreement import novelty_disagreements

            observed = novelty_disagreements(
                state, self.repository.list_model_executions(run.run_id)
            )
            known = {
                (item.subject_id, item.execution_A, item.execution_B)
                for item in state.model_disagreements
            }
            state.model_disagreements.extend(
                item
                for item in observed
                if (item.subject_id, item.execution_A, item.execution_B) not in known
            )
        value = AuditInput(
            task="Independently audit citation metadata and evidence consistency",
            papers=[item.paper for item in state.candidates],
            claims=state.claims,
            evidence=state.evidence,
            conflicts=state.conflicts,
        )
        result = await self.safe(
            self.call(agents.CitationAuditor, value), AuditsOutput(), state, "CitationAuditor"
        )
        state.audits.extend(AuditsOutput.model_validate(result).audits)
        invalid = set()
        for claim in state.claims:
            if unresolved_conflict(claim, state.conflicts) or any(
                citation_conflict_open(audit, claim, state.conflicts)
                and (claim.claim_id in audit.claim_ids or audit.paper_id in claim.source_paper_ids)
                for audit in state.audits
            ):
                claim.verification_status = VerificationStatus.CONTRADICTED
                invalid.add(claim.claim_id)
        if invalid.intersection(state.synthesis.claim_ids):
            state.synthesis.claim_ids = [
                identity for identity in state.synthesis.claim_ids if identity not in invalid
            ]
            state.synthesis.summary = (
                "Scientific conclusions require renewed review after citation/evidence conflicts."
            )
        state.limitations.append(
            "Automatic quotation/metadata checks do not replace scientific entailment review."
        )
        gate = publication_gate(
            state,
            self.repository.list_model_executions(run.run_id),
            require_novelty=run.mode in (Mode.NOVELTY, Mode.AUDIT),
            minimum_evidence=self.settings.research.min_novelty_evidence,
        )
        if {item.paper_id for item in AuditsOutput.model_validate(result).audits} != {
            item.paper_id for item in value.papers
        }:
            gate.passed = False
            gate.reasons.append("Current citation audit did not complete for every source.")
        state.gates = [item for item in state.gates if item.gate != 3] + [gate]
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
        if self.pipeline.router.live_budget:
            self.pipeline.router.live_budget.begin_novelty(iteration)
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
            prior_art_ids=list(
                {match.paper_id for report in state.prior_art for match in report.matches}
            ),
        )
        result = await self.pipeline.safe(
            self.pipeline.call(agents.NoveltyGenerator, value),
            NoveltyOutput(),
            state,
            "NoveltyGenerator",
        )
        candidates = NoveltyOutput.model_validate(result).candidates[
            : 4 if self.pipeline.settings.science_benchmark else 3
        ]
        if self.pipeline.settings.science_benchmark and iteration == 1 and state.evidence:
            from research_council.validation.benchmark import load_benchmark

            candidates.append(
                NoveltyCandidate(
                    candidate_id=uuid5(self.run.run_id, "negative-novelty-control"),
                    gap_ids=[state.gaps[0].gap_id],
                    evidence_ids=[state.evidence[0].evidence_id],
                    normalized_claim=load_benchmark().negative_control,
                    keywords=["OMP", "UAV", "FHSS"],
                    what_is_new="Application change only; intentionally weak benchmark control.",
                    why_it_matters="Measure whether unchanged-method reuse is overpromoted.",
                    why_prior_methods_insufficient="No scientific insufficiency has been established.",
                    proposed_method="Existing OMP without mathematical or implementation changes.",
                    validation_plan="Independent prior-art attack and reviewer assessment; preserve raw model verdict.",
                    risk_level=RiskLevel.LOW_RISK,
                    mathematical_change="NONE",
                    implementation_change="NONE",
                    falsification_test="Existing matching-pursuit prior art invalidates an algorithmic-novelty claim.",
                    is_negative_control=True,
                )
            )
        for candidate in candidates:
            if self.pipeline.settings.science_benchmark and iteration > 1:
                previous = next(
                    (
                        item
                        for item in reversed(state.novelty_candidates)
                        if item.risk_level == candidate.risk_level and not item.is_negative_control
                    ),
                    None,
                )
                if previous:
                    candidate.candidate_id = previous.candidate_id
                    if not (candidate.revision_summary and candidate.change_reason):
                        raise ValueError("Candidate revisions require what changed and why")
            candidate.revision = iteration
            if self.run.mode == Mode.AUDIT and self.run.question.audit_claim:
                candidate.normalized_claim = self.run.question.audit_claim
            candidate.novelty_claim_id = uuid5(
                candidate.candidate_id, f"novelty-claim:{candidate.revision}"
            )
            premises = [
                item for item in state.evidence if item.evidence_id in candidate.evidence_ids
            ]
            claim = ResearchClaim(
                claim_id=candidate.novelty_claim_id,
                statement=candidate.normalized_claim,
                claim_type=ClaimType.HYPOTHESIS,
                primary=False,
                source_paper_ids=list(dict.fromkeys(item.paper_id for item in premises)),
                evidence_ids=candidate.evidence_ids,
                reviewer_status="NOVELTY_HYPOTHESIS_REQUIRES_EXPERIMENTAL_PROOF",
            )
            state.claims = [item for item in state.claims if item.claim_id != claim.claim_id] + [
                claim
            ]
        return candidates

    async def prior_art(self, candidate: NoveltyCandidate, state: WorkflowState) -> PriorArtReport:
        result = await self.pipeline.call(
            agents.PriorArtHunter, independent_review(candidate, state.evidence)
        )
        return PriorArtReport.model_validate(result)

    async def review(self, candidate: NoveltyCandidate, state: WorkflowState) -> ReviewerReport:
        return ReviewerReport.model_validate(
            await self.pipeline.call(
                agents.ReviewerTwo,
                independent_review(candidate, state.evidence),
                avoid_provider=candidate.generator_provider,
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
            minimal_candidate=bool(self.pipeline.settings.science_benchmark),
        )
        default = NoveltyDecision(
            candidate_id=candidate.candidate_id,
            revision=candidate.revision,
            remaining_risks=["Judgment incomplete."],
        )
        decision = NoveltyDecision.model_validate(
            await self.pipeline.safe(
                self.pipeline.call(agents.NoveltyJudge, value), default, state, "NoveltyJudge"
            )
        )
        if self.pipeline.settings.science_benchmark:
            from research_council.validation.controls import (
                novelty_coverage_status,
                unchanged_method_control,
            )

            decision.model_verdict = decision.verdict if decision.model_execution_id else None
            if unchanged_method_control(candidate):
                decision.verdict = "REJECT"
                decision.policy_overrides.append(
                    "UNCHANGED_METHOD_CONTROL: no mathematical or implementation contribution is claimed; raw model verdict retained separately."
                )
            elif (
                decision.verdict == "SURVIVE"
                and novelty_coverage_status(prior_art) == "INSUFFICIENT_SEARCH_COVERAGE"
            ):
                decision.verdict = "REVISE"
                decision.policy_overrides.append("INSUFFICIENT_SEARCH_COVERAGE")
            if decision.verdict == "SURVIVE" and not any(
                item.verification_status == VerificationStatus.VERIFIED for item in value.evidence
            ):
                decision.verdict = "REVISE"
                decision.policy_overrides.append("Verified scientific evidence is unavailable.")
        return decision

    async def targeted_search(self, queries: list[str], state: WorkflowState) -> WorkflowState:
        before_papers = {item.paper.paper_id for item in state.candidates}
        before_evidence, history_start = len(state.evidence), len(state.search_history)
        targeted = [
            SearchQuery(text=text, strategy="targeted", iteration=state.novelty_iteration)
            for text in queries[: self.pipeline.settings.research.max_queries]
        ]
        state.queries.extend(targeted)
        await self.pipeline._discover_queries(state, targeted)
        state = await self.pipeline.analysis(self.run, state)
        state = await self.pipeline.gaps(self.run, state)
        self.pipeline.observe_search(state, before_papers, before_evidence, history_start)
        return state
