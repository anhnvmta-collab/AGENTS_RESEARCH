from research_council.agents.base import BaseResearchAgent
from research_council.agents.contracts import CandidatesOutput, SearchInput
from research_council.schemas.models import TaskProfile


class LocalDocumentScout(BaseResearchAgent[SearchInput, CandidatesOutput]):
    name = "LocalDocumentScout"
    role = "Read bounded local PDFs/text within the workspace; parsing failure is not a finding."
    task_profile = TaskProfile.PAPER_EXTRACTION
    allowed_tools = frozenset(["local_read"])
    input_schema = SearchInput
    output_schema = CandidatesOutput
    prompt_file = "local_document_scout.md"
