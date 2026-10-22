from __future__ import annotations

import io
import zipfile
from typing import Any
from uuid import UUID, uuid4

from research_council.core.orchestration.state import WorkflowState
from research_council.exporters import MarkdownExporter
from research_council.schemas.models import utcnow
from research_council.studio.models import Revision
from research_council.studio.service import StudioService

SECTIONS = [
    "Title",
    "Abstract",
    "Keywords",
    "Introduction",
    "Related Work",
    "System Model",
    "Proposed Method",
    "Implementation",
    "Experiments",
    "Results",
    "Discussion",
    "Limitations",
    "Conclusion",
    "References",
]


def revision(service: StudioService, identity: UUID, request: Revision) -> dict[str, Any]:
    service.repository.get_run(identity)
    previous = [
        row
        for row in service.store.list("revision")
        if row["run_id"] == str(identity)
        and row["kind"] == request.kind
        and row["target"] == request.target
    ]
    record = {
        **request.model_dump(mode="json"),
        "id": str(uuid4()),
        "run_id": str(identity),
        "revision": len(previous) + 1,
        "at": utcnow().isoformat(),
        "canonical_mutation": False,
    }
    return service.store.put("revision", record["id"], record)


def paper_sections(
    service: StudioService, identity: UUID, *, include_revisions: bool = True
) -> list[dict[str, Any]]:
    snapshot = service.snapshot(identity)
    state = snapshot["state"]
    if snapshot.get("practice_design") and not state["outline"]["sections"]:
        state = {**state, "outline": snapshot["practice_design"]["outline"]}
    revisions = (
        [
            row
            for row in service.store.list("revision")
            if row["run_id"] == str(identity) and row["kind"] == "paper"
        ]
        if include_revisions
        else []
    )
    claims = [row for row in state["claims"] if row["claim_id"] in state["outline"]["claim_ids"]]
    evidence_ids = {eid for claim in claims for eid in claim["evidence_ids"]}
    result = []
    for section in SECTIONS:
        latest = next((r for r in reversed(revisions) if r["target"] == section), None)
        plan: list[str] = next(
            (
                value
                for key, value in state["outline"]["sections"].items()
                if key.casefold() == section.casefold()
            ),
            [],
        )
        if section == "Title":
            content = state["outline"]["title"]
        elif section == "Keywords":
            content = ", ".join(service.project(UUID(snapshot["run"]["project_id"])).keywords)
        elif section == "References":
            content = "\n".join(
                f"[{index}] {c['paper']['metadata']['title']} ({c['paper']['metadata'].get('year') or 'year unknown'}). DOI: {c['paper']['metadata'].get('doi') or 'unverified / absent'}"
                for index, c in enumerate(state["candidates"], 1)
            )
        elif section == "Limitations":
            content = "\n".join(state["limitations"] + state["outline"]["limitations"])
        else:
            content = (
                "\n".join(plan)
                + "\n\n"
                + (
                    "\n".join(
                        "[" + c["verification_status"] + "] " + c["statement"] for c in claims
                    )
                    if claims
                    else "MISSING EVIDENCE: no supporting claims assigned by PaperArchitect."
                )
            )
        result.append(
            {
                "section": section,
                "status": latest["status"] if latest else "PLANNED" if plan else "MISSING_EVIDENCE",
                "content": latest["content"] if latest else content.strip(),
                "claims": [c["claim_id"] for c in claims],
                "evidence": sorted(evidence_ids),
                "missing_evidence": [
                    c["claim_id"] for c in claims if c["verification_status"] != "VERIFIED"
                ]
                or ([] if claims else ["No verified supporting claims assigned"]),
                "revision": latest["revision"] if latest else 0,
            }
        )
    return result


def export_zip(service: StudioService, identity: UUID) -> bytes:
    if identity in service.jobs and not service.jobs[identity].done():
        raise RuntimeError("Wait for a checkpoint before export")
    run = service.repository.get_run(identity)
    state = WorkflowState.model_validate(service.repository.artifacts(identity).get("state", {}))
    directory = MarkdownExporter(service.workspace, service.repository).export(run, state)
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(directory.iterdir()):
            if path.is_file() and not path.is_symlink() and path.suffix != ".tmp":
                archive.write(path, arcname=path.name)
        import json

        archive.writestr(
            "studio_revisions.json",
            json.dumps(
                [row for row in service.store.list("revision") if row["run_id"] == str(identity)],
                ensure_ascii=False,
                indent=2,
            ),
        )
        archive.writestr(
            "studio_human_decisions.json",
            json.dumps(
                [row for row in service.store.list("decision") if row["run_id"] == str(identity)],
                ensure_ascii=False,
                indent=2,
            ),
        )
        archive.writestr(
            "studio_practice_advisory.json",
            json.dumps(service.store.list("practice_design"), ensure_ascii=False, indent=2),
        )
    return output.getvalue()
