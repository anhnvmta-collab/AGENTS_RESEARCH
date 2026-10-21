from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Protocol

from research_council.core.config import Settings
from research_council.core.gates import publication_gate
from research_council.core.integrity import validate_graph
from research_council.core.orchestration.state import WorkflowState
from research_council.core.security import csv_safe, workspace_path
from research_council.repositories.store import SQLRepository
from research_council.schemas.models import Mode, ModelExecution, ResearchRun, utcnow


class Exporter(Protocol):
    def export(self, run: ResearchRun, state: WorkflowState) -> Path: ...


def md(value: object) -> str:
    return str(value).replace("<", "&lt;").replace(">", "&gt;").replace("|", "\\|")


class MarkdownExporter:
    def __init__(self, workspace: Path, repository: SQLRepository) -> None:
        self.workspace, self.repository = workspace, repository

    def export(self, run: ResearchRun, state: WorkflowState) -> Path:
        validate_graph(state)
        target = workspace_path(self.workspace, f"outputs/{run.run_id}")
        target.mkdir(parents=True, exist_ok=True)

        def write(name: str, text: str) -> None:
            path = target / name
            temporary = workspace_path(self.workspace, path.with_suffix(path.suffix + ".tmp"))
            temporary.write_text(text, encoding="utf-8")
            temporary.replace(path)

        def json_file(name: str, value: Any) -> None:
            write(name, json.dumps(value, indent=2, ensure_ascii=False))

        def csv_file(name: str, rows: list[dict[str, Any]], columns: list[str]) -> None:
            path = target / name
            temporary = workspace_path(self.workspace, path.with_suffix(".csv.tmp"))
            with temporary.open("w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=columns)
                writer.writeheader()
                writer.writerows({key: csv_safe(row.get(key)) for key in columns} for row in rows)
            temporary.replace(path)

        notice = (
            "SYNTHETIC FIXTURES — NOT SCIENTIFIC FINDINGS\n\n"
            if run.provenance == "fixture"
            else ""
        )
        json_file("research_plan.json", state.plan.model_dump(mode="json"))
        json_file("search_queries.json", [item.model_dump(mode="json") for item in state.queries])
        paper_rows = [
            {
                "paper_id": item.paper.paper_id,
                "title": item.paper.metadata.title,
                "authors": "; ".join(item.paper.metadata.authors),
                "year": item.paper.metadata.year,
                "doi": item.paper.metadata.doi,
                "url": item.paper.metadata.url,
                "provenance": item.paper.provenance,
                "score": item.aggregate_score
                if item.aggregate_score is not None
                else item.score.total
                if item.score
                else None,
                **(item.score.model_dump(exclude={"paper_id"}) if item.score else {}),
            }
            for item in state.candidates
        ]
        csv_file(
            "paper_candidates.csv",
            paper_rows,
            [
                "paper_id",
                "title",
                "authors",
                "year",
                "doi",
                "url",
                "provenance",
                "score",
                "relevance",
                "venue_quality",
                "methodological_value",
                "novelty_relevance",
                "hardware_relevance",
                "citation_influence",
                "freshness",
                "rationale",
            ],
        )
        json_file("literature_matrix.json", [row.model_dump(mode="json") for row in state.matrix])
        csv_file(
            "core_papers.csv",
            [row for row in paper_rows if row["paper_id"] in state.core_paper_ids],
            ["paper_id", "title", "authors", "year", "doi", "url", "score", "provenance"],
        )
        fields = sorted({key for row in state.matrix for key in row.fields})
        csv_file(
            "literature_matrix.csv",
            [
                {
                    "paper_id": row.paper_id,
                    "evidence_ids": ";".join(map(str, row.evidence_ids)),
                    **row.fields,
                }
                for row in state.matrix
            ],
            ["paper_id", "evidence_ids", *fields],
        )
        write("evidence.jsonl", "".join(item.model_dump_json() + "\n" for item in state.evidence))
        write("claims.jsonl", "".join(item.model_dump_json() + "\n" for item in state.claims))
        write(
            "reviewer_report.md",
            notice
            + "# Independent reviewer reports\n\n```json\n"
            + json.dumps([item.model_dump(mode="json") for item in state.reviews], indent=2)
            + "\n```\n",
        )
        write(
            "novelty_decisions.md",
            notice
            + "# Novelty decisions by revision\n\n```json\n"
            + json.dumps([item.model_dump(mode="json") for item in state.decisions], indent=2)
            + "\n```\n",
        )
        write(
            "research_gaps.md",
            notice
            + "# Evidence-scoped research gaps\n\n"
            + (
                "\n\n".join(
                    f"## {gap.gap_type}: {gap.gap_id}\n\nEvidence: {', '.join(map(str, gap.evidence_ids))}\n\nLimitation: {md(gap.limitation)}\n\nConsequence: {md(gap.consequence)}\n\nOpportunity: {md(gap.opportunity)}\n\nSearch scope: {md(gap.search_scope)}"
                    for gap in state.gaps
                )
                or "No evidence-grounded gaps available."
            ),
        )
        write(
            "novelty_candidates.md",
            notice
            + "# Unverified candidate contributions\n\n"
            + (
                "\n\n".join(
                    f"## {candidate.candidate_id} revision {candidate.revision}\n\nClaim: {md(candidate.normalized_claim)}\n\nRisk: {candidate.risk_level}\n\nWhat: {md(candidate.what_is_new)}\n\nWhy: {md(candidate.why_it_matters)}\n\nPrior-method limitation: {md(candidate.why_prior_methods_insufficient)}\n\nMethod: {md(candidate.proposed_method)}\n\nTest: {md(candidate.validation_plan)}\n\nEvidence: {', '.join(map(str, candidate.evidence_ids))}"
                    for candidate in state.novelty_candidates
                )
                or "No candidates available."
            ),
        )
        write(
            "prior_art_report.md",
            notice
            + "# Independent novelty attack\n\n"
            + (
                "\n\n".join(
                    f"## {decision.candidate_id} revision {decision.revision}: {decision.verdict}\n\nConfidence: {decision.novelty_confidence}\n\nRemaining risks: {'; '.join(map(md, decision.remaining_risks))}\n\nFollow-up queries: {'; '.join(map(md, decision.required_followup_searches))}"
                    for decision in state.decisions
                )
                or "No contribution-specific attack completed."
            )
            + "\n\n## Hunter/reviewer records\n\n```json\n"
            + json.dumps(
                {
                    "prior_art": [
                        report.model_dump(mode="json", exclude={"discovered_candidates"})
                        for report in state.prior_art
                    ],
                    "reviews": [report.model_dump(mode="json") for report in state.reviews],
                },
                indent=2,
            )
            + "\n```\n",
        )
        write(
            "hardware_feasibility.md",
            notice
            + "# Hardware feasibility — assessments, not measurements\n\n"
            + (
                "\n\n".join(
                    f"## {assessment.platform}: {assessment.feasibility}\n\nMeasurement status: {assessment.measurement_status}\n\n{md(assessment.justification)}\n\nUnknowns: {', '.join(map(md, assessment.unknowns))}\n\nEvidence: {', '.join(map(str, assessment.evidence_ids))}\n\n```json\n{assessment.model_dump_json(indent=2)}\n```"
                    for assessment in state.hardware
                )
                or "Hardware assessment was not completed."
            ),
        )
        write(
            "experiment_plan.md",
            notice
            + "# Proposed experiments — no measured results\n\n"
            + (
                "\n\n".join(
                    f"## {md(plan.objective)}\n\nHypothesis: {md(plan.hypothesis)}\n\nProgression: {' -> '.join(map(md, plan.progression))}\n\nBaselines: {'; '.join(map(md, plan.baselines))}\n\nMetrics: {'; '.join(map(md, plan.metrics))}\n\nProcedures: {'; '.join(map(md, plan.procedures))}\n\nAblations: {'; '.join(map(md, plan.ablations))}\n\nStatistics: {md(plan.statistical_plan)}\n\nFailure cases: {'; '.join(map(md, plan.failure_cases))}\n\nAcceptance criteria: {'; '.join(map(md, plan.acceptance_criteria))}\n\nReproducibility: {'; '.join(map(md, plan.reproducibility))}\n\nLimitations: {'; '.join(map(md, plan.limitations))}\n\n```json\n{plan.model_dump_json(indent=2)}\n```"
                    for plan in state.experiments
                )
                or "No experiment plan passed prerequisites."
            ),
        )
        write(
            "ieee_paper_plan.md",
            notice
            + f"# {md(state.outline.title)}\n\n"
            + "\n\n".join(
                f"## {md(section)}\n\n" + "\n".join(f"- {md(item)}" for item in items)
                for section, items in state.outline.sections.items()
            )
            + "\n\nJournal quartile and publication acceptance are not established.\n",
        )
        csv_file(
            "citation_audit.csv",
            [
                {
                    "paper_id": audit.paper_id,
                    "status": audit.status,
                    "verifier": audit.verifier,
                    "checks": json.dumps(audit.checks),
                    "notes": "; ".join(audit.notes),
                }
                for audit in state.audits
            ],
            ["paper_id", "status", "verifier", "checks", "notes"],
        )
        report = [
            f"# Research Council: {md(run.question.topic)}",
            notice,
            f"Run: {run.run_id} | Mode: {run.mode} | Status: {run.status} | Provenance: {run.provenance}",
        ]
        publication = publication_gate(
            state,
            self.repository.list_model_executions(run.run_id),
            require_novelty=run.mode in (Mode.NOVELTY, Mode.AUDIT),
            minimum_evidence=Settings.model_validate(
                self.repository.artifacts(run.run_id).get("settings", {})
            ).research.min_novelty_evidence,
        ).passed
        report += [
            "## Publication readiness",
            "PASSED" if publication else "NOT ESTABLISHED",
            "## Verified scientific conclusions",
            state.synthesis.summary,
        ]
        report += ["## Quality gates"]
        report += [
            f"- Gate {gate.gate}: {'PASS' if gate.passed else 'FAIL'} — {md('; '.join(gate.reasons) or 'Scoped checks passed.')}"
            for gate in state.gates
        ] or ["No gates evaluated."]
        report += [
            "## Traceable claim register",
            "AUTHOR_REPORTED/DERIVED/AGENT_ANALYSIS entries below retain their stated verification status. Hypotheses are proposals.",
        ]
        evidence_lookup = {item.evidence_id: item for item in state.evidence}
        papers = {item.paper.paper_id: item.paper for item in state.candidates}
        for claim in state.claims:
            report += [
                f"### Claim {claim.claim_id}",
                f"{md(claim.statement)} [{claim.claim_type}; {claim.verification_status}]",
            ]
            for identity in claim.evidence_ids:
                item = evidence_lookup.get(identity)
                if item and item.paper_id in papers:
                    paper = papers[item.paper_id]
                    report += [
                        f"Evidence {identity} → Paper {paper.paper_id}: {md(paper.metadata.title)}; DOI: {md(paper.metadata.doi or 'unavailable')}; URL: {md(paper.metadata.url or 'unavailable')}; location: {md(item.source_location)}; page: {item.page}; section: {md(item.section or 'unavailable')}; table: {md(item.table or 'unavailable')}; figure: {md(item.figure or 'unavailable')}."
                    ]
        report += [
            "## Limitations",
            *[f"- {md(item)}" for item in state.limitations],
            "## Operational warnings",
            *[f"- {md(item)}" for item in state.warnings],
            "## Scope",
            "Search coverage is limited to logged queries and enabled adapters. Absence from this corpus does not establish universal novelty. See the accompanying evidence, audit and attack records.",
        ]
        write("final_report.md", "\n\n".join(report) + "\n")
        executions = self.repository.list_all("model_executions", ModelExecution, run.run_id)
        json_file(
            "run_manifest.json",
            {
                "run": run.model_dump(mode="json"),
                "exported_at": utcnow().isoformat(),
                "config_fingerprint": run.config_fingerprint,
                "publication_ready": publication,
                "novelty_iterations": state.novelty_iteration,
                "search_saturation": [item.model_dump(mode="json") for item in state.saturation],
                "evidence_conflicts": [item.model_dump(mode="json") for item in state.conflicts],
                "targeted_search_requests": [
                    item.model_dump(mode="json") for item in state.targeted_requests
                ],
                "knowledge_map": state.knowledge_map.model_dump(mode="json")
                if state.knowledge_map
                else None,
                "workflow_events": [item.model_dump(mode="json") for item in state.events],
                "source_chunks": [
                    item.model_dump(mode="json", exclude={"text"}) for item in state.chunks
                ],
                "model_calls": len(executions),
                "search_attempts": [
                    attempt.model_dump(mode="json") for attempt in state.search_history
                ],
                "input_tokens": sum(item.input_tokens for item in executions),
                "output_tokens": sum(item.output_tokens for item in executions),
                "estimated_cost_usd": sum(item.estimated_cost or 0 for item in executions),
                "cost_complete": all(item.estimated_cost is not None for item in executions),
                "cost_includes_upper_bounds": any(
                    item.cost_basis == "reserved_upper_bound" for item in executions
                ),
                "gates": [item.model_dump(mode="json") for item in state.gates],
                "files": {
                    path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in sorted(target.iterdir())
                    if path.is_file() and path.name != "run_manifest.json"
                },
            },
        )
        return target
