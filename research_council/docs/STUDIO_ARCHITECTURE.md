# STUDIO-0: application boundary and API contract

Studio is a local React/TypeScript client of a FastAPI application service. The service uses
the existing SQLRepository, Runtime, ResearchPipeline, WorkflowEngine, gates, router and
MarkdownExporter. Practice changes only provider/source configuration and fixture provenance.
Canonical scientific models, validation and readiness transitions remain authoritative.

## Storage and execution

One local workspace contains council.db and a separate studio.db for project preferences,
named human decisions, discussion history, proposed actions, document jobs and UI revisions.
These application records cannot certify evidence or advance scientific readiness. Scientific
state is read through repository checkpoints. A single local worker per run uses existing run
leases. Pause/cancel requests are cooperative and take effect at durable stage boundaries.
Restarting the server leaves durable checkpoints available for explicit resume.

Discussion uses the selected real agent's typed input/output contracts and tools, records its
execution, and returns a structured advisory artifact without changing the scientific checkpoint.
Actions are persisted proposals: validate typed input, inspect, explicitly approve with a named
reviewer, then execute under a lease. Results remain proposed artifacts until an existing
workflow stage integrates and validates them. No prompt can directly overwrite verified state.

## HTTP contract (prefix /api)

- GET/POST /projects; GET/PATCH /projects/{id}; GET /dashboard
- POST /projects/{id}/runs; POST /projects/{id}/documents
- GET /runs/{id}; POST /runs/{id}/{start,pause,resume,cancel}
- GET /runs/{id}/{agents,papers,evidence,claims,gaps,novelty,reviews,cost,events,export}
- POST /runs/{id}/approve (approve/reject/revise, reviewer, comment)
- POST /agents/{agent}/{discuss,propose-action} (run_id, task, optional typed input)
- POST /proposals/{id}/approve; GET /runs/{id}/interactions
- GET/PUT /settings; POST /projects/{id}/preflight
- POST /runs/{id}/revisions (noncanonical experiment/paper revisions)

Snapshots include typed scientific state and safe execution summaries. SSE events derive from
persisted executions and checkpoint changes, support Last-Event-ID, and never contain raw
provider payloads, credentials or hidden reasoning. Browser updates also refresh snapshots.

## Security and real research

Bind 127.0.0.1; explicit localhost frontend origins/Host checks; reject cross-origin writes.
Bounded PDFs are named by generated IDs, parsed as untrusted source material and stored
inside the workspace. Downloads are generated packages, never arbitrary filesystem paths.
Settings expose credential-presence booleans only. Real start requires validated configured
routes/sources/prices/caps plus the exact confirmation START REAL RESEARCH. Implementation
and tests use FakeProvider and synthetic sources exclusively. No automatic SRL promotion.

## Frontend

Vite React TypeScript; localized English/Vietnamese resources; dark/light CSS tokens.
One workspace has Overview, Workflow, Agents, Papers, Evidence, Claims, Literature Map,
Gaps, Novelty, Hardware, Experiments, Paper, Reviews, Cost and Logs. All scientific views
render API data with provenance, verification and missing-data states. Provider compatibility
is an offline schema capability result; it does not imply that credentials/model access work.

## Milestone verification

Each STUDIO-0 through STUDIO-11 is separately committed after relevant checks pass.
Final verification runs all offline backend tests, lint/type checking, frontend unit/build
checks and a full Playwright fixture workflow, including human gates and generated screenshots.
