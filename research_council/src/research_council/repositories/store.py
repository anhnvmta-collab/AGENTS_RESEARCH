from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any, Protocol, TypeVar
from uuid import UUID

from sqlalchemy import delete, insert, select, update
from sqlalchemy.engine import Connection, Engine

from research_council.schemas.models import (
    Evidence,
    Paper,
    ResearchClaim,
    ResearchProject,
    ResearchRun,
    Schema,
    VerificationStatus,
)
from research_council.storage.database import tables

T = TypeVar("T", bound=Schema)


def normalized_title(title: str) -> str:
    return re.sub(r"[^\w]+", " ", title.casefold()).strip()


class PaperRepository(Protocol):
    def get_paper(self, paper_id: UUID) -> Paper | None: ...
    def save_paper(self, paper: Paper) -> None: ...


class EvidenceRepository(Protocol):
    def save_evidence(self, evidence: Evidence, run_id: UUID) -> None: ...
    def get_evidence(self, evidence_id: UUID) -> Evidence | None: ...


class ClaimRepository(Protocol):
    def save_claim(self, claim: ResearchClaim, run_id: UUID) -> None: ...


class ResearchRepository(Protocol):
    def get_run(self, run_id: UUID) -> ResearchRun: ...
    def create_run(self, project: ResearchProject, run: ResearchRun) -> None: ...


class SQLRepository:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def _put(
        self,
        connection: Connection,
        table_name: str,
        identity: str,
        payload: dict[str, Any],
        **fields: Any,
    ) -> None:
        table = tables[table_name]
        exists = connection.execute(select(table.c.id).where(table.c.id == identity)).first()
        if exists:
            connection.execute(
                update(table).where(table.c.id == identity).values(payload=payload, **fields)
            )
        else:
            connection.execute(insert(table).values(id=identity, payload=payload, **fields))

    def save(
        self,
        table_name: str,
        identity: UUID,
        obj: Schema,
        run_id: UUID | None = None,
        **fields: Any,
    ) -> None:
        if "run_id" in tables[table_name].c:
            fields["run_id"] = str(run_id) if run_id else None
        with self.engine.begin() as connection:
            self._put(connection, table_name, str(identity), obj.model_dump(mode="json"), **fields)

    def get(self, table_name: str, identity: UUID, schema: type[T]) -> T | None:
        table = tables[table_name]
        with self.engine.connect() as connection:
            payload: Any = connection.execute(
                select(table.c.payload).where(table.c.id == str(identity))
            ).scalar_one_or_none()
        return schema.model_validate(payload) if payload is not None else None

    def list_all(self, table_name: str, schema: type[T], run_id: UUID | None = None) -> list[T]:
        table = tables[table_name]
        query = select(table.c.payload)
        if run_id is not None:
            query = query.where(table.c.run_id == str(run_id))
        with self.engine.connect() as connection:
            payloads: Any = connection.execute(query).scalars().all()
            return [schema.model_validate(payload) for payload in payloads]

    def create_run(self, project: ResearchProject, run: ResearchRun) -> None:
        with self.engine.begin() as connection:
            self._put(
                connection, "projects", str(project.project_id), project.model_dump(mode="json")
            )
            self._put(
                connection,
                "research_runs",
                str(run.run_id),
                run.model_dump(mode="json"),
                project_id=str(project.project_id),
            )

    def get_run(self, run_id: UUID) -> ResearchRun:
        result = self.get("research_runs", run_id, ResearchRun)
        if result is None:
            raise KeyError("Unknown research run")
        return result

    def save_run(self, run: ResearchRun) -> None:
        self.save("research_runs", run.run_id, run, project_id=str(run.project_id))

    def save_paper(self, paper: Paper) -> None:
        with self.engine.begin() as connection:
            self._put(
                connection,
                "papers",
                str(paper.paper_id),
                paper.model_dump(mode="json"),
                doi=paper.metadata.doi,
                normalized_title=normalized_title(paper.metadata.title),
            )
            self._put(
                connection,
                "paper_metadata",
                str(paper.paper_id),
                paper.metadata.model_dump(mode="json"),
                paper_id=str(paper.paper_id),
            )

    def get_paper(self, paper_id: UUID) -> Paper | None:
        return self.get("papers", paper_id, Paper)

    def save_evidence(self, evidence: Evidence, run_id: UUID) -> None:
        paper = self.get_paper(evidence.paper_id)
        if paper is None:
            raise ValueError("Evidence references an unknown paper")
        source = (
            paper.page_texts.get(evidence.page, "") if evidence.page else paper.source_text or ""
        )
        if " ".join(evidence.verbatim_excerpt.split()) not in " ".join(source.split()):
            raise ValueError("Evidence excerpt was not found in its source location")
        self.save(
            "evidence", evidence.evidence_id, evidence, run_id, paper_id=str(evidence.paper_id)
        )

    def get_evidence(self, evidence_id: UUID) -> Evidence | None:
        return self.get("evidence", evidence_id, Evidence)

    def save_claim(self, claim: ResearchClaim, run_id: UUID) -> None:
        supports = [self.get_evidence(identity) for identity in claim.evidence_ids]
        contradictions = [
            self.get_evidence(identity) for identity in claim.contradicting_evidence_ids
        ]
        if any(item is None for item in supports + contradictions):
            raise ValueError("Claim references unknown evidence")
        for evidence in supports:
            if evidence and evidence.paper_id not in claim.source_paper_ids:
                raise ValueError("Claim/evidence paper mismatch")
        if any(self.get_paper(identity) is None for identity in claim.source_paper_ids):
            raise ValueError("Claim references an unknown paper")
        if claim.verification_status == VerificationStatus.VERIFIED and any(
            item and item.verification_status != VerificationStatus.VERIFIED for item in supports
        ):
            raise ValueError("Verified claim requires verified supporting evidence")
        self.save("claims", claim.claim_id, claim, run_id)

    def checkpoint(
        self, run: ResearchRun, artifacts: dict[str, Schema | list[Schema] | dict[str, Any]]
    ) -> None:
        with self.engine.begin() as connection:
            for name, value in artifacts.items():
                if isinstance(value, Schema):
                    payload: Any = value.model_dump(mode="json")
                elif isinstance(value, list):
                    payload = [item.model_dump(mode="json") for item in value]
                else:
                    payload = value
                self._put(
                    connection,
                    "artifacts",
                    f"{run.run_id}:{name}",
                    payload,
                    run_id=str(run.run_id),
                    name=name,
                )
            self._put(
                connection,
                "research_runs",
                str(run.run_id),
                run.model_dump(mode="json"),
                project_id=str(run.project_id),
            )

    def artifacts(self, run_id: UUID) -> dict[str, Any]:
        table = tables["artifacts"]
        with self.engine.connect() as connection:
            return {
                row.name: row.payload
                for row in connection.execute(select(table).where(table.c.run_id == str(run_id)))
            }

    def delete_artifacts(self, run_id: UUID, names: Iterable[str]) -> None:
        table = tables["artifacts"]
        with self.engine.begin() as connection:
            connection.execute(
                delete(table).where(table.c.run_id == str(run_id), table.c.name.in_(list(names)))
            )
