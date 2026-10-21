from __future__ import annotations

import json
from pathlib import Path

from research_council.core.security import workspace_path
from research_council.schemas.models import ResearchQuestion, utcnow

BENCHMARK_QUESTION = ResearchQuestion(
    topic="Compressed Sensing for Real-Time Detection, Parameter Estimation and DOA of FHSS UAV Signals on Coherent SDR/FPGA Platforms",
    constraints=[
        "FHSS 500-1000 hops/s",
        "Coherent multi-channel SDR",
        "FPGA / RFSoC / Zynq-class platform",
        "Sparse recovery and wideband sensing",
        "Cross-channel coherence",
        "Real-time detection, parameter estimation and DOA",
    ],
)


def prepare_benchmark(workspace: Path, question: ResearchQuestion | None = None) -> Path:
    path = workspace_path(workspace, "benchmarks/fhss/preparation.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "status": "BENCHMARK_READY_BUT_NOT_EXECUTED",
                "prepared_at": utcnow().isoformat(),
                "question": (question or BENCHMARK_QUESTION).model_dump(mode="json"),
                "findings": [],
                "measured_results": [],
                "requirements": [
                    "Configure model IDs and prices",
                    "Provide provider keys through environment",
                    "Enable scholarly adapters or authorized local documents",
                    "Run --live explicitly and review evidence/gates",
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return path
