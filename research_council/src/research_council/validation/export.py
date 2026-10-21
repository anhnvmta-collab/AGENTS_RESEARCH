from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from research_council.core.config import Settings
from research_council.core.orchestration.state import WorkflowState
from research_council.core.security import csv_safe, workspace_path
from research_council.exporters.markdown import md
from research_council.schemas.models import ModelExecution, ResearchRun
from research_council.validation.models import model_benchmark_rows
from research_council.validation.quality import hardware_parameter_rows, sample_real_evidence

EVIDENCE_COLUMNS = [
    "evidence_id",
    "paper_id",
    "claim_id",
    "page",
    "section",
    "excerpt",
    "normalized_statement",
    "agent_interpretation",
    "human_location_correct",
    "human_entailment_correct",
    "human_interpretation_correct",
    "notes",
]


def write_csv(root: Path, name: str, rows: list[dict[str, Any]], columns: list[str]) -> None:
    path = workspace_path(root, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = workspace_path(root, name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows({key: csv_safe(row.get(key)) for key in columns} for row in rows)
    temporary.replace(path)


def evidence_review_rows(state: WorkflowState, sample_seed: int = 11) -> list[dict[str, Any]]:
    selected = sample_real_evidence(
        [item.paper for item in state.candidates], state.evidence, seed=sample_seed
    )
    return [
        {
            "evidence_id": item.evidence_id,
            "paper_id": item.paper_id,
            "claim_id": ";".join(
                str(claim.claim_id)
                for claim in state.claims
                if item.evidence_id in claim.evidence_ids
                or item.evidence_id in claim.contradicting_evidence_ids
            ),
            "page": item.page,
            "section": item.section,
            "excerpt": item.verbatim_excerpt,
            "normalized_statement": item.normalized_statement,
            "agent_interpretation": item.agent_interpretation,
        }
        for item in selected
    ]


def prior_art_rows(state: WorkflowState) -> list[dict[str, Any]]:
    papers = {item.paper.paper_id: item.paper for item in state.candidates}
    return [
        {
            "candidate": report.candidate_id,
            "revision": report.revision,
            "paper": match.paper_id,
            "doi": papers[match.paper_id].metadata.doi if match.paper_id in papers else None,
            "overlap": match.overlap,
            "difference": match.overlap_components.get("difference", "UNVERIFIED"),
            "risk": match.severity,
            "evidence": ";".join(map(str, match.evidence_ids)),
            "similarity": match.similarity,
        }
        for report in state.prior_art
        for match in report.matches
    ]


def export_review_package(
    workspace: Path,
    run: ResearchRun,
    state: WorkflowState,
    settings: Settings,
    executions: list[ModelExecution],
    *,
    sample_seed: int = 11,
) -> Path:
    target = workspace_path(workspace, f"outputs/{run.run_id}")
    target.mkdir(parents=True, exist_ok=True)
    review = workspace_path(target, "human_review")
    review.mkdir(parents=True, exist_ok=True)
    for name in ("gap_review.md", "novelty_review.md", "hardware_review.md", "review_checklist.md"):
        workspace_path(review, name)
    latest_identity = {item.paper_id: item for item in state.identity_audits}
    paper_rows = []
    for item in state.candidates:
        if item.paper.paper_id not in state.core_paper_ids:
            continue
        identity = latest_identity.get(item.paper.paper_id)
        paper_rows.append(
            {
                "paper_id": item.paper.paper_id,
                "title": item.paper.metadata.title,
                "authors": ";".join(item.paper.metadata.authors),
                "year": item.paper.metadata.year,
                "doi": item.paper.metadata.doi,
                "source_url": item.paper.metadata.url,
                "identity_status": identity.status if identity else "UNVERIFIED",
                "total_score": item.aggregate_score,
                "selection_reasons": ";".join(state.shortlist_reasons.get(item.paper.paper_id, [])),
                **(item.score.model_dump(exclude={"paper_id"}) if item.score else {}),
            }
        )
    write_csv(
        review,
        "top_core_papers.csv",
        paper_rows,
        [
            "paper_id",
            "title",
            "authors",
            "year",
            "doi",
            "source_url",
            "identity_status",
            "total_score",
            "relevance",
            "venue_quality",
            "novelty_relevance",
            "methodological_value",
            "hardware_relevance",
            "citation_influence",
            "freshness",
            "selection_reasons",
        ],
    )
    rows = evidence_review_rows(state, sample_seed)
    write_csv(review, "evidence_review.csv", rows, EVIDENCE_COLUMNS)
    write_csv(target, "human_evidence_review_template.csv", rows, EVIDENCE_COLUMNS)
    prior = prior_art_rows(state)
    prior_columns = [
        "candidate",
        "revision",
        "paper",
        "doi",
        "overlap",
        "difference",
        "risk",
        "evidence",
        "similarity",
    ]
    write_csv(review, "closest_prior_art.csv", prior, prior_columns)
    write_csv(target, "closest_prior_art_matrix.csv", prior, prior_columns)
    disagreements = [item.model_dump(mode="json") for item in state.model_disagreements]
    write_csv(
        review,
        "model_disagreement.csv",
        disagreements,
        [
            "disagreement_id",
            "subject_id",
            "task",
            "provider_A",
            "model_A",
            "provider_B",
            "model_B",
            "execution_A",
            "execution_B",
            "position_A",
            "position_B",
            "severity",
            "resolution_status",
            "resolved_by",
            "resolution_note",
        ],
    )
    hardware = hardware_parameter_rows(state.hardware, state.evidence)
    write_csv(
        target,
        "hardware_assumptions.csv",
        hardware,
        [
            "assessment_id",
            "parameter",
            "value",
            "provenance",
            "evidence_ids",
            "assumptions",
            "derivation",
            "notes",
        ],
    )
    models = model_benchmark_rows(executions, settings)
    write_csv(
        target,
        "model_benchmark.csv",
        models,
        list(models[0]) if models else ["task_profile", "provider", "model"],
    )
    write_csv(
        target,
        "search_rounds.csv",
        [
            {
                "search_round": item.round,
                "queries": item.queries,
                "papers_found": item.papers_found,
                "new_unique": item.new_unique_papers,
                "new_core": item.new_core,
                "new_method_family": item.new_method_families,
                "new_evidence": item.new_evidence,
                "new_citation_clusters": item.new_citation_clusters,
                "status": item.status,
                "reason": ";".join(item.reasons),
            }
            for item in state.saturation
        ],
        [
            "search_round",
            "queries",
            "papers_found",
            "new_unique",
            "new_core",
            "new_method_family",
            "new_evidence",
            "new_citation_clusters",
            "status",
            "reason",
        ],
    )
    gap_text = (
        "# Expert gap review\n\nAll gaps are scoped to recorded search coverage. Human judgment is blank.\n\n"
        + "\n\n".join(
            f"## {gap.gap_id}\n\n{md(gap.limitation)}\n\nConsequence: {md(gap.consequence)}\n\nOpportunity: {md(gap.opportunity)}\n\nCoverage: {md(gap.search_scope)}\n\nPotential counterexample: {md(gap.potential_counterexample or 'UNVERIFIED')}\n\nEvidence: {gap.evidence_ids}\n\nKnown approaches: {gap.known_prior_approaches}\n\nConfidence (not verification): {gap.confidence}\n\nHuman reviewer / validity / notes: ______"
            for gap in state.gaps
        )
    )
    (review / "gap_review.md").write_text(gap_text, encoding="utf-8")
    (review / "novelty_review.md").write_text(
        "# Expert novelty review\n\nCandidates are hypotheses; assess closest prior art and falsification criteria.\n\n"
        + "\n\n".join(
            f"## {item.candidate_id} revision {item.revision}\n\n{md(item.normalized_claim)}\n\nRisk: {item.risk_level}\n\nMathematical change: {md(item.mathematical_change)}\n\nImplementation change: {md(item.implementation_change)}\n\nFalsification: {md(item.falsification_test)}\n\nChanged: {md(item.revision_summary)}\n\nWhy: {md(item.change_reason)}\n\nTrigger prior art: {item.trigger_prior_art_ids}\n\nHuman novelty judgment / reviewer / notes: ______"
            for item in state.novelty_candidates
        ),
        encoding="utf-8",
    )
    (review / "hardware_review.md").write_text(
        "# Hardware realism review\n\nNumbers retain SOURCE_REPORTED / DERIVED / ESTIMATED labels. No benchmark measurements are inferred.\n\n```json\n"
        + json.dumps(hardware, default=str, indent=2)
        + "\n```\n\nHuman assumptions / throughput / resources / reviewer / notes: ______\n",
        encoding="utf-8",
    )
    (review / "review_checklist.md").write_text(
        "# Domain expert checklist\n\n- [ ] Check primary source identity, DOI, authors, dates and source conflicts.\n- [ ] Review the randomly selected evidence locations, entailment and interpretation.\n- [ ] Review ten subquestions and missing method/application families.\n- [ ] Check gap scope, known approaches and potential counterexamples.\n- [ ] Attempt to invalidate each novelty candidate, including the weak OMP control.\n- [ ] Review severe model/evidence disagreements explicitly.\n- [ ] Check coherent-channel, sampling, fixed-point, memory and deadline assumptions.\n- [ ] Inspect baselines, ablations, statistics, failure and acceptance criteria.\n- [ ] Record reviewer identity, date and evidence before requesting any SRL advancement.\n\nNo checkbox is automatically completed.\n",
        encoding="utf-8",
    )
    return target
