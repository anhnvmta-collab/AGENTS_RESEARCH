from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from research_council.studio.models import StudioProject
from research_council.studio.service import StudioService

ORIGINS = {"http://127.0.0.1:5173", "http://localhost:5173", "http://127.0.0.1:8765"}


def create_app(workspace: Path = Path("workspace/studio")) -> FastAPI:
    service = StudioService(workspace)

    @asynccontextmanager
    async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
        yield
        service.repository.engine.dispose()

    app = FastAPI(title="Research Council Studio", lifespan=lifespan)
    app.state.service = service
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"]
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=sorted(ORIGINS),
        allow_methods=["GET", "POST", "PATCH", "PUT"],
        allow_headers=["Content-Type", "Last-Event-ID"],
    )

    @app.middleware("http")
    async def local_origin(request: Request, call_next: Any) -> Any:
        if request.method not in {"GET", "HEAD", "OPTIONS"} and request.headers.get(
            "origin"
        ) not in {*ORIGINS, None}:
            return JSONResponse({"detail": "Untrusted browser origin"}, status_code=403)
        return await call_next(request)

    @app.exception_handler(KeyError)
    async def missing(request: Request, exc: KeyError) -> JSONResponse:
        return JSONResponse({"detail": "Record not found"}, status_code=404)

    @app.exception_handler(ValueError)
    async def invalid(request: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse({"detail": "Invalid operation or typed input"}, status_code=422)

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

    return app
