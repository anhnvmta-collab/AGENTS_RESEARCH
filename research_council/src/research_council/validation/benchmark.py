from __future__ import annotations

import hashlib
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import yaml
from pydantic import Field, model_validator

from research_council.schemas.models import ResearchQuestion, Schema, SearchQuery

BENCHMARK_ID = "CS_FHSS_DOA_FPGA"


class QueryFamily(Schema):
    name: str
    queries: list[str] = Field(min_length=1)
    provenance: str


class BenchmarkDefinition(Schema):
    identifier: str
    version: str
    question: ResearchQuestion
    subquestions: dict[str, ResearchQuestion]
    perspectives: list[str]
    query_families: list[QueryFamily]
    negative_control: str
    notice: str

    @model_validator(mode="after")
    def required_scope(self) -> BenchmarkDefinition:
        if self.identifier == BENCHMARK_ID and not {f"RQ{i}" for i in range(1, 11)}.issubset(
            self.subquestions
        ):
            raise ValueError("FHSS benchmark requires explicit RQ1-RQ10")
        return self

    def queries(self) -> list[SearchQuery]:
        result = []
        for family in self.query_families:
            for text in family.queries:
                result.append(
                    SearchQuery(
                        query_id=uuid5(
                            NAMESPACE_URL, f"{self.identifier}:{self.version}:{family.name}:{text}"
                        ),
                        text=text,
                        strategy="targeted",
                        family=family.name,
                        provenance=family.provenance,
                    )
                )
        return result


def benchmark_directory() -> Path:
    packaged = Path(__file__).parents[1] / "benchmarks/cs_fhss_doa_fpga"
    development = Path(__file__).parents[3] / "benchmarks/cs_fhss_doa_fpga"
    return packaged if packaged.is_dir() else development


def load_benchmark(directory: Path | None = None) -> BenchmarkDefinition:
    root = directory or benchmark_directory()
    return BenchmarkDefinition.model_validate(
        yaml.safe_load((root / "benchmark.yaml").read_text(encoding="utf-8"))
    )


def benchmark_hash(directory: Path | None = None) -> str:
    root = directory or benchmark_directory()
    digest = hashlib.sha256()
    for path in sorted(root.glob("*.yaml")):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()
