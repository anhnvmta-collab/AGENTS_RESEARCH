from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from uuid import UUID

import yaml
from pydantic import Field

from research_council.core.config import Settings, load_settings
from research_council.core.gates import publication_gate
from research_council.core.orchestration.engine import RunLease
from research_council.core.orchestration.state import WorkflowState
from research_council.core.runtime import Runtime, create_run, open_repository, settings_for_run
from research_council.core.security import workspace_path
from research_council.exporters import MarkdownExporter
from research_council.repositories.store import SQLRepository
from research_council.schemas.models import (
    Mode,
    ResearchPerspective,
    ResearchPlan,
    ResearchQuestion,
    Schema,
)
from research_council.validation.benchmark import benchmark_directory, load_benchmark
from research_council.validation.budget import BudgetUsage, LiveResearchBudget
from research_council.validation.coverage import (
    coverage_report,
    load_seeds,
    verified_citation_edges,
    vocabulary,
)
from research_council.validation.disagreement import detect_disagreements, novelty_disagreements
from research_council.validation.export import export_review_package, write_csv
from research_council.validation.models import model_benchmark_rows
from research_council.validation.provenance import reproducibility_manifest
from research_council.validation.quality import scientific_quality
from research_council.validation.readiness import (
    ReadinessEvidence,
    ScientificReadinessRecord,
    advance_readiness,
)
from research_council.validation.report import render_validation_report
from research_council.validation.reviews import (
    HumanReviewBundle,
    apply_disagreement_resolutions,
    readiness_facts,
    validate_human_reviews,
)


class ValidationMetadata(Schema):
    phase_status: str = "PHASE_11_IMPLEMENTED"
    live_status: str = "LIVE_VALIDATION_NOT_YET_EXECUTED"
    planned_config_sha256: str | None = None
    review_bundle_sha256: str | None = None
    sample_seed: int = 11
    warnings: list[str] = Field(default_factory=list)


def safe_text(root: Path, name: str, text: str) -> None:
    path = workspace_path(root, name)
    temporary = workspace_path(root, name + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def json_text(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


def load_review_file(workspace: Path, name: str) -> tuple[HumanReviewBundle, str]:
    path = workspace_path(workspace, name)
    if path.stat().st_size > 2_000_000:
        raise ValueError("Human review bundle is too large")
    data = path.read_bytes()
    return HumanReviewBundle.model_validate_json(data), hashlib.sha256(data).hexdigest()


def finalize_validation(
    repository: SQLRepository, workspace: Path, run_id: UUID, *, human_reviews: str | None = None
) -> Path:
    lease = RunLease(repository, run_id)
    lease.acquire()
    try:
        run = repository.get_run(run_id)
        settings = settings_for_run(repository, run_id)
        if not settings.science_benchmark:
            raise ValueError("Run is not a scientific validation benchmark")
        artifacts = repository.artifacts(run_id)
        state = WorkflowState.model_validate(artifacts.get("state", {}))
        metadata = ValidationMetadata.model_validate(artifacts.get("scientific_validation", {}))
        readiness = ScientificReadinessRecord.model_validate(
            artifacts.get("scientific_readiness", {"run_id": run_id})
        )
        executions = repository.list_model_executions(run_id)
        bundle = (
            HumanReviewBundle.model_validate(artifacts["scientific_human_reviews"])
            if artifacts.get("scientific_human_reviews")
            else None
        )
        if human_reviews:
            bundle, metadata.review_bundle_sha256 = load_review_file(workspace, human_reviews)
            validate_human_reviews(bundle, state, executions)
        if bundle:
            validate_human_reviews(bundle, state, executions)
        observed = novelty_disagreements(state, executions)
        if bundle:
            observed.extend(detect_disagreements(bundle.model_positions, executions))
        known = {
            (item.subject_id, item.task, item.execution_A, item.execution_B)
            for item in state.model_disagreements
        }
        state.model_disagreements.extend(
            item
            for item in observed
            if (item.subject_id, item.task, item.execution_A, item.execution_B) not in known
        )
        if bundle:
            apply_disagreement_resolutions(bundle, state)
            repository.checkpoint(run, {"scientific_human_reviews": bundle})
        actual_calls = [item for item in executions if item.provider != "fake"]
        if run.provenance == "live" and (actual_calls or state.search_history):
            metadata.live_status = (
                "LIVE_VALIDATION_EXECUTED"
                if run.status == "COMPLETED"
                else "LIVE_VALIDATION_PARTIALLY_EXECUTED"
            )
        papers = [item.paper for item in state.candidates]
        seeds = load_seeds()
        expected_edges = yaml.safe_load(
            (benchmark_directory() / "seed_papers.yaml").read_text(encoding="utf-8")
        ).get("expected_citation_edges", [])
        coverage = coverage_report(
            papers,
            seeds,
            vocabulary("expected_method_families.yaml", "families"),
            vocabulary("expected_concepts.yaml", "concepts"),
            evidence_text=" ".join(
                item.normalized_statement for item in state.evidence if item.provenance != "fixture"
            ),
            expected_citation_edges={tuple(edge) for edge in expected_edges},
            observed_citation_edges=verified_citation_edges(state.citation_observations),
        )
        successful_search = any(
            item.status == "SUCCESS" and item.adapter in {"crossref", "openalex", "arxiv"}
            for item in state.search_history
        )
        if not successful_search:
            coverage.measurement_status = (
                "INSUFFICIENT_SEARCH_COVERAGE" if state.search_history else "NOT_EXECUTED"
            )
            for ratio in (
                coverage.seed_paper_recall,
                coverage.method_family_recall,
                coverage.concept_coverage,
                coverage.citation_chain_recovery,
            ):
                ratio.numerator, ratio.denominator = 0, 0
        quality = scientific_quality(
            papers,
            state.evidence,
            state.claims,
            state.conflicts,
            bundle.evidence if bundle else None,
            bundle.contradiction_labels if bundle else None,
            bundle.claim_support_labels if bundle else None,
        )
        usage = BudgetUsage.model_validate(artifacts.get("live_budget_usage", {}))
        gate = publication_gate(
            state,
            executions,
            require_novelty=run.mode in {Mode.NOVELTY, Mode.AUDIT},
            minimum_evidence=settings.research.min_novelty_evidence,
        )
        state.gates = [item for item in state.gates if item.gate != 3] + [gate]
        repository.checkpoint(
            run,
            {"state": state, "scientific_validation": metadata, "scientific_readiness": readiness},
        )
        target = MarkdownExporter(workspace, repository).export(run, state)
        export_review_package(
            workspace, run, state, settings, executions, sample_seed=metadata.sample_seed
        )
        model_rows = model_benchmark_rows(
            executions, settings, bundle.model_scores if bundle else None
        )
        write_csv(
            target,
            "model_benchmark.csv",
            model_rows,
            list(model_rows[0]) if model_rows else ["task_profile", "provider", "model"],
        )
        routes = []
        execution_map = {item.execution_id: item for item in executions}
        for review in state.reviews:
            candidate = next(
                (
                    item
                    for item in state.novelty_candidates
                    if item.candidate_id == review.candidate_id and item.revision == review.revision
                ),
                None,
            )
            generator = (
                execution_map.get(candidate.generation_execution_id)
                if candidate and candidate.generation_execution_id
                else None
            )
            reviewer = (
                execution_map.get(review.model_execution_id) if review.model_execution_id else None
            )
            routes.append(
                {
                    "candidate_id": review.candidate_id,
                    "revision": review.revision,
                    "generator_provider": generator.provider if generator else None,
                    "reviewer_provider": reviewer.provider if reviewer else None,
                    "generator_model": generator.model if generator else None,
                    "reviewer_model": reviewer.model if reviewer else None,
                    "same_provider_fallback": generator.provider == reviewer.provider
                    if generator and reviewer
                    else None,
                    "reason": reviewer.routing_note
                    if reviewer and reviewer.routing_note
                    else "CONTROL_OR_MISSING_GENERATOR_EXECUTION",
                }
            )
        write_csv(
            target,
            "provider_independence.csv",
            routes,
            [
                "candidate_id",
                "revision",
                "generator_provider",
                "generator_model",
                "reviewer_provider",
                "reviewer_model",
                "same_provider_fallback",
                "reason",
            ],
        )
        metrics = {
            "coverage": coverage.model_dump(mode="json"),
            "coverage_values": {
                name: getattr(coverage, name).value
                for name in (
                    "seed_paper_recall",
                    "method_family_recall",
                    "concept_coverage",
                    "citation_chain_recovery",
                )
            },
            "quality": quality.model_dump(mode="json"),
            "quality_values": {name: ratio.value for name, ratio in quality.metrics.items()},
            "scientific_readiness": readiness.model_dump(mode="json"),
            "readiness_facts": readiness_facts(
                run, state, executions, bundle, settings.research.min_novelty_evidence
            ).model_dump(mode="json"),
            "phase_status": metadata.phase_status,
            "live_status": metadata.live_status,
        }
        safe_text(target, "scientific_metrics.json", json_text(metrics))
        provenance = reproducibility_manifest(run, state, settings, executions)
        provenance.update(
            {
                "planned_config_sha256": metadata.planned_config_sha256,
                "review_bundle_sha256": metadata.review_bundle_sha256,
                "budget_usage": usage.model_dump(mode="json"),
                "evidence_sample_seed": metadata.sample_seed,
                "curated_seed_ids": [seed.identifier for seed in seeds],
                "curation_is_benchmark_execution": False,
                "citation_observations": [
                    item.model_dump(mode="json") for item in state.citation_observations
                ],
            }
        )
        safe_text(target, "scientific_reproducibility.json", json_text(provenance))
        safe_text(
            target,
            "literature_taxonomy.json",
            json_text(state.knowledge_map.model_dump(mode="json") if state.knowledge_map else {}),
        )
        safe_text(
            target,
            "LIVE_SCIENTIFIC_VALIDATION.md",
            render_validation_report(
                run,
                state,
                settings,
                executions,
                coverage,
                quality,
                readiness,
                usage,
                metadata.live_status,
            ),
        )
        manifest = json.loads((target / "run_manifest.json").read_text(encoding="utf-8"))
        manifest["scientific_validation"] = metrics
        manifest["files"] = {
            path.relative_to(target).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(target.rglob("*"))
            if path.is_file() and path != target / "run_manifest.json"
        }
        safe_text(target, "run_manifest.json", json_text(manifest))
        return target
    finally:
        lease.release()


def prepare_validation(
    workspace: Path, question: ResearchQuestion | None = None, planned_config: Path | None = None
) -> tuple[UUID, Path]:
    benchmark = load_benchmark()
    settings = Settings(
        science_benchmark="CS_FHSS_DOA_FPGA", live_research_budget=LiveResearchBudget()
    )
    settings.research.max_queries = len(benchmark.queries())
    repository = open_repository(workspace)
    try:
        run = create_run(repository, question or benchmark.question, Mode.NOVELTY, settings)
        state = WorkflowState(
            plan=ResearchPlan(
                objective=run.question.topic,
                subquestions=benchmark.subquestions,
                limitations=["Prepared input questions; no live model has produced this plan."],
            ),
            perspectives=[
                ResearchPerspective(
                    name=name,
                    questions=[question.topic for question in benchmark.subquestions.values()],
                )
                for name in benchmark.perspectives
            ],
            queries=benchmark.queries(),
            limitations=[
                "LIVE_VALIDATION_NOT_YET_EXECUTED",
                "Curated seeds are not counted as retrieved benchmark findings.",
            ],
        )
        metadata = ValidationMetadata(
            planned_config_sha256=hashlib.sha256(planned_config.read_bytes()).hexdigest()
            if planned_config
            else None
        )
        repository.checkpoint(
            run,
            {
                "state": state,
                "scientific_validation": metadata,
                "scientific_readiness": ScientificReadinessRecord(run_id=run.run_id),
            },
        )
        return run.run_id, finalize_validation(repository, workspace, run.run_id)
    finally:
        repository.engine.dispose()


def live_validation_settings(config: Path) -> Settings:
    settings = load_settings(config)
    settings.science_benchmark = "CS_FHSS_DOA_FPGA"
    if any(
        route.provider not in {"openai", "anthropic", "google"}
        for routes in settings.route_groups()
        for route in routes
    ):
        raise ValueError(
            "Scientific live validation requires real provider routes for every enabled task, without fake fallback"
        )
    if any(
        name not in {"crossref", "openalex", "arxiv", "ieee"} for name in settings.search.adapters
    ):
        raise ValueError("Unsupported scientific search adapter configuration")
    budget = settings.live_research_budget or LiveResearchBudget()
    settings.live_research_budget = budget
    settings.research.budget_usd = min(settings.research.budget_usd, budget.max_total_cost)
    settings.research.max_model_calls = max(
        1, min(settings.research.max_model_calls, budget.max_model_calls)
    )
    settings.research.max_core_papers = max(
        1, min(settings.research.max_core_papers, budget.max_core_papers)
    )
    settings.research.max_novelty_iterations = max(
        1, min(settings.research.max_novelty_iterations, budget.max_novelty_iterations, 3)
    )
    return settings


def validate_science(
    workspace: Path,
    *,
    question: ResearchQuestion | None = None,
    config: Path | None = None,
    live: bool = False,
    confirm_paid_apis: bool = False,
    resume_id: UUID | None = None,
    human_reviews: str | None = None,
    mode: Mode = Mode.NOVELTY,
) -> tuple[UUID, Path]:
    if resume_id is None and not (live and confirm_paid_apis):
        return prepare_validation(workspace, question, config)
    repository = open_repository(workspace)
    try:
        if resume_id is not None:
            run = repository.get_run(resume_id)
            settings = settings_for_run(repository, run.run_id)
            if not settings.science_benchmark:
                raise ValueError("Resume target is not a scientific validation run")
        else:
            if config is None:
                raise ValueError(
                    "Confirmed live validation requires an operator-configured --config file"
                )
            settings = live_validation_settings(config)
            run = create_run(
                repository,
                question or load_benchmark().question,
                mode,
                settings,
                live=True,
                confirm_paid_apis=True,
            )
            repository.checkpoint(
                run,
                {
                    "scientific_validation": ValidationMetadata(
                        planned_config_sha256=hashlib.sha256(config.read_bytes()).hexdigest()
                    )
                },
            )
        if live and confirm_paid_apis:
            if run.provenance != "live":
                raise ValueError(
                    "Prepared offline run cannot be converted to live; create a new explicitly confirmed run"
                )

            async def execute() -> None:
                async with Runtime(workspace, repository, settings, run) as pipeline:
                    await pipeline.engine(run.mode).resume(run.run_id)

            try:
                asyncio.run(execute())
            except (RuntimeError, ValueError):
                # Engine checkpoints retain explicit failures; export them for review.
                if repository.get_run(run.run_id).status not in {"FAILED", "BUDGET_EXHAUSTED"}:
                    raise
        return run.run_id, finalize_validation(
            repository, workspace, run.run_id, human_reviews=human_reviews
        )
    finally:
        repository.engine.dispose()


def review_readiness(
    workspace: Path, run_id: UUID, proof_file: str | None = None
) -> ScientificReadinessRecord:
    repository = open_repository(workspace)
    lease = RunLease(repository, run_id)
    lease.acquire()
    try:
        run = repository.get_run(run_id)
        artifacts = repository.artifacts(run_id)
        record = ScientificReadinessRecord.model_validate(
            artifacts.get("scientific_readiness", {"run_id": run_id})
        )
        if proof_file:
            path = workspace_path(workspace, proof_file)
            if path.stat().st_size > 100_000:
                raise ValueError("Readiness request is too large")
            proof = ReadinessEvidence.model_validate_json(path.read_bytes())
            source = workspace_path(workspace, proof.artifact_path)
            if source.stat().st_size > 20_000_000:
                raise ValueError("Readiness proof artifact exceeds size limit")
            state = WorkflowState.model_validate(artifacts.get("state", {}))
            executions = repository.list_model_executions(run_id)
            bundle = (
                HumanReviewBundle.model_validate(artifacts["scientific_human_reviews"])
                if artifacts.get("scientific_human_reviews")
                else None
            )
            if bundle:
                validate_human_reviews(bundle, state, executions)
            available = (
                {str(item.execution_id) for item in executions}
                | {str(item.paper.paper_id) for item in state.candidates}
                | {str(item.evidence_id) for item in state.evidence}
                | {str(item.claim_id) for item in state.claims}
                | {str(item.gap_id) for item in state.gaps}
                | {str(item.candidate_id) for item in state.novelty_candidates}
            )
            record = advance_readiness(
                record,
                proof,
                readiness_facts(
                    run,
                    state,
                    executions,
                    bundle,
                    settings_for_run(repository, run_id).research.min_novelty_evidence,
                ),
                available,
                hashlib.sha256(source.read_bytes()).hexdigest(),
            )
            repository.checkpoint(run, {"scientific_readiness": record})
        return record
    finally:
        lease.release()
        repository.engine.dispose()
