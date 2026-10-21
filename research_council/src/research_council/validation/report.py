from __future__ import annotations

import json

from research_council.core.config import Settings
from research_council.core.orchestration.state import WorkflowState
from research_council.exporters.markdown import md
from research_council.schemas.models import ModelExecution, ResearchRun
from research_council.validation.benchmark import load_benchmark
from research_council.validation.budget import BudgetUsage
from research_council.validation.coverage import CoverageReport, load_seeds
from research_council.validation.quality import ScientificQualityReport
from research_council.validation.readiness import SRL_DESCRIPTIONS, ScientificReadinessRecord

REPORT_SECTIONS = [
    "Executive Summary",
    "Benchmark Configuration",
    "Providers Used",
    "Search Sources",
    "Search Coverage",
    "Seed Paper Recall",
    "Literature Taxonomy",
    "Core Papers",
    "Evidence Quality",
    "Claim Quality",
    "Contradictions",
    "Research Gaps",
    "Novelty Candidates",
    "Prior-Art Attacks",
    "ReviewerTwo Findings",
    "Novelty Decisions",
    "Hardware Feasibility",
    "Experiment Plan",
    "Model Comparison",
    "Model Disagreements",
    "Human Review Requirements",
    "Known Limitations",
    "Scientific Readiness Decision",
]


def block(value: object) -> str:
    return (
        "```json\n"
        + json.dumps(value, ensure_ascii=False, default=str, indent=2)
        .replace("<", "\\u003c")
        .replace("`", "\\u0060")
        + "\n```"
    )


def render_validation_report(
    run: ResearchRun,
    state: WorkflowState,
    settings: Settings,
    executions: list[ModelExecution],
    coverage: CoverageReport,
    quality: ScientificQualityReport,
    readiness: ScientificReadinessRecord,
    usage: BudgetUsage,
    status: str,
) -> str:
    benchmark = load_benchmark()
    actual = [item for item in executions if item.provider != "fake"]
    papers = {
        item.paper.paper_id: item.paper
        for item in state.candidates
        if item.paper.provenance != "fixture"
    }
    content = {
        "Executive Summary": f"PHASE_11_IMPLEMENTED\n\n{status}\n\nRun {run.run_id}: {run.status}. Recorded readiness remains {readiness.level.label}. Software test success and curated references are not scientific validation.",
        "Benchmark Configuration": block(
            {
                "identifier": benchmark.identifier,
                "question": run.question.model_dump(mode="json"),
                "subquestions": state.plan.subquestions,
                "constraints_are_inputs": True,
                "budget": settings.live_research_budget.model_dump()
                if settings.live_research_budget
                else None,
            }
        ),
        "Providers Used": block(
            [
                {
                    "provider": item.provider,
                    "model": item.model,
                    "role": item.agent_id,
                    "status": item.status,
                    "execution_id": str(item.execution_id),
                }
                for item in actual
            ]
        )
        + "\n\nEmpty means no real provider was exercised. Credential availability is not execution.",
        "Search Sources": block(
            {
                "configured": settings.search.adapters,
                "attempts": [item.model_dump(mode="json") for item in state.search_history],
                "failures": state.warnings,
            }
        ),
        "Search Coverage": block(coverage.model_dump(mode="json"))
        + "\n\nSee search_rounds.csv. Method families are lexical proxies; citation clusters are explored-seed proxies. Any saturation is under the configured search strategy, never universal completeness.",
        "Seed Paper Recall": f"Curated nonexhaustive seeds available: {len(load_seeds())}. Measured recall: {coverage.seed_paper_recall.value if coverage.seed_paper_recall.value is not None else 'UNMEASURED'}. Seeds are not automatically counted as discovered papers.",
        "Literature Taxonomy": block(
            state.knowledge_map.model_dump(mode="json") if state.knowledge_map else {}
        )
        + "\n\nOnly observed metadata/evidence contributes; starter families are not forced into empty branches.",
        "Core Papers": block(
            [
                item.metadata.model_dump(mode="json") | {"paper_id": str(identity)}
                for identity, item in papers.items()
                if identity in state.core_paper_ids
            ]
        )
        + "\n\nSee human_review/top_core_papers.csv for identity status, component scores and diversity reasons.",
        "Evidence Quality": block(
            {
                name: ratio.model_dump() | {"value": ratio.value}
                for name, ratio in quality.metrics.items()
            }
        )
        + "\n\n"
        + block(quality.definitions),
        "Claim Quality": block([item.model_dump(mode="json") for item in state.claims])
        + "\n\nHuman entailment/support judgments remain unmeasured until independently supplied. Hypotheses are not verified claims.",
        "Contradictions": block([item.model_dump(mode="json") for item in state.conflicts])
        + "\n\nOpposing evidence and historical identity conflicts remain visible.",
        "Research Gaps": block([item.model_dump(mode="json") for item in state.gaps])
        + "\n\nAbsence claims apply only within recorded search coverage. Expert gap judgments are required.",
        "Novelty Candidates": block(
            [item.model_dump(mode="json") for item in state.novelty_candidates]
        )
        + f"\n\nPrepared weak control: {md(benchmark.negative_control)}\n\nA prepared control is NOT_EXECUTED until the attack/review workflow actually runs.",
        "Prior-Art Attacks": block(
            [
                item.model_dump(mode="json", exclude={"discovered_candidates"})
                for item in state.prior_art
            ]
        )
        + "\n\nSee closest_prior_art_matrix.csv. Missing/failing search means INSUFFICIENT_SEARCH_COVERAGE, not novelty.",
        "ReviewerTwo Findings": block([item.model_dump(mode="json") for item in state.reviews])
        + "\n\nProvider independence and same-provider fallback are recorded in provider_independence.csv. Reviewer inputs exclude generator private reasoning.",
        "Novelty Decisions": block([item.model_dump(mode="json") for item in state.decisions])
        + "\n\nRaw model verdicts and deterministic policy overrides are separate; policy rejection is not credited as a model's successful scientific judgment.",
        "Hardware Feasibility": block([item.model_dump(mode="json") for item in state.hardware])
        + "\n\nSee hardware_assumptions.csv. SOURCE_REPORTED, DERIVED and ESTIMATED are distinct. No new benchmark measurements are manufactured.",
        "Experiment Plan": block([item.model_dump(mode="json") for item in state.experiments])
        + "\n\nThese are proposed protocols, not executed experiments. The linked IEEE roadmap is in ieee_paper_plan.md.",
        "Model Comparison": "See model_benchmark.csv for attempts, failures, retries, validity, latency, reported tokens, estimated cost and optional human scores. Unexecuted tasks and absent judgments stay blank. No model is universally best from one run.\n\n"
        + block(usage.model_dump()),
        "Model Disagreements": block(
            [item.model_dump(mode="json") for item in state.model_disagreements]
        )
        + "\n\nNo opposing position is silently averaged away. High unresolved disagreement requires human review.",
        "Human Review Requirements": "Review human_review/ and human_evidence_review_template.csv. At least 20 real evidence objects are sampled when available, otherwise all available evidence. Human location, entailment and interpretation fields are blank by design. Use independently completed review bundles and explicit SRL evidence; workflow approval is not scientific attestation.",
        "Known Limitations": "This report cannot establish universal coverage, mathematical correctness, actual FPGA performance or publication readiness from metadata/quotes alone. Lexical retrieval may miss terminology; abstracts may omit implementation details. APIs may fail or require credentials. Human identities are trusted local attestations, not authenticated expert certification. Source-reported synthesis is not an RF/FPGA measurement by this benchmark. Native experiment/replication ingestion is not implemented, so CLI readiness cannot claim SRL-8/9.\n\n"
        + block(state.limitations),
        "Scientific Readiness Decision": f"{readiness.level.label}: {SRL_DESCRIPTIONS[int(readiness.level)]}. No automatic advancement occurred. Evidence-backed sequential operator review is required.\n\n{status}\n\nReproducibility: scientific_reproducibility.json records source/config/prompt/evidence hashes, actual executions, queries, timestamps, source revision and dirty-tree status.",
    }
    return (
        "# LIVE SCIENTIFIC VALIDATION\n\n"
        + "\n\n".join(
            f"## {index} {name}\n\n{content[name]}" for index, name in enumerate(REPORT_SECTIONS, 1)
        )
        + "\n"
    )
