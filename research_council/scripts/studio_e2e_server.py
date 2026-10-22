"""Isolated fixture-only browser test server; all outbound Python HTTP is forbidden."""

import tempfile
from pathlib import Path

import httpx
import uvicorn

from research_council.studio.app import create_app


async def forbidden_network(*args, **kwargs):
    raise AssertionError("Studio E2E forbids outbound HTTP, paid providers and live research")


httpx.AsyncClient.send = forbidden_network
workspace = Path(tempfile.mkdtemp(prefix="research-council-studio-e2e-"))
uvicorn.run(create_app(workspace), host="127.0.0.1", port=8765, log_level="warning")
