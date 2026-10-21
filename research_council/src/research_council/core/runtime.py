from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from uuid import UUID

import httpx

from research_council.agents.contracts import AuditInput, SearchInput
from research_council.agents.research_director import ResearchDirector
from research_council.core.config import Settings
from research_council.core.orchestration.pipeline import ResearchPipeline
from research_council.core.routing import ModelRouter
from research_council.core.security import workspace_path
from research_council.core.tracing import JSONLTraceSink
from research_council.providers.base import BaseLLMProvider
from research_council.providers.demo import SyntheticSearchAdapter, synthetic_response
from research_council.providers.fake import FakeProvider
from research_council.providers.http import AnthropicProvider, GeminiProvider, OpenAIProvider
from research_council.repositories.store import SQLRepository
from research_council.schemas.models import Mode, ResearchProject, ResearchQuestion, ResearchRun
from research_council.storage.database import make_engine, migrate
from research_council.tools.arxiv import ArxivAdapter
from research_council.tools.audit import CitationAuditService
from research_council.tools.discovery import DiscoveryService
from research_council.tools.ieee import IEEEAdapter
from research_council.tools.local import LocalDocumentAdapter
from research_council.tools.registry import ToolRegistry
from research_council.tools.search import (
    CitationAdapter,
    CrossrefAdapter,
    MetadataAdapter,
    OpenAlexAdapter,
    SearchAdapter,
)


def open_repository(workspace: Path) -> SQLRepository:
    workspace.mkdir(parents=True, exist_ok=True)
    database = workspace_path(workspace, "council.db")
    engine = make_engine("sqlite:///" + database.as_posix())
    migrate(engine)
    return SQLRepository(engine)


def create_run(
    repository: SQLRepository,
    question: ResearchQuestion,
    mode: Mode,
    settings: Settings,
    *,
    demo: bool = False,
    live: bool = False,
) -> ResearchRun:
    configured = {route.provider for routes in settings.route_groups() for route in routes}
    if demo and live:
        raise ValueError("Choose either --demo or --live")
    if not live and configured - {"fake"}:
        raise ValueError("Configured paid providers require an explicit --live run")
    if not live and settings.search.adapters:
        raise ValueError("Real search adapters require --live")
    if live and (not settings.search.adapters and not settings.search.local_documents):
        raise ValueError("Enable a real search adapter or local documents for a live run")
    if live and configured == {"fake"}:
        raise ValueError("Configure a real model provider before a live run")
    if live:
        key_names = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "google": "GOOGLE_API_KEY",
        }
        for routes in settings.route_groups():
            for route in routes:
                if route.provider == "fake":
                    continue
                if (
                    route.provider not in key_names
                    or route.model == "CONFIGURE_ME"
                    or route.input_cost_per_million is None
                    or route.output_cost_per_million is None
                ):
                    raise ValueError(
                        "Live routes require a supported provider, model ID and configured token prices"
                    )
        if not any(os.environ.get(key_names[name]) for name in configured if name in key_names):
            raise ValueError("No API key is configured for the enabled model providers")
    project = ResearchProject(title=question.topic, question=question)
    run = ResearchDirector.create_research_run(
        project_id=project.project_id,
        question=question,
        mode=mode,
        provenance="fixture" if demo else "live" if live else "offline",
        config_fingerprint=settings.fingerprint(),
        budget_usd=settings.research.budget_usd,
    )
    repository.create_run(project, run)
    repository.checkpoint(run, {"settings": settings})
    return run


class Runtime:
    def __init__(
        self, workspace: Path, repository: SQLRepository, settings: Settings, run: ResearchRun
    ) -> None:
        self.workspace, self.repository, self.settings, self.run = (
            workspace,
            repository,
            settings,
            run,
        )
        self.client = httpx.AsyncClient(
            timeout=settings.timeout_seconds,
            follow_redirects=False,
            limits=httpx.Limits(
                max_connections=settings.concurrency.searches + settings.concurrency.agents
            ),
        )

    async def __aenter__(self) -> ResearchPipeline:
        settings = self.settings
        providers: dict[str, BaseLLMProvider] = {
            "fake": FakeProvider(
                responder=synthetic_response if self.run.provenance == "fixture" else None
            )
        }
        adapters: list[SearchAdapter] = []
        citations: list[CitationAdapter] = []
        metadata: list[MetadataAdapter] = []
        if self.run.provenance == "fixture":
            fixture = SyntheticSearchAdapter()
            adapters.append(fixture)
            citations.append(fixture)
        elif self.run.provenance == "live":
            providers.update(
                openai=OpenAIProvider(self.client),
                anthropic=AnthropicProvider(self.client),
                google=GeminiProvider(self.client),
            )
            for name in settings.search.adapters:
                if name == "arxiv":
                    adapters.append(ArxivAdapter(self.client))
                    continue
                if name == "ieee":
                    adapters.append(IEEEAdapter())
                    continue
                if name == "crossref":
                    adapter: CrossrefAdapter | OpenAlexAdapter = CrossrefAdapter(
                        self.client, settings.search.contact_email
                    )
                elif name == "openalex":
                    adapter = OpenAlexAdapter(self.client, settings.search.contact_email)
                else:
                    raise ValueError(f"Unsupported search adapter: {name}")
                adapters.append(adapter)
                citations.append(adapter)
                metadata.append(adapter)
        router = ModelRouter(settings, providers, self.repository, self.run.run_id)
        trace = JSONLTraceSink(
            workspace_path(self.workspace, f"runs/{self.run.run_id}/trace.jsonl")
        )
        tools = ToolRegistry()
        pipeline = ResearchPipeline(self.repository, settings, router, tools, trace)
        discovery = DiscoveryService(
            adapters,
            citations,
            LocalDocumentAdapter(self.workspace),
            pipeline.concurrency.searches,
            limit=settings.search.results_per_query,
        )
        audit = CitationAuditService(metadata, pipeline.concurrency.searches)
        tools.register("search", SearchInput, discovery.search)
        tools.register("citation_search", SearchInput, discovery.citation_search)
        tools.register("local_read", SearchInput, discovery.local_read)
        tools.register("metadata_verify", AuditInput, audit.audit)
        return pipeline

    async def __aexit__(self, *_: object) -> None:
        await self.client.aclose()


def settings_for_run(repository: SQLRepository, run_id: UUID) -> Settings:
    raw = repository.artifacts(run_id)["settings"]
    settings = Settings.model_validate(raw)
    expected = repository.get_run(run_id).config_fingerprint
    if settings.fingerprint() != expected:
        raw_fingerprint = hashlib.sha256(json.dumps(raw, sort_keys=True).encode()).hexdigest()
        if raw_fingerprint != expected:
            raise ValueError("Pinned run configuration fingerprint is invalid")
        settings.pin_compatible_fingerprint(expected)
    return settings
