import csv
from uuid import uuid4

from test_regressions import human_ready_state

from research_council.core.config import Settings
from research_council.validation.export import export_review_package


def test_human_review_package_has_blank_random_judgments(repository, tmp_path):
    _, run = repository
    state = human_ready_state()
    state.core_paper_ids = [state.candidates[0].paper.paper_id]
    state.evidence = [
        state.evidence[0].model_copy(update={"evidence_id": uuid4()}) for _ in range(25)
    ]
    target = export_review_package(tmp_path, run, state, Settings(), [])
    expected = {
        "top_core_papers.csv",
        "evidence_review.csv",
        "gap_review.md",
        "novelty_review.md",
        "closest_prior_art.csv",
        "hardware_review.md",
        "model_disagreement.csv",
        "review_checklist.md",
    }
    assert {path.name for path in (target / "human_review").iterdir()} == expected
    with (target / "human_review/evidence_review.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 20
    assert all(
        not row[column]
        for row in rows
        for column in [
            "human_location_correct",
            "human_entailment_correct",
            "human_interpretation_correct",
            "notes",
        ]
    )
    assert (target / "model_benchmark.csv").is_file() and (
        target / "hardware_assumptions.csv"
    ).is_file()
