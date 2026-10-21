from research_council.agents.base import BaseResearchAgent
from research_council.agents.contracts import JudgmentInput, NoveltyDecision
from research_council.schemas.models import TaskProfile


class NoveltyJudge(BaseResearchAgent[JudgmentInput, NoveltyDecision]):
    name = "NoveltyJudge"
    role = "Judge independent prior-art attack and skeptical review against evidence. Do not average scores. Return REJECT/REVISE/SURVIVE with confidence, closest art, follow-up searches and risks. Incomplete reports cannot support survival."
    task_profile = TaskProfile.ADVERSARIAL_REVIEW
    allowed_tools = frozenset(["evidence_read"])
    input_schema = JudgmentInput
    output_schema = NoveltyDecision
    prompt_file = "novelty_judge.md"
