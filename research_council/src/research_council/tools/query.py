from __future__ import annotations

import re

from research_council.schemas.models import SearchQuery


class QueryExpander:
    def __init__(self, synonyms: dict[str, str] | None = None) -> None:
        self.synonyms = synonyms or {
            "FHSS": "frequency hopping spread spectrum",
            "DOA": "direction of arrival",
            "FPGA": "field programmable gate array",
            "SDR": "software defined radio",
            "RFSoC": "RF system on chip",
            "compressed sensing": "compressive sensing",
            "sparse recovery": "sparse reconstruction",
        }

    def expand(self, topic: str, limit: int = 12) -> list[SearchQuery]:
        base = " ".join(topic.split())[:1600]
        expanded = base
        for word, replacement in self.synonyms.items():
            expanded = re.sub(r"\b" + re.escape(word) + r"\b", replacement, expanded, flags=re.I)
        variants = [
            (base, "broad"),
            (f'"{base}"', "exact"),
            (expanded[:1900], "synonym"),
            (base + " algorithm method complexity", "algorithm"),
            (base + " hardware real-time implementation", "hardware"),
            (base + " application experimental evaluation", "application"),
            (base, "recent"),
            (base + " foundational methods", "seminal"),
        ]
        return [
            SearchQuery.model_validate({"text": text, "strategy": strategy})
            for text, strategy in variants[:limit]
        ]
