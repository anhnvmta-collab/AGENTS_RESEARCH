"""Explicitly synthetic scenario for demonstrations and offline integration testing only."""

from __future__ import annotations

import json
from uuid import NAMESPACE_URL, UUID, uuid5

from research_council.providers.base import LLMRequest, LLMResponse
from research_council.schemas.models import (
    ClaimType,
    Evidence,
    Gap,
    GapType,
    NoveltyCandidate,
    Paper,
    PaperMetadata,
    ResearchClaim,
    SearchQuery,
)


class SyntheticSearchAdapter:
    name = "fixture"

    def __init__(self) -> None:
        self.papers = [
            Paper(
                paper_id=uuid5(NAMESPACE_URL, f"research-council-fixture-{index}"),
                metadata=PaperMetadata(
                    title=f"[SYNTHETIC FIXTURE] Receiver test record {index}",
                    authors=["Fictional Fixture Author"],
                    year=2024,
                    url=f"https://example.invalid/fixture-{index}",
                    metadata_source="fixture",
                ),
                provenance="fixture",
                source_kind="fixture",
                source_text="SYNTHETIC FIXTURE: streaming latency and fixed-point accuracy were not evaluated.",
            )
            for index in (1, 2)
        ]

    async def search(self, query: SearchQuery, limit: int) -> list[Paper]:
        return [paper.model_copy(deep=True) for paper in self.papers[:limit]]

    async def explore(self, paper: Paper, direction: str, limit: int) -> list[Paper]:
        return await self.search(SearchQuery(text="synthetic fixture"), limit)


def synthetic_response(request: LLMRequest) -> LLMResponse:
    """Return test artifacts, not findings about actual scientific literature."""
    data = json.loads(request.user)["untrusted_task_data"]
    role = request.role
    result: dict[str, object] = {}
    if role == "ResearchPlanner":
        result = {
            "objective": "SYNTHETIC workflow exercise; no real literature results.",
            "tasks": ["Discover fixtures", "Validate provenance", "Exercise skeptical review"],
        }
    elif role == "PerspectiveGenerator":
        result = {
            "perspectives": [
                {"name": name, "questions": ["Which evidence is missing?"]}
                for name in ("theoretical", "hardware", "experimental")
            ]
        }
    elif role == "QueryPlanner":
        result = {
            "queries": [
                {"text": "synthetic receiver fixture", "strategy": "broad"},
                {"text": "synthetic real-time fixture", "strategy": "hardware"},
            ]
        }
    elif role == "DeepReader":
        paper = Paper.model_validate(data["paper"])
        source_text = data.get("chunks", [{}])[0].get("text") or paper.source_text or ""
        evidence = Evidence(
            evidence_id=uuid5(paper.paper_id, "evidence"),
            paper_id=paper.paper_id,
            evidence_type="fixture limitation",
            source_location="synthetic text",
            verbatim_excerpt=source_text,
            normalized_statement="Synthetic fixture omitted latency/fixed-point evaluation.",
            extraction_agent="DeepReader",
        )
        claim = ResearchClaim(
            claim_id=uuid5(paper.paper_id, "claim"),
            statement=evidence.normalized_statement,
            claim_type=ClaimType.AUTHOR_REPORTED,
            source_paper_ids=[paper.paper_id],
            evidence_ids=[evidence.evidence_id],
        )
        result = {
            "evidence": [evidence.model_dump(mode="json")],
            "claims": [claim.model_dump(mode="json")],
            "extractions": [
                {
                    "field": "authors_limitations",
                    "value": evidence.normalized_statement,
                    "evidence_ids": [str(evidence.evidence_id)],
                }
            ],
            "limitations": ["SYNTHETIC FIXTURE — not scientific evidence."],
        }
    elif role == "GapMiner" and data.get("evidence"):
        gap_evidence = [Evidence.model_validate(item) for item in data["evidence"]]
        gap = Gap(
            gap_id=uuid5(NAMESPACE_URL, "fixture-gap"),
            gap_type=GapType.REAL_TIME,
            evidence_ids=[item.evidence_id for item in gap_evidence],
            claim_ids=[UUID(item["claim_id"]) for item in data["claims"]],
            limitation="Synthetic fixtures omit measured latency.",
            consequence="Fixture cannot establish real-time operation.",
            opportunity="Test latency under explicit synthetic assumptions.",
            search_scope="Synthetic fixtures only.",
        )
        result = {"gaps": [gap.model_dump(mode="json")]}
    elif role == "NoveltyGenerator" and data.get("gaps"):
        gap = Gap.model_validate(data["gaps"][0])
        prior = data.get("previous_candidates", [])
        candidate = NoveltyCandidate(
            candidate_id=uuid5(NAMESPACE_URL, "fixture-novelty"),
            revision=max((item["revision"] for item in prior), default=0) + 1,
            gap_ids=[gap.gap_id],
            evidence_ids=gap.evidence_ids,
            normalized_claim="SYNTHETIC HYPOTHESIS: evaluate streaming latency of a fixture receiver.",
            keywords=["synthetic receiver", "streaming latency"],
            what_is_new="Unverified synthetic proposal",
            why_it_matters="Exercise the workflow",
            why_prior_methods_insufficient="Not established by real sources",
            proposed_method="Design a synthetic latency experiment",
            validation_plan="Compare synthetic baselines; do not report measured results.",
        )
        result = {"candidates": [candidate.model_dump(mode="json")]}
    elif role == "PriorArtHunter":
        result = {
            "candidate_id": data["candidate_id"],
            "revision": data["revision"],
            "complete": False,
        }
    elif role == "ReviewerTwo":
        result = {
            "candidate_id": data["candidate_id"],
            "revision": data["revision"],
            "verdict": "MAJOR_REVISION",
            "reasons": [
                {
                    "category": "evidence",
                    "severity": "HIGH",
                    "explanation": "Synthetic fixtures cannot demonstrate actual novelty or experimental sufficiency.",
                }
            ],
        }
    elif role == "NoveltyJudge":
        candidate_data = data["candidate"]
        result = {
            "candidate_id": candidate_data["candidate_id"],
            "revision": candidate_data["revision"],
            "verdict": "REVISE",
            "required_followup_searches": ["synthetic latency prior art"],
            "remaining_risks": ["No real scientific evidence."],
        }
    elif role == "HardwareArchitect":
        result = {
            "feasibility": "YELLOW",
            "justification": "SYNTHETIC fixture lacks implementation measurements.",
            "evidence_ids": [item["evidence_id"] for item in data.get("evidence", [])],
            "paper_ids": [item["paper_id"] for item in data.get("papers", [])],
        }
    elif role == "ExperimentDesigner":
        result = {
            "objective": "SYNTHETIC experiment plan only",
            "hypothesis": "Unverified synthetic pipeline hypothesis: deadline is met without degraded detection.",
            "baselines": ["Reference floating-point implementation"],
            "metrics": ["Latency", "Detection probability", "DOA error", "FPGA resources"],
            "procedures": [
                "Pre-register hypotheses, seeds and hop-rate sweep; measure rather than assume."
            ],
            "limitations": ["No experimental data collected."],
            "ablations": ["Disable sparse recovery; compare identical inputs and budgets"],
            "statistical_plan": "Pre-register paired seeds, sample size and 95% confidence intervals.",
            "failure_cases": ["Low SNR, missed hops, calibration drift and deadline overruns"],
            "acceptance_criteria": [
                "Pre-register error and deadline thresholds before data collection"
            ],
            "reproducibility": [
                "Record seeds, source hashes, tool versions and hardware configuration"
            ],
            "progression": [
                "Simulation",
                "Synthetic IQ",
                "Recorded IQ",
                "SDR",
                "FPGA/RFSoC",
                "RF experiment if appropriate",
            ],
        }
    elif role == "PaperArchitect":
        result = {
            "title": "SYNTHETIC research roadmap",
            "sections": {
                "Introduction": ["State an unverified hypothesis"],
                "Evaluation": ["Collect real evidence and reproducible measurements"],
            },
            "limitations": ["No publication readiness established."],
        }
    return LLMResponse(text=json.dumps(result), input_tokens=100, output_tokens=50)
