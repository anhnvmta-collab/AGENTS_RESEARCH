# Architecture

Research Council is a scientific evidence pipeline. It does not claim that a model's
agreement establishes truth. The unit of work is a typed artifact, never a shared transcript.

## Boundaries

* Domain: Pydantic schemas, claim validation, novelty decisions, deterministic gates.
* Application: asyncio workflow, stage checkpoints, budgets, approvals and role context builders.
* Ports: repositories, LLM providers, search/citation adapters, vector store, exporters, tracing.
* Infrastructure: SQLAlchemy 2, Alembic, HTTPX, local document parser, JSONL tracing, Typer/Rich.

Dependencies point inward. Agents never execute SQL or import vendor SDKs. No graph framework
is required: a versioned stage machine implements a replaceable workflow port.

## Memory and provenance

Run memory is a versioned checkpoint; project memory holds scoped gaps, decisions and experiments;
the global library holds deduplicated papers and reusable evidence. Evidence is immutable in
meaning: verification changes require an audit. Every primary conclusion resolves claim IDs
to evidence IDs, papers, DOI/URL, and source locations. Hypotheses remain hypotheses.

## Persistence and concurrency

SQLite is the local default, with foreign keys, WAL and short transactions. JSON payloads
retain typed artifacts, relational keys retain identity and scope. SQLAlchemy database URLs
allow PostgreSQL without changing domain code. Migration revisions own schema creation.
Async semaphores independently bound agents, searches and paper reads. No database session
is shared across asynchronous work. Stage artifact writes and checkpoint advancement are atomic.

## Risks

| Risk | Control | Residual limit |
|---|---|---|
| Fabricated or misattributed evidence | Validate IDs, exact short excerpts against retrieved source, deterministic audit | Semantic entailment still needs human review |
| Reviewer anchoring | Separate input schema containing only normalized claim, keywords and necessary evidence | Same model family may share biases |
| Incomplete prior art | Log queries, failures, dates, bounded targeted-search loop | Search cannot prove universal absence |
| Metadata confused with full text | Source kind and verification scope; partial status | Paywalls and missing full text limit conclusions |
| Provider changes | HTTP adapters, mocked protocol tests, configurable model IDs | Paid live API compatibility needs deployment smoke tests |
| Checkpoint drift | Schema/config fingerprint and explicit resume validation | V1 cannot migrate old workflow checkpoints |
| Costs and rate limits | Per-call caps, run budget, usage persistence, bounded retries and jitter | Provider billing remains authoritative |
| Malicious documents | Workspace containment, size limits, untrusted data envelope, tool allowlists | Prompt injection cannot be solved by prompts alone |

## Repository layout

```text
research_council/
  pyproject.toml, README.md, .env.example, alembic.ini
  config/default.yaml
  docs/{architecture,workflow,data-model,agent-contracts,provider-routing,quality-gates,security}.md
  docs/ADR/{0001-orchestration,0002-evidence-first,0003-provider-abstraction}.md
  docs/phases/
  prompts/*.md
  src/research_council/
    cli/  schemas/  agents/  providers/  repositories/  storage/
    core/{orchestration,routing,gates,context,tracing,security}/
    tools/  knowledge/  evaluation/  exporters/
  src/research_council/storage/migrations/versions/
  tests/
  examples/fhss.yaml
  scripts/{check,acceptance}.py
```

See [implementation-plan.md](implementation-plan.md) for dependencies and phase checks.

## Implemented audit refinements
Source adapters implement search/metadata/citation/full-text ports. arXiv serializes requests with
bounded XML parsing; IEEE is an optional authenticated-backend boundary. Located lexical retrieval
ranks source chunks before DeepReader; quotations retain paper/chunk/hash/location provenance.
Run/revision graph snapshots and composite foreign keys supplement JSON artifacts. Lease ownership
is fenced during checkpoint writes, with persisted stage events and configuration fingerprints.
Role exports load lazily to avoid contract/core import cycles; fresh-process import tests cover the
public entry points. Outputs reside at workspace/outputs/RUN_ID; JSONL traces remain under runs.
See ADRs 0004-0007 and FINAL_IMPLEMENTATION_AUDIT.md for verified scope and remaining limits.
