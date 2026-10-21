# V1 implementation and validation

Validated locally on 2026-10-21, Windows, Python 3.12.10.

| V1 requirement | Evidence |
|---|---|
| CLI starts a project | CLI lifecycle tests; FHSS offline CLI smoke run |
| Fake-provider end-to-end completion | All five modes plus explicit synthetic NOVELTY run |
| Three independently configurable providers | Mocked OpenAI/Anthropic/Gemini protocol tests |
| Concurrent branches | Semaphore test and observed fake provider max_active >=2 |
| Normalization/deduplication | DOI prefix/case, title, author/year, conflicting DOI/numeric title tests |
| Evidence linked to claims | Schema/repository/reader tests and exported evidence IDs |
| Evidence-grounded gaps | Synthetic end-to-end gap generation with traceable IDs |
| Independent prior-art/reviewer attack | Separate allowlist schema; actual search tool history; concurrent attack |
| Deterministic loop termination | Three unresolved demo iterations; bounded-loop and pending-search resume tests |
| Gates block unsupported conclusions | Empty work, fixture, missing evidence, wrong revision, severe review and audit tests |
| Retry/fallback | Malformed JSON, transient failure, timeout and fallback tests |
| Checkpoint/resume | Completed-stage replay prevention, substage checkpoint, lease/configuration tests |
| Token/cost/latency metrics | Persisted per-attempt records, cancellation and conservative budget tests |
| Traceable final report | End-to-end report contains evidence UUIDs and source identity/location |
| No paid test dependencies | Fake providers and HTTPX MockTransport throughout the suite |

Final checks: Ruff format/lint pass; mypy passes for 68 source files; pytest **58 passed**;
`pip check` reports no broken requirements. Wheel inspection found 20 external prompts and
both migration files, with no secrets, workspace data or bytecode. A wheel installed into a
separate target ran a synthetic DEEP workflow from the wheel package path.

The FHSS example was run with no real search adapters and produced zero evidence/claims.
A distinct synthetic demo generated explicitly fictional papers/evidence to test the software;
its novelty remained unresolved and publication readiness failed.

## Unverified deployment integrations

No live paid LLM requests or real scientific literature review was performed. Provider payloads
are checked against official documentation and mocked tests, not account-specific model access.
Live credentials, model/schema compatibility, rate limits and current token prices must be set
for the deployment. PostgreSQL and the supplied remote CI matrix have not been executed here.
Automatic quotation matching does not establish scientific entailment; human attestation is
required for verified primary conclusions. Search coverage cannot establish universal novelty.

## Deliberate V1 boundaries

Own deterministic asyncio orchestration instead of a framework dependency; HTTP adapters instead
of vendor SDK dependencies; JSON artifact payloads with indexed relational identity/scope; local
text-only PDF parsing; buffered provider stream fallback; model-cost budgets with conservative
reservations for unavailable usage; explicit workspace human review; no mandatory vector service.
Model-cost metrics exclude search-service charges. Source snapshots are cached, with source
refresh/version migration deferred. See the ADRs and security document for tradeoffs.
