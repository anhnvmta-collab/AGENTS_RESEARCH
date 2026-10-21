from __future__ import annotations

import re
from collections.abc import Iterable
from contextvars import ContextVar
from typing import Any, Protocol, TypeVar
from uuid import UUID

from sqlalchemy import delete, insert, or_, select, update
from sqlalchemy.engine import Connection, Engine

from research_council.schemas.models import (
    AgentExecution,
    Evidence,
    Gap,
    ModelExecution,
    NoveltyCandidate,
    Paper,
    ResearchClaim,
    ResearchProject,
    ResearchRun,
    Schema,
    VerificationStatus,
    utcnow,
)
from research_council.storage.database import runs, tables
from research_council.storage.graph import record_id

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


class RunRepository(ResearchRepository, Protocol):
    def save_run(self, run: ResearchRun) -> None: ...


class GapRepository(Protocol):
    def save_gap(self, gap: Gap, run_id: UUID) -> None: ...
    def get_gap(self, gap_id: UUID, run_id: UUID) -> Gap | None: ...


class NoveltyRepository(Protocol):
    def save_candidate(self, candidate: NoveltyCandidate, run_id: UUID) -> None: ...
    def get_candidate(
        self, candidate_id: UUID, run_id: UUID, revision: int | None = None
    ) -> NoveltyCandidate | None: ...


class ExecutionRepository(Protocol):
    def save_execution(self, execution: AgentExecution) -> None: ...
    def list_model_executions(self, run_id: UUID) -> list[ModelExecution]: ...


DOMAIN_TABLES = {
    "evidence",
    "claims",
    "gaps",
    "novelty_candidates",
    "prior_art_matches",
    "reviews",
    "citation_audits",
    "search_queries",
    "quality_gate_results",
}


class SQLRepository:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine
        self._leases: ContextVar[dict[str, str] | None] = ContextVar(
            "research_run_leases", default=None
        )

    def _assert_lease(self, connection: Connection, run_id: UUID) -> None:
        row = connection.execute(
            select(runs.c.lease_owner, runs.c.lease_until).where(runs.c.id == str(run_id))
        ).first()
        owner = (self._leases.get() or {}).get(str(run_id))
        if row is None:
            raise KeyError("Unknown research run")
        now = utcnow().isoformat()
        if owner and (row.lease_owner != owner or not row.lease_until or row.lease_until <= now):
            raise RuntimeError("Stale run lease; checkpoint write refused")
        if not owner and row.lease_owner and row.lease_until and row.lease_until > now:
            raise RuntimeError("Run has an active lease owned by another operation")

    def acquire_lease(self, run_id: UUID, owner: str, until: str) -> None:
        with self.engine.begin() as connection:
            result = connection.execute(
                update(runs)
                .where(
                    runs.c.id == str(run_id),
                    or_(runs.c.lease_owner.is_(None), runs.c.lease_until < utcnow().isoformat()),
                )
                .values(lease_owner=owner, lease_until=until)
            )
            if result.rowcount != 1:
                raise RuntimeError("Research run is already owned by another worker")
        self._leases.set({**(self._leases.get() or {}), str(run_id): owner})

    def renew_lease(self, run_id: UUID, owner: str, until: str) -> None:
        with self.engine.begin() as connection:
            result = connection.execute(
                update(runs)
                .where(runs.c.id == str(run_id), runs.c.lease_owner == owner)
                .values(lease_until=until)
            )
            if result.rowcount != 1:
                raise RuntimeError("Research run lease was lost")

    def release_lease(self, run_id: UUID, owner: str) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                update(runs)
                .where(runs.c.id == str(run_id), runs.c.lease_owner == owner)
                .values(lease_owner=None, lease_until=None)
            )
        self._leases.set(
            {key: value for key, value in (self._leases.get() or {}).items() if key != str(run_id)}
        )

    def scientific_records(
        self,
        kind: str,
        schema: type[T],
        run_id: UUID | None = None,
        identity: UUID | None = None,
        revision: int | None = None,
    ) -> list[T]:
        table = tables["scientific_artifacts"]
        query = select(table.c.payload).where(table.c.artifact_type == kind)
        if run_id:
            query = query.where(table.c.run_id == str(run_id))
        if identity:
            query = query.where(table.c.artifact_id == str(identity))
        if revision is not None:
            query = query.where(table.c.revision == revision)
        with self.engine.connect() as connection:
            payloads: Any = (
                connection.execute(query.order_by(table.c.revision.desc())).scalars().all()
            )
        return [schema.model_validate(payload) for payload in payloads]

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
        obj = obj.__class__.model_validate_json(obj.model_dump_json())
        if "run_id" in tables[table_name].c:
            fields["run_id"] = str(run_id) if run_id else None
        with self.engine.begin() as connection:
            if table_name == "research_runs":
                self._assert_lease(connection, identity)
            if table_name == "artifacts" and run_id:
                self._assert_lease(connection, run_id)
            row_identity = (
                record_id(run_id, table_name, identity, getattr(obj, "revision", 1))
                if run_id and table_name in DOMAIN_TABLES
                else identity
            )
            self._put(
                connection, table_name, str(row_identity), obj.model_dump(mode="json"), **fields
            )
            if run_id and table_name in DOMAIN_TABLES:
                self._put(
                    connection,
                    "scientific_artifacts",
                    str(row_identity),
                    obj.model_dump(mode="json"),
                    run_id=str(run_id),
                    artifact_type=table_name,
                    artifact_id=str(identity),
                    revision=getattr(obj, "revision", 1),
                )

    def get(self, table_name: str, identity: UUID, schema: type[T]) -> T | None:
        if table_name in DOMAIN_TABLES:
            snapshots = self.scientific_records(table_name, schema, identity=identity)
            if snapshots:
                return snapshots[0]
        table = tables[table_name]
        with self.engine.connect() as connection:
            payload: Any = connection.execute(
                select(table.c.payload).where(table.c.id == str(identity))
            ).scalar_one_or_none()
        return schema.model_validate(payload) if payload is not None else None

    def list_all(self, table_name: str, schema: type[T], run_id: UUID | None = None) -> list[T]:
        if run_id and table_name in DOMAIN_TABLES:
            snapshots = self.scientific_records(table_name, schema, run_id)
            if snapshots:
                return snapshots
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
        evidence.provenance = paper.provenance
        if (
            paper.provenance == "fixture"
            and evidence.verification_status == VerificationStatus.VERIFIED
        ):
            raise ValueError("Fixture evidence cannot be scientifically verified")
        source = (
            paper.page_texts.get(evidence.page, "") if evidence.page else paper.source_text or ""
        )
        if " ".join(evidence.verbatim_excerpt.split()) not in " ".join(source.split()):
            raise ValueError("Evidence excerpt was not found in its source location")
        self.save(
            "evidence", evidence.evidence_id, evidence, run_id, paper_id=str(evidence.paper_id)
        )

    def get_evidence(self, evidence_id: UUID, run_id: UUID | None = None) -> Evidence | None:
        if run_id:
            snapshots = self.scientific_records("evidence", Evidence, run_id, evidence_id)
            return snapshots[0] if snapshots else None
        return self.get("evidence", evidence_id, Evidence)

    def save_claim(self, claim: ResearchClaim, run_id: UUID) -> None:
        from research_council.core.integrity import unresolved_conflict
        from research_council.schemas.models import EvidenceConflict

        claim = ResearchClaim.model_validate_json(claim.model_dump_json())
        supports = [self.get_evidence(identity, run_id) for identity in claim.evidence_ids]
        contradictions = [
            self.get_evidence(identity, run_id) for identity in claim.contradicting_evidence_ids
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
        if claim.verification_status == VerificationStatus.VERIFIED and unresolved_conflict(
            claim, self.scientific_records("conflicts", EvidenceConflict, run_id)
        ):
            raise ValueError("Verified claim has unresolved evidence conflicts")
        self.save("claims", claim.claim_id, claim, run_id)

    def save_gap(self, gap: Gap, run_id: UUID) -> None:
        if any(self.get_evidence(identity, run_id) is None for identity in gap.evidence_ids):
            raise ValueError("Gap references unknown run evidence")
        if any(
            not self.scientific_records("claims", ResearchClaim, run_id, identity)
            for identity in gap.claim_ids
        ):
            raise ValueError("Gap references unknown run claims")
        self.save("gaps", gap.gap_id, gap, run_id)

    def get_gap(self, gap_id: UUID, run_id: UUID) -> Gap | None:
        values = self.scientific_records("gaps", Gap, run_id, gap_id)
        return values[0] if values else None

    def save_candidate(self, candidate: NoveltyCandidate, run_id: UUID) -> None:
        if any(self.get_gap(identity, run_id) is None for identity in candidate.gap_ids) or any(
            self.get_evidence(identity, run_id) is None for identity in candidate.evidence_ids
        ):
            raise ValueError("Novelty candidate references unknown run artifacts")
        self.save("novelty_candidates", candidate.candidate_id, candidate, run_id)

    def get_candidate(
        self, candidate_id: UUID, run_id: UUID, revision: int | None = None
    ) -> NoveltyCandidate | None:
        values = self.scientific_records(
            "novelty_candidates", NoveltyCandidate, run_id, candidate_id, revision
        )
        return values[0] if values else None

    def save_execution(self, execution: AgentExecution) -> None:
        self.save(
            "model_executions" if isinstance(execution, ModelExecution) else "agent_executions",
            execution.execution_id,
            execution,
            execution.run_id,
        )

    def list_model_executions(self, run_id: UUID) -> list[ModelExecution]:
        return self.list_all("model_executions", ModelExecution, run_id)

    def checkpoint(
        self, run: ResearchRun, artifacts: dict[str, Schema | list[Schema] | dict[str, Any]]
    ) -> None:
        with self.engine.begin() as connection:
            self._assert_lease(connection, run.run_id)
            for name, value in artifacts.items():
                if name == "state":
                    from research_council.core.orchestration.state import WorkflowState
                    from research_council.storage.projector import project_state

                    value = (
                        value
                        if isinstance(value, WorkflowState)
                        else WorkflowState.model_validate(value)
                    )
                    project_state(self, connection, run, value)
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
