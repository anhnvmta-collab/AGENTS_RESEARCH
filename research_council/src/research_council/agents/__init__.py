"""Role exports are lazy so importing a contract never instantiates the role graph."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .citation_auditor import CitationAuditor
    from .citation_scout import CitationScout
    from .deep_reader import DeepReader
    from .experiment_designer import ExperimentDesigner
    from .final_synthesizer import FinalSynthesizer
    from .gap_miner import GapMiner
    from .hardware_architect import HardwareArchitect
    from .local_document_scout import LocalDocumentScout
    from .math_dsp_analyst import MathDSPAnalyst
    from .novelty_generator import NoveltyGenerator
    from .novelty_judge import NoveltyJudge
    from .paper_architect import PaperArchitect
    from .paper_scout import PaperScout
    from .paper_triage import PaperTriage
    from .perspective_generator import PerspectiveGenerator
    from .prior_art_hunter import PriorArtHunter
    from .query_planner import QueryPlanner
    from .research_director import ResearchDirector
    from .research_planner import ResearchPlanner
    from .reviewer_two import ReviewerTwo

_MODULES = {
    "ResearchDirector": "research_director",
    "ResearchPlanner": "research_planner",
    "PerspectiveGenerator": "perspective_generator",
    "QueryPlanner": "query_planner",
    "PaperScout": "paper_scout",
    "CitationScout": "citation_scout",
    "LocalDocumentScout": "local_document_scout",
    "PaperTriage": "paper_triage",
    "DeepReader": "deep_reader",
    "MathDSPAnalyst": "math_dsp_analyst",
    "HardwareArchitect": "hardware_architect",
    "GapMiner": "gap_miner",
    "NoveltyGenerator": "novelty_generator",
    "PriorArtHunter": "prior_art_hunter",
    "ReviewerTwo": "reviewer_two",
    "NoveltyJudge": "novelty_judge",
    "ExperimentDesigner": "experiment_designer",
    "PaperArchitect": "paper_architect",
    "CitationAuditor": "citation_auditor",
    "FinalSynthesizer": "final_synthesizer",
}


def __getattr__(name: str) -> Any:
    if name not in _MODULES:
        raise AttributeError(name)
    value = getattr(import_module(f"{__name__}.{_MODULES[name]}"), name)
    globals()[name] = value
    return value


__all__ = [
    "ResearchDirector",
    "ResearchPlanner",
    "PerspectiveGenerator",
    "QueryPlanner",
    "PaperScout",
    "CitationScout",
    "LocalDocumentScout",
    "PaperTriage",
    "DeepReader",
    "MathDSPAnalyst",
    "HardwareArchitect",
    "GapMiner",
    "NoveltyGenerator",
    "PriorArtHunter",
    "ReviewerTwo",
    "NoveltyJudge",
    "ExperimentDesigner",
    "PaperArchitect",
    "CitationAuditor",
    "FinalSynthesizer",
]
