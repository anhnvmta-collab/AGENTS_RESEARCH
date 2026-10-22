from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import FastAPI, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from research_council.core.config import Settings
from research_council.core.human_review import ScientificAttestation
from research_council.studio.models import (
    Decision,
    Interaction,
    Revision,
    StartRequest,
    StudioError,
    StudioProject,
)
from research_council.studio.security import BodyLimitMiddleware
from research_council.studio.service import StudioService

ORIGINS = {"http://127.0.0.1:5173", "http://localhost:5173", "http://127.0.0.1:8765"}


def create_app(
    workspace: Path = Path("workspace/studio"), *, origin: str = "http://127.0.0.1:8765"
) -> FastAPI:
    service = StudioService(workspace)
    origins = ORIGINS | {origin}

    @asynccontextmanager
    async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
        yield
        for identity in service.jobs:
            service.control(identity, "pause")
        if service.jobs:
            import asyncio

            await asyncio.gather(*service.jobs.values(), return_exceptions=True)
        service.repository.engine.dispose()

    app = FastAPI(title="Research Council Studio", lifespan=lifespan)
    app.state.service = service
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])
    app.add_middleware(
        CORSMiddleware,
        allow_origins=sorted(origins),
        allow_methods=["GET", "POST", "PATCH", "PUT"],
        allow_headers=["Content-Type", "Last-Event-ID"],
    )

    @app.middleware("http")
    async def local_origin(request: Request, call_next: Any) -> Any:
        if request.method not in {"GET", "HEAD", "OPTIONS"} and request.headers.get(
            "origin"
        ) not in {*origins, None}:
            return JSONResponse({"detail": "Untrusted browser origin"}, status_code=403)
        if (
            request.method not in {"GET", "HEAD", "OPTIONS"}
            and request.headers.get("sec-fetch-site") == "cross-site"
        ):
            return JSONResponse({"detail": "Cross-site writes are refused"}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'"
        )
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            {"detail": "Request validation failed; check required fields and limits"},
            status_code=422,
        )

    @app.exception_handler(KeyError)
    async def missing(request: Request, exc: KeyError) -> JSONResponse:
        return JSONResponse({"detail": "Record not found"}, status_code=404)

    @app.exception_handler(ValueError)
    async def invalid(request: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(
            {
                "detail": str(exc)
                if isinstance(exc, StudioError)
                else "Invalid operation or typed input"
            },
            status_code=422,
        )

    @app.exception_handler(RuntimeError)
    async def conflict(request: Request, exc: RuntimeError) -> JSONResponse:
        return JSONResponse(
            {"detail": "Operation conflicts with the current run state"}, status_code=409
        )

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "product": "RESEARCH COUNCIL STUDIO"}

    @app.get("/api/dashboard")
    def dashboard() -> dict[str, Any]:
        return service.dashboard()

    @app.get("/api/settings")
    def settings() -> Any:
        from research_council.studio.settings import view

        return view(service)

    @app.put("/api/settings")
    def save_settings(request: Settings) -> Any:
        from research_council.studio.settings import save

        return save(service, request)

    @app.post("/api/projects/{identity}/preflight")
    def preflight(identity: UUID) -> Any:
        from research_council.studio.settings import preflight

        return preflight(service, identity)

    @app.get("/api/runs/{identity}/cost")
    def cost(identity: UUID) -> Any:
        from research_council.studio.settings import cost

        return cost(service, identity)

    @app.get("/api/projects")
    def projects() -> list[dict[str, Any]]:
        return service.store.list("project")

    @app.post("/api/projects", status_code=201)
    def create_project(project: StudioProject) -> dict[str, Any]:
        try:
            service.project(project.id)
        except KeyError:
            return service.save_project(project)
        raise ValueError("Project already exists")

    @app.get("/api/projects/{identity}")
    def project(identity: UUID) -> dict[str, Any]:
        result = service.project(identity).model_dump(mode="json")
        result["runs"] = [
            item for item in service.dashboard()["runs"] if item["project_id"] == str(identity)
        ]
        result["documents"] = [
            item for item in service.store.list("document") if item["project_id"] == str(identity)
        ]
        return result

    @app.patch("/api/projects/{identity}")
    def update_project(identity: UUID, project: StudioProject) -> dict[str, Any]:
        service.project(identity)
        if identity != project.id:
            raise ValueError("Identity is immutable")
        return service.save_project(project)

    @app.get("/api/runs/{identity}")
    def run(identity: UUID) -> dict[str, Any]:
        return service.snapshot(identity)

    @app.post("/api/projects/{identity}/documents")
    async def documents(identity: UUID, files: list[UploadFile]) -> list[dict[str, Any]]:
        from research_council.studio.documents import upload

        return await upload(service, identity, files)

    @app.get("/api/runs/{identity}/papers")
    @app.get("/api/runs/{identity}/evidence")
    @app.get("/api/runs/{identity}/claims")
    @app.get("/api/runs/{identity}/gaps")
    @app.get("/api/runs/{identity}/novelty")
    @app.get("/api/runs/{identity}/reviews")
    def collection(identity: UUID, request: Request) -> Any:
        collection = request.url.path.rsplit("/", 1)[-1]
        fields = {
            "papers": "candidates",
            "evidence": "evidence",
            "claims": "claims",
            "gaps": "gaps",
            "novelty": "novelty_candidates",
            "reviews": "reviews",
        }
        if collection not in fields:
            raise KeyError("Unknown collection")
        return service.snapshot(identity)["state"][fields[collection]]

    @app.post("/api/projects/{identity}/runs", status_code=201)
    def new_run(identity: UUID, request: StartRequest) -> dict[str, Any]:
        return service.new_run(identity, request.confirmation)

    @app.post("/api/runs/{identity}/start")
    @app.post("/api/runs/{identity}/resume")
    async def start(identity: UUID) -> dict[str, Any]:
        return await service.start(identity)

    @app.post("/api/runs/{identity}/pause")
    def pause(identity: UUID) -> dict[str, Any]:
        return service.control(identity, "pause")

    @app.post("/api/runs/{identity}/cancel")
    async def cancel(identity: UUID) -> dict[str, Any]:
        result = service.control(identity, "cancel")
        if identity not in service.jobs or service.jobs[identity].done():
            run = service.repository.get_run(identity)
            if run.status not in {"COMPLETED", "REJECTED", "BUDGET_EXHAUSTED"}:
                from research_council.core.orchestration.engine import WorkflowEngine
                from research_council.core.runtime import settings_for_run

                await WorkflowEngine(
                    service.repository,
                    settings_for_run(service.repository, identity),
                    [],
                    control=lambda: "cancel",
                ).resume(identity)
        return result

    @app.post("/api/runs/{identity}/approve")
    def decide(identity: UUID, decision: Decision) -> dict[str, Any]:
        return service.decide(identity, decision)

    @app.get("/api/runs/{identity}/agents")
    def agents(identity: UUID) -> list[dict[str, Any]]:
        return service.agents(identity)

    @app.get("/api/runs/{identity}/agents/{agent}/artifacts")
    def agent_artifacts(identity: UUID, agent: str) -> Any:
        from research_council.schemas.models import AgentExecution
        from research_council.studio.interactions import agent_class

        agent_class(agent)
        artifacts = service.repository.artifacts(identity)
        return [
            {
                "execution_id": row.execution_id,
                "output": artifacts.get(f"agent_output_{row.execution_id}"),
            }
            for row in service.repository.list_all("agent_executions", AgentExecution, identity)
            if row.agent_id == agent
        ]

    @app.get("/api/runs/{identity}/decisions")
    def decisions(identity: UUID) -> Any:
        service.repository.get_run(identity)
        return [row for row in service.store.list("decision") if row["run_id"] == str(identity)]

    @app.post("/api/runs/{identity}/attest")
    def attest(identity: UUID, request: ScientificAttestation) -> Any:
        from uuid import uuid4

        from research_council.core.human_review import attest_claim
        from research_council.schemas.models import utcnow

        attest_claim(service.repository, identity, request)
        service.store.put(
            "decision",
            str(uuid4()),
            {
                **request.model_dump(mode="json"),
                "kind": "SCIENTIFIC_ATTESTATION",
                "run_id": str(identity),
                "at": utcnow().isoformat(),
            },
        )
        return service.snapshot(identity)

    @app.get("/api/runs/{identity}/paper")
    def paper(identity: UUID) -> Any:
        from research_council.studio.artifacts import paper_sections

        return paper_sections(service, identity)

    @app.post("/api/runs/{identity}/paper/draft")
    def draft(identity: UUID, request: Decision) -> Any:
        from research_council.studio.artifacts import paper_sections, revision

        if request.action != "approve":
            raise ValueError("Draft requires a named request")
        for section in paper_sections(service, identity, include_revisions=False):
            if request.comment and request.comment != section["section"]:
                continue
            revision(
                service,
                identity,
                Revision(
                    kind="paper",
                    target=section["section"],
                    content=section["content"],
                    reviewer=request.reviewer,
                ),
            )
        return paper_sections(service, identity)

    @app.get("/api/runs/{identity}/revisions")
    def revisions(identity: UUID) -> Any:
        service.repository.get_run(identity)
        return [row for row in service.store.list("revision") if row["run_id"] == str(identity)]

    @app.post("/api/runs/{identity}/revisions")
    def revision(identity: UUID, request: Revision) -> Any:
        from research_council.studio.artifacts import revision

        return revision(service, identity, request)

    @app.get("/api/runs/{identity}/export")
    def export(identity: UUID) -> Any:
        from fastapi.responses import Response

        from research_council.studio.artifacts import export_zip

        return Response(
            export_zip(service, identity),
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="research-{identity}.zip"'},
        )

    @app.post("/api/agents/{agent}/discuss")
    async def discuss(agent: str, request: Interaction) -> dict[str, Any]:
        from research_council.studio.interactions import discuss

        return await discuss(service, agent, request)

    @app.post("/api/agents/{agent}/propose-action")
    def propose(agent: str, request: Interaction) -> dict[str, Any]:
        from research_council.studio.interactions import propose

        return propose(service, agent, request)

    @app.post("/api/proposals/{identity}/approve")
    async def approve_proposal(identity: UUID, decision: Decision) -> dict[str, Any]:
        from research_council.studio.interactions import approve_proposal

        return await approve_proposal(service, identity, decision)

    @app.get("/api/runs/{identity}/interactions")
    def interactions(identity: UUID) -> list[dict[str, Any]]:
        service.repository.get_run(identity)
        return [row for row in service.store.list("interaction") if row["run_id"] == str(identity)]

    @app.get("/api/runs/{identity}/events")
    async def event_stream(identity: UUID, request: Request, once: bool = False) -> Any:
        import asyncio

        from fastapi.responses import StreamingResponse

        from research_council.studio.events import encode_event, events

        service.repository.get_run(identity)
        raw_last = request.headers.get("last-event-id", "0")
        if not raw_last.isdigit() or len(raw_last) > 15:
            raise ValueError("Invalid event cursor")

        async def generate():  # type: ignore[no-untyped-def]
            last = int(raw_last)
            while not await request.is_disconnected():
                for event in events(service, identity):
                    if event["id"] > last:
                        yield encode_event(event)
                        last = event["id"]
                if once:
                    break
                yield ": heartbeat\n\n"
                await asyncio.sleep(0.5)

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    import mimetypes

    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles

    # Windows registry associations may otherwise label JavaScript as text/plain.
    mimetypes.add_type("text/javascript", ".js")
    mimetypes.add_type("text/javascript", ".mjs")

    frontend = Path(__file__).parent / "static"
    if not (frontend / "index.html").is_file():
        frontend = Path(__file__).parents[3] / "studio/frontend/dist"
    if (frontend / "index.html").is_file():
        app.mount("/assets", StaticFiles(directory=frontend / "assets"), name="assets")

        @app.get("/", include_in_schema=False)
        def index() -> Any:
            return FileResponse(frontend / "index.html")

    app.add_middleware(BodyLimitMiddleware)
    return app
