from research_council.agents.base import BaseResearchAgent
from research_council.agents.contracts import PriorArtReport, ReviewInput
from research_council.schemas.models import TaskProfile


class PriorArtHunter(BaseResearchAgent[ReviewInput, PriorArtReport]):
    name = "PriorArtHunter"
    role = "Find work that INVALIDATES the normalized claim. Attack exact concepts, synonyms, component combinations, older terminology, recent work, citations and author chains. Rank closest prior art. Missing results do not prove novelty."
    task_profile = TaskProfile.ADVERSARIAL_REVIEW
    allowed_tools = frozenset(["search", "evidence_read"])
    input_schema = ReviewInput
    output_schema = PriorArtReport
    prompt_file = "prior_art_hunter.md"
