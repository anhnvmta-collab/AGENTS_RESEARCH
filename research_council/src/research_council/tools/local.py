from __future__ import annotations

import asyncio
import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from pypdf import PdfReader

from research_council.core.security import sanitize_text, workspace_path
from research_council.schemas.models import Paper, PaperMetadata


class LocalDocumentAdapter:
    name = "local"

    def __init__(
        self, workspace: Path, *, max_bytes: int = 20_000_000, max_pages: int = 300
    ) -> None:
        self.workspace = workspace
        self.max_bytes = max_bytes
        self.max_pages = max_pages

    async def read(self, name: str) -> Paper:
        path = workspace_path(self.workspace, name)
        if not path.is_file() or path.stat().st_size > self.max_bytes:
            raise ValueError("Local source missing or exceeds size limit")
        return await asyncio.to_thread(self._read, path)

    def _read(self, path: Path) -> Paper:
        page_texts: dict[int, str] = {}
        title = path.stem
        authors: list[str] = []
        year: int | None = None
        if path.suffix.lower() == ".pdf":
            reader = PdfReader(path)
            if reader.is_encrypted:
                raise ValueError("Encrypted PDF is not supported")
            metadata = reader.metadata
            if metadata:
                title = metadata.title or title
                authors = [metadata.author] if metadata.author else []
            remaining = 100_000
            for index, page in enumerate(reader.pages[: self.max_pages], 1):
                text = sanitize_text(page.extract_text() or "", remaining)
                page_texts[index] = text
                remaining -= len(text)
                if remaining <= 0:
                    break
            text = "\n".join(page_texts.values())[:100_000]
        elif path.suffix.lower() in (".txt", ".md"):
            text = sanitize_text(path.read_text(encoding="utf-8"))
            page_texts = {1: text}
        else:
            raise ValueError("Only PDF, TXT and Markdown sources are supported")
        meta = PaperMetadata(title=title, authors=authors, year=year, metadata_source="local")
        sidecar = workspace_path(
            self.workspace, str(path.relative_to(self.workspace.resolve())) + ".metadata.json"
        )
        if sidecar.is_file():
            if sidecar.stat().st_size > 50_000:
                raise ValueError("Local metadata sidecar exceeds size limit")
            payload = json.loads(sidecar.read_text(encoding="utf-8"))
            payload.update(metadata_source="local_sidecar", metadata_verified=False)
            meta = PaperMetadata.model_validate(payload)
        return Paper(
            paper_id=uuid5(NAMESPACE_URL, "local:" + str(path)),
            metadata=meta,
            provenance="local",
            source_text=text,
            source_kind="local_pdf" if path.suffix.lower() == ".pdf" else "full_text",
            source_path=str(path.relative_to(self.workspace.resolve())),
            page_texts=page_texts,
        )
