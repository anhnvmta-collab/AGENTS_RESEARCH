from __future__ import annotations

import re
from typing import Any
from uuid import UUID, uuid4

from fastapi import UploadFile

from research_council.core.security import workspace_path
from research_council.studio.service import StudioService
from research_council.tools.local import LocalDocumentAdapter

MAX_DOCUMENT_BYTES = 20_000_000


async def upload(
    service: StudioService, identity: UUID, files: list[UploadFile]
) -> list[dict[str, Any]]:
    service.project(identity)
    if not files or len(files) > 10:
        raise ValueError("Select between 1 and 10 PDFs")
    result = []
    for file in files:
        filename = re.sub(
            r"[^\w. -]", "_", (file.filename or "paper.pdf").replace("\\", "/").rsplit("/", 1)[-1]
        )[:120]
        if not filename.lower().endswith(".pdf") or file.content_type not in {
            "application/pdf",
            "application/octet-stream",
        }:
            raise ValueError("Only PDFs are supported")
        document_id = str(uuid4())
        relative = f"documents/{identity}/{document_id}.pdf"
        path = workspace_path(service.workspace, relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        size = 0
        try:
            with path.open("xb") as target:
                while chunk := await file.read(65536):
                    size += len(chunk)
                    if size > MAX_DOCUMENT_BYTES:
                        raise ValueError("PDF exceeds size limit")
                    if size == len(chunk) and not chunk.startswith(b"%PDF-"):
                        raise ValueError("Invalid PDF signature")
                    target.write(chunk)
            record = {
                "id": document_id,
                "project_id": str(identity),
                "filename": filename,
                "path": relative,
                "bytes": size,
                "status": "PARSING",
                "agent": "LocalDocumentScout",
                "job_status": "QUEUED_FOR_NEXT_RUN",
                "untrusted": True,
            }
            service.store.put("document", document_id, record)
            try:
                paper = await LocalDocumentAdapter(service.workspace).read(relative)
                if not paper.source_text or not paper.source_text.strip():
                    raise ValueError("PDF has no extractable text; OCR is required")
                record.update(
                    status="PARSED", paper_id=str(paper.paper_id), title=paper.metadata.title
                )
            except Exception as exc:
                record.update(status="FAILED", error_type=type(exc).__name__, job_status="BLOCKED")
            service.store.put("document", document_id, record)
            result.append(record)
        except Exception:
            path.unlink(missing_ok=True)
            raise
        finally:
            await file.close()
    return result
