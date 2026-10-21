import json

import pytest
import yaml

from research_council.agents.contracts import AuditInput, ReadingInput
from research_council.agents.deep_reader import DeepReader
from research_council.core.config import Settings
from research_council.core.routing import ModelRouter
from research_council.providers.base import LLMResponse
from research_council.providers.fake import FakeProvider
from research_council.schemas.models import CitationObservation, Evidence, Paper, PriorArtReport
from research_council.tools.audit import CitationAuditService
from research_council.validation.benchmark import benchmark_directory
from research_council.validation.controls import (
    novelty_coverage_status,
    unchanged_method_control,
    verify_reference_title,
)
from research_council.validation.coverage import load_seeds, verified_citation_edges


def test_curated_seed_references_have_primary_source_provenance():
    seeds = load_seeds()
    assert len(seeds) == 3 and all(
        seed.metadata.doi and seed.identity_sources and seed.verified_on for seed in seeds
    )
    assert any(seed.metadata.doi == "10.48550/arxiv.0803.2392" for seed in seeds)


@pytest.mark.parametrize("case_index", range(3))
async def test_real_known_answer_excerpts_recover_grounding_with_fake_contract(
    case_index, repository
):
    # Real source text, but fake output: tests provenance/validation only, not model capability.
    import asyncio

    cases = yaml.safe_load(
        (benchmark_directory() / "known_answers.yaml").read_text(encoding="utf-8")
    )["cases"]
    case = cases[case_index]
    seed = next(item for item in load_seeds() if item.identifier == case["seed_id"])
    paper = Paper(
        metadata=seed.metadata,
        provenance="local",
        source_kind="abstract",
        source_text=case["excerpt"],
    )
    evidence = Evidence(
        paper_id=paper.paper_id,
        evidence_type=case["field"],
        source_location="abstract",
        verbatim_excerpt=case["excerpt"],
        normalized_statement=case["normalized_statement"],
        extraction_agent="DeepReader",
    )
    provider = FakeProvider(
        [
            LLMResponse(
                text=json.dumps(
                    {
                        "evidence": [evidence.model_dump(mode="json")],
                        "extractions": [
                            {
                                "field": case["field"],
                                "value": case["normalized_statement"],
                                "evidence_ids": [str(evidence.evidence_id)],
                            }
                        ],
                    }
                )
            )
        ]
    )
    repo, run = repository
    output = await DeepReader(ModelRouter(Settings(), {"fake": provider}, repo, run.run_id)).run(
        ReadingInput(
            task="Recover the source-stated method, limitation or hardware result", paper=paper
        )
    )
    assert output.evidence[0].verbatim_excerpt == case["excerpt"]
    assert output.evidence[0].verification_status == "PARTIALLY_VERIFIED"

    class MetadataSnapshot:
        name = "curated_snapshot"

        async def resolve(self, doi):
            return seed.metadata

    audit = await CitationAuditService([MetadataSnapshot()], asyncio.Semaphore(1)).audit(
        AuditInput(
            task="Known identity control", papers=[paper], claims=[], evidence=output.evidence
        )
    )
    assert audit.audits[0].checks["doi"] is True
    assert audit.audits[0].status != "VERIFIED"


def test_hallucinated_paper_request_does_not_create_metadata():
    title = "Quantum-Coherent OMP FHSS Oracle for 997-Hop UAVs: An Invented Benchmark Reference"
    result = verify_reference_title(title, [Paper(metadata=seed.metadata) for seed in load_seeds()])
    assert result.status == "NOT_FOUND_IN_SEARCHED_SOURCES" and not result.matches
    assert "doi" not in result.__class__.model_fields


def test_weak_novelty_and_missing_search_cannot_be_promoted():
    from test_novelty import candidate_and_evidence

    candidate, _ = candidate_and_evidence()
    candidate.is_negative_control = True
    candidate.mathematical_change, candidate.implementation_change = "NONE", "NONE"
    assert unchanged_method_control(candidate)
    assert (
        novelty_coverage_status(PriorArtReport(candidate_id=candidate.candidate_id, revision=1))
        == "INSUFFICIENT_SEARCH_COVERAGE"
    )


def test_citation_chain_recovery_requires_verified_directional_edges():
    observations = [
        CitationObservation(
            seed_identifier="a", target_identifier="b", direction="related", adapter="crossref"
        ),
        CitationObservation(
            seed_identifier="a",
            target_identifier="c",
            direction="forward",
            adapter="openalex",
            relation_verified=True,
        ),
    ]
    assert verified_citation_edges(observations) == {("c", "a")}
