from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path

from research_council.core.config import Settings
from research_council.core.orchestration.state import WorkflowState
from research_council.schemas.models import ModelExecution, ResearchRun, utcnow
from research_council.validation.benchmark import benchmark_hash


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def reproducibility_manifest(
    run: ResearchRun, state: WorkflowState, settings: Settings, executions: list[ModelExecution]
) -> dict[str, object]:
    package = Path(__file__).parents[1]
    try:
        git = shutil.which("git") or "C:/Program Files/Git/cmd/git.exe"
        revision = subprocess.run(
            [git, "rev-parse", "HEAD"], capture_output=True, text=True, timeout=5
        )
        status = subprocess.run(
            [git, "status", "--porcelain"], capture_output=True, text=True, timeout=5
        )
        commit = revision.stdout.strip() if revision.returncode == 0 else None
        dirty = bool(status.stdout) if status.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        commit, dirty = None, None
    prompt_root = package / "prompts"
    if not prompt_root.is_dir():
        prompt_root = package.parents[1] / "prompts"
    source_files = sorted(package.rglob("*.py"))
    source_digest = hashlib.sha256()
    for path in source_files:
        source_digest.update(path.relative_to(package).as_posix().encode())
        source_digest.update(path.read_bytes())
    return {
        "run_id": str(run.run_id),
        "created_at": utcnow().isoformat(),
        "commit_sha": commit,
        "working_tree_dirty": dirty,
        "source_tree_sha256": source_digest.hexdigest(),
        "config_hash": settings.fingerprint(),
        "benchmark_hash": benchmark_hash(),
        "workflow_version": run.workflow_version,
        "state_schema_version": state.schema_version,
        "prompt_versions": {
            path.name: sha256(path.read_bytes()) for path in sorted(prompt_root.glob("*.md"))
        },
        "search_sources": settings.search.adapters,
        "queries": [query.model_dump(mode="json") for query in state.queries],
        "search_attempts": [attempt.model_dump(mode="json") for attempt in state.search_history],
        "paper_identities": [
            item.paper.metadata.model_dump(mode="json")
            | {"paper_id": str(item.paper.paper_id), "provenance": item.paper.provenance}
            for item in state.candidates
        ],
        "identity_audits": [item.model_dump(mode="json") for item in state.identity_audits],
        "evidence_hashes": {
            str(item.evidence_id): sha256(item.model_dump_json().encode())
            for item in state.evidence
        },
        "source_hashes": {str(item.chunk_id): item.source_sha256 for item in state.chunks},
        "model_executions": [item.model_dump(mode="json") for item in executions],
        "budget": settings.live_research_budget.model_dump(mode="json")
        if settings.live_research_budget
        else None,
        "estimated_model_cost_usd": sum(item.estimated_cost or 0 for item in executions),
        "actual_billed_cost_usd": None,
        "live_execution": run.provenance == "live",
        "human_judgments_inferred": False,
        "interpretation": "Reproducibility record, not proof of scientific correctness. Unknown installed-source commit IDs remain null; source and prompt hashes are retained.",
    }
