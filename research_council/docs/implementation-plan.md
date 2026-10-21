# Implementation plan and dependencies

Runtime dependency list (the exact accepted ranges are in pyproject.toml): Python >=3.11;
Pydantic >=2.10,<3; SQLAlchemy >=2.0.36,<3; Alembic >=1.14,<2; Typer >=0.15,<1;
Rich >=13.9,<15; HTTPX >=0.28,<1; PyYAML >=6.0.2,<7; python-dotenv >=1.0.1,<2;
pypdf >=5,<7. Optional PostgreSQL: psycopg[binary] >=3.2,<4.
Development: pytest >=8.3,<10; pytest-asyncio >=0.25,<2; Ruff >=0.9,<1;
mypy >=1.14,<2; types-PyYAML >=6,<7. A resolved requirements lock records tested versions.

| Phase | Deliverable | Exit verification |
|---|---|---|
| 0 | Documents, ADRs, package skeleton, tooling | install, package import |
| 1 | Models, migrations, repository ports/adapters, config, logs | schema/DOI/persistence/security tests |
| 2 | Provider port, fake and three HTTP adapters, router | retries/fallback/metrics/wire-format tests |
| 3 | Agent contract, role modules, prompts, context and permissions | schema/role-isolation/allowlist tests |
| 4 | Workflow state machine, semaphores, checkpoints, approvals | parallelism/resume/lease/failure tests |
| 5 | Search, citation/local document adapters, dedup and triage | mock HTTP, normalization, branch failure |
| 6 | Grounded reading, evidence/claim store, citation audit | excerpt location/citation/contradiction tests |
| 7 | Gaps, novelty, independent attack and gates | bounded loops and unsupported survival rejection |
| 8 | Hardware assessment, experiments, IEEE roadmap | missing-resource conservative assessment |
| 9 | CLI, manifests, all exports, tracing | CLI offline run/status/resume/export/approval |
| 10 | Evaluation, fixtures, integration and end-to-end tests | complete offline suite, wheel smoke test |

Every phase runs format, lint, mypy and pytest before the next phase. Reports live in docs/phases.
No paid API test is required. No research results for the FHSS example are created from imagination.
