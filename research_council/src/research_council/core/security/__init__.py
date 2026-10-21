from __future__ import annotations

import re
from pathlib import Path


def workspace_path(workspace: Path, name: str | Path) -> Path:
    root = workspace.resolve()
    path = (root / name).resolve()
    if not path.is_relative_to(root):
        raise ValueError("Path must remain inside the project workspace")
    return path


def sanitize_text(text: str, limit: int = 100_000) -> str:
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)[:limit]


def csv_safe(value: object) -> str:
    text = str(value) if value is not None else ""
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text
