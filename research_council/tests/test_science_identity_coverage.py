from uuid import uuid4

import pytest

from research_council.schemas.models import Paper, PaperCandidate, PaperMetadata
from research_council.validation.coverage import SeedPaper, coverage_report
from research_council.validation.identity import audit_identity, retain_identity_observations
from research_council.validation.triage import diverse_shortlist


def metadata(**updates):
    values = dict(
        title="Unit identity source",
        authors=["Test Author"],
        year=2020,
        doi="10.1234/unit",
        metadata_source="crossref",
        metadata_verified=True,
    )
    return PaperMetadata(**(values | updates))


@pytest.mark.parametrize(
    "change, conflict",
    [
        ({"title": "Different title"}, "SAME_DOI_DIFFERENT_TITLE"),
        ({"doi": "10.1234/other"}, "SAME_TITLE_DIFFERENT_DOI"),
        ({"year": 2021}, "YEAR_MISMATCH"),
        ({"authors": ["Other Author"]}, "AUTHOR_MISMATCH"),
    ],
)
def test_paper_identity_conflicts(change, conflict):
    paper = Paper(metadata=metadata())
    audit = audit_identity(paper, [metadata(**change)])
    assert audit.status == "CONTRADICTED" and conflict in audit.conflicts
    assert audit_identity(paper, []).status == "UNVERIFIED"
    assert audit_identity(paper, [metadata()]).status == "VERIFIED"
    paper.provenance = "fixture"
    assert audit_identity(paper, [metadata()]).status == "UNVERIFIED"


def test_identity_observations_survive_deduplication():
    from research_council.tools.discovery import PaperDeduplicator

    candidates = [
        PaperCandidate(paper=Paper(metadata=metadata())),
        PaperCandidate(paper=Paper(metadata=metadata(title="Different source title"))),
    ]
    observed = {}
    retain_identity_observations(observed, candidates)
    reduced = PaperDeduplicator().deduplicate(candidates)
    assert len(reduced) == 1 and len(observed["doi:10.1234/unit"]) == 2
    assert audit_identity(reduced[0].paper, observed["doi:10.1234/unit"]).conflicts


def test_seed_method_concept_and_citation_coverage_are_scoped():
    # This is a metric unit fixture, explicitly not a curated literature seed.
    seed = SeedPaper(
        identifier="unit",
        metadata=metadata(),
        identity_sources=["https://unit.test/identity"],
        verified_on="2026-10-21",
        verification_basis="UNIT METRIC FIXTURE, not a published seed",
    )
    paper = Paper(
        metadata=metadata(
            title="OMP FPGA unit example", abstract="Sparse recovery FPGA implementation"
        )
    )
    result = coverage_report(
        [paper],
        [seed],
        {"OMP": ["OMP"], "ADMM": ["ADMM"]},
        {"FPGA": ["FPGA"]},
        expected_citation_edges={("a", "b")},
        observed_citation_edges={("a", "b")},
    )
    assert result.seed_paper_recall.value == 1
    assert result.method_family_recall.value == 0.5 and result.concept_coverage.value == 1
    assert result.citation_chain_recovery.value == 1
    assert coverage_report([], [], {}, {}).seed_paper_recall.value is None
    paper.provenance = "fixture"
    assert coverage_report([paper], [seed], {}, {}).seed_paper_recall.value == 0


def test_diversity_shortlist_retains_old_and_implementation_papers():
    def candidate(title, year, score):
        return PaperCandidate(
            paper=Paper(paper_id=uuid4(), metadata=metadata(title=title, year=year)),
            aggregate_score=score,
        )

    top = candidate("High scoring paper", 2023, 0.95)
    duplicate = candidate("Second high scoring paper", 2023, 0.9)
    old = candidate("Seminal sparse reconstruction", 2008, 0.2)
    hardware = candidate("OMP FPGA implementation", 2026, 0.1)
    result = diverse_shortlist([top, duplicate, old, hardware], 3, {"OMP": ["OMP"]}, 2026)
    assert set(result.paper_ids) == {
        top.paper.paper_id,
        old.paper.paper_id,
        hardware.paper.paper_id,
    }
