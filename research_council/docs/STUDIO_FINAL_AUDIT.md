# Research Council Studio — final implementation audit

Verified 2026-10-22. Branch: `research-council-studio`, based on
`6c089bec1eef68c3aaaee25a86d44d933f0393cd` from `phase-11-live-validation`.

| Required result | Verified value |
| --- | --- |
| PAID_MODEL_CALLS_MADE | **0** |
| LIVE_RESEARCH_EXECUTED | **false** |
| PRACTICE_RUN_EXECUTED | **true — COMPLETED, all 20 real agent classes** |
| ANTHROPIC_COMPATIBILITY | **READY_WITH_SCHEMA_TRANSFORM for 16 contracts; 4 explicitly BLOCKED with route fallback** |
| BACKEND_TESTS | **206 passed; 2 live tests deselected** |
| FRONTEND_TESTS | **3 unit tests passed; ESLint, TypeScript and production build passed** |
| E2E_TESTS | **2 Playwright tests passed against the Python-served production build** |

## Architecture and retained scientific controls

React/TypeScript/Vite → loopback FastAPI → Studio application services → existing SQLRepository,
Runtime, ResearchPipeline, WorkflowEngine, agents, ModelRouter, sources and MarkdownExporter.
Studio metadata has its own durable SQLite store; canonical research data stays in council.db.
Existing migrations remain authoritative. Studio's application store creates its separate
records table on startup; no canonical database migration was necessary.

All Phase 0–11 reports and `docs/FINAL_IMPLEMENTATION_AUDIT.md` remain in the branch.
Evidence/claim integrity, conflict resolution, source gates, adversarial novelty loop,
reviewer-independence policy, scientific attestation and SRL implementation are retained.
Engine changes add an optional cooperative control callback at durable boundaries. Runtime
accepts an existing project and an optional fixture pacing delay; default CLI behavior remains
unchanged. Agent observations contain contract/count/tool/paper metadata and typed outputs,
never provider thinking blocks or hidden reasoning. Model-call budgets include interactions.

## Implemented pages and actions

Dashboard/project library/recent runs; three-step project wizard; first-run Practice entry;
Overview; interactive 20-role Workflow; Agents with contracts, real executions, current
routing, retries, latency, tokens, cost, safe summaries, actual tools and generated artifacts;
Paper Library and bounded multi-PDF upload; Evidence Explorer/source context; backwards
Paper → Evidence → Claim → Gap → Novelty links; observed Literature Map/category filtering;
Gap Board/approved investigation proposals; Novelty Lab/revision changes; four-column Novelty
Battle; Hardware Lab/provenance; revisioned experiment editor; 14-section IEEE paper roadmap;
named human Reviews/scientific attestation; cost/reservation/call monitor; operational Logs;
Providers & Models/eight routing profiles/NoveltyJudge fallback selection; preflight; ZIP export.

Start/Pause/Resume/Cancel use durable checkpoints and run leases. Cancellation becomes terminal
REJECTED; no process is killed. Approved canonical actions explicitly restart planning with
the researcher's instruction and invalidate downstream state. Discussions remain advisory.
Stale proposals are refused. Experiment/paper edits retain named revision history separately
from canonical source verification. English/Vietnamese resources and light/dark themes work.

All 20 agents executed in the browser Practice run:
ResearchDirector, ResearchPlanner, PerspectiveGenerator, QueryPlanner, PaperScout,
CitationScout, LocalDocumentScout, PaperTriage, DeepReader, MathDSPAnalyst, HardwareArchitect,
GapMiner, NoveltyGenerator, PriorArtHunter, ReviewerTwo, NoveltyJudge, ExperimentDesigner,
PaperArchitect, CitationAuditor and FinalSynthesizer. All 13 requested practical agents also
pass typed interactive execution tests without changing their canonical scientific checkpoint.

## API contract

The exact 34-path OpenAPI contract is committed as [studio-openapi.json](audits/studio-openapi.json).
Main groups under `/api`:

- health/dashboard; project list/create/get/update and project runs/preflight/documents;
- run snapshot/start/pause/resume/cancel/approve;
- agents and per-agent generated artifacts; papers/evidence/claims/gaps/novelty/reviews;
- cost, replayable SSE events, ZIP export, decisions and scientific attestation;
- agent discussion/action proposals, explicit proposal approval and interaction history;
- paper sections/draft generation, named revisions and provider settings read/update.

The UI never queries SQL. SSE covers all requested agent, artifact, review, gate, budget and
workflow events. Last-Event-ID replays the durable application journal. Polling also refreshes
snapshots. Source records and schema validation errors are rendered safely as text.

## Security

Default bind is 127.0.0.1. Restricted Host/CORS/Origin checks and cross-site write rejection;
bounded JSON/multipart bodies; redacted validation errors; CSP/nosniff/no-referrer headers;
generated document IDs; filename sanitization; PDF signature/type/size checks; maximum ten
20 MB documents; extraction bounds; encrypted/image-only parsing failures visible. Files stay
inside the workspace. Exports use generated archive entries, with no arbitrary path endpoint.
Windows JavaScript MIME registry associations are overridden for correct production launch.

Provider credentials are read only by backend providers/environment-presence checks. Settings
accept model/configuration fields, never API keys. FakeProvider/source fixtures are isolated
by run provenance. PDF text stays inside the existing untrusted-document context boundary.
Real run creation requires configuration/schema preflight and exact START REAL RESEARCH
confirmation. No real run was started during implementation or testing.

## Practice evidence

See [machine-readable Practice result](audits/studio-practice-result.json): completed run,
2 synthetic papers, 2 evidence records, 5 claims, 1 gap, 3 novelty revisions, 3 skeptical reviews,
31 FakeProvider model calls, all 20 agent classes, seven named approval points, zero paid
calls, zero external browser requests and zero browser runtime errors. Source-matched fixture
excerpts remain PARTIALLY_VERIFIED, with no synthetic scientific verification or SRL promotion.

**Scientific limit preserved:** the canonical NOVELTY pipeline blocks experiment adoption
without Gate 2. Practice therefore creates separate ADVISORY_SYNTHETIC experiment and paper
learning artifacts through the real ExperimentDesigner/PaperArchitect after the approved
novelty stage. The accepted canonical experiment list remains empty; four gate failures and
SRL-0 remain visible. This is a software/workflow demonstration, not a scientific benchmark.

The browser also exercised paper/evidence inspection, ReviewerTwo's same-provider limitation,
cooperative pause/resume, all seven approvals, final export, Vietnamese project creation,
light theme, cancellation and checkpoint persistence after reload. A separate backend test
uploads an actual PDF and verifies its arrival through LocalDocumentScout into run papers.

## Provider compatibility

[Detailed report and official references](STUDIO_PROVIDER_COMPATIBILITY.md), plus
[all 20 offline contract results](audits/studio-provider-contracts.json).
OpenAI/Google transport status is READY; authentication/model access/grammar acceptance have
not been tested live. Anthropic uses reversible typed-map transport, preserves canonical
bounds via original Pydantic validation, reserves against actual transformed schema/instructions,
and skips unsupported schemas before network activity. PaperScout, CitationScout,
LocalDocumentScout and PriorArtHunter exceed the documented 16-union cap and require another
configured provider. Settings shows each blocked role; preflight rejects missing fallback.
Provider rejections still use ordinary fallback. Default timeout remains 60 seconds, configurable
up to 600; no automatic output-budget or thinking-policy increase was applied.

## Verification artifacts

- [Backend JUnit](audits/studio-backend-offline.xml): 206 passing offline tests; 2 live deselected.
- [Frontend unit JSON](audits/studio-frontend-tests.json): 3 passed in 2 files.
- [Playwright JSON](audits/studio-playwright.json): 2 passed, 0 failed.
- Ruff format/check passed for the Python tree; mypy passed for 116 source files.
- Frontend ESLint/TypeScript/Vite production build passed; npm dependency audit found no vulnerabilities.

The only backend test warning is the installed Starlette TestClient's httpx deprecation notice;
it is not an application failure. No paid/live test flags were used.

## Screenshots

All are actual Playwright captures of the functioning application, regenerated after data
hydration, under [screenshots/](screenshots/). File hashes are in
[studio-screenshots.json](audits/studio-screenshots.json).

| View | Capture |
| --- | --- |
| Dashboard | [studio-dashboard.png](screenshots/studio-dashboard.png) |
| Workflow / real execution history | [studio-workflow.png](screenshots/studio-workflow.png) |
| Agents | [studio-agents.png](screenshots/studio-agents.png) |
| Paper Library | [studio-paper-library.png](screenshots/studio-paper-library.png) |
| Evidence Explorer | [studio-evidence-explorer.png](screenshots/studio-evidence-explorer.png) |
| Gap Board | [studio-gap-board.png](screenshots/studio-gap-board.png) |
| Novelty Lab | [studio-novelty-lab.png](screenshots/studio-novelty-lab.png) |
| Novelty Battle | [studio-novelty-battle.png](screenshots/studio-novelty-battle.png) |
| Hardware Lab | [studio-hardware-lab.png](screenshots/studio-hardware-lab.png) |
| Paper Builder | [studio-paper-builder.png](screenshots/studio-paper-builder.png) |
| Provider Settings | [studio-provider-settings.png](screenshots/studio-provider-settings.png) |
| Completed Practice | [studio-practice-completed.png](screenshots/studio-practice-completed.png) |

## Operational commands and limits

See [STUDIO.md](STUDIO.md) for installation, two-terminal development and detailed operation.
After `npm ci` and `npm run build` in `studio/frontend/`, run from `research_council/`:

```powershell
.\.venv\Scripts\research-council.exe studio
```

Open http://127.0.0.1:8765. Development: `research-council studio backend` plus `npm run dev`.

Known limits: local single-operator deployment; frontend build from the repository checkout
is required (standalone wheel does not bundle it); PDF OCR is unavailable; pause/cancel waits
for the current durable stage boundary; action adoption restarts dependent planning rather
than merging arbitrary edits; paper generation provides grounded roadmaps/drafts with missing
support, not a publication-ready manuscript; real service access and scientific validation
remain unexecuted; complex Claude schemas require fallback. Technical scientific field names
and source content may stay English within the bilingual UI. None of these limits bypasses
the scientific quality gates or authorizes automatic readiness promotion.
