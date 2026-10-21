# Phase 1 implementation report

Implemented Pydantic domain models, DOI normalization, configuration/fingerprints, SQLAlchemy
tables and packaged Alembic revision, typed repository ports, grounded excerpt checks, claim
reference validation, atomic artifact checkpoints, workspace containment and structured traces.
Formatter, Ruff, mypy and pytest pass (7 tests). Missing quartile remains unknown.

## Independent re-audit, 2026-10-21

Implemented/modified: schemas/models, agents/contracts, repositories/store, storage/database,
projector and graph, Alembic 0002, core/integrity, deterministic gates and regression tests.
Decisions: separate global paper identity from run/revision snapshots; FK-backed graph edges;
round-trip validation and UTC normalization. Actual checks: format/lint/mypy PASS, 77 tests PASS,
including migration up/down and cross-run/revision integrity. Architectural review: agents execute
no SQL, typed provenance is retained and a failed gate cannot be overridden by confidence.
Limits/debt: JSON scientific payloads need application validation in addition to FK edges;
PostgreSQL is not locally exercised. Next dependency: configured provider routing and execution
provenance, while preserving these storage contracts.
