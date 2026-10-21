from research_council.agents.base import BaseResearchAgent
from research_council.agents.contracts import ReviewerReport, ReviewInput
from research_council.schemas.models import TaskProfile


class ReviewerTwo(BaseResearchAgent[ReviewInput, ReviewerReport]):
    name = "ReviewerTwo"
    role = "Try to reject as a skeptical IEEE reviewer: novelty, A+B composition, dataset-only change, implementation-only change, weak baselines, unrealistic assumptions, theory, parameter tuning, hardware and experimental sufficiency. Return structured severity and REJECT/MAJOR_REVISION/MINOR_REVISION/SURVIVES."
    task_profile = TaskProfile.ADVERSARIAL_REVIEW
    allowed_tools = frozenset(["evidence_read"])
    input_schema = ReviewInput
    output_schema = ReviewerReport
    prompt_file = "reviewer_two.md"

    async def execute(self, value: ReviewInput) -> ReviewerReport:
        report = await super().execute(value)
        if report.candidate_id != value.candidate_id or report.revision != value.revision:
            raise ValueError("Reviewer candidate mismatch")
        known = {item.evidence_id for item in value.evidence}
        if any(not set(reason.evidence_ids).issubset(known) for reason in report.reasons):
            raise ValueError("Reviewer references unknown evidence")
        report.complete = True
        for reason in report.reasons:
            reason.resolved = False
        return report
