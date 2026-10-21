# Final implementation audit

Date: 2026-10-21. Platform actually tested: Windows, Python 3.12.10.
Scope: the local Research Council V1 implementation on `engineering-audit-v1`.
This is a tested single-user engineering baseline. It is not a claim of production readiness,
scientific novelty, publication acceptance or completed real research.

## Result and evidence

**113 passed, 0 failed**, with 0 skipped tests in the clean installed-wheel acceptance suite.
The development suite also passed 113 tests. Ruff formatting/lint and mypy passed; mypy checked
81 source files. `pip check` passed in the development and isolated installation environments.

**Acceptance A-Z: 26 PASS, 0 FAIL.**

Acceptance A-Y executes against the wheel installed in a newly created `.acceptance-env`,
without system-site packages or an editable project import. Z checks this document against the
recorded test totals and explicit limitations after engineering review. Final A-Z statuses are in
[acceptance-results.json](audits/acceptance-results.json). This documentation consistency check
does not constitute an independent external scientific or security audit.

Reproducible evidence:

- [Original independent review](audits/pre-phase2-audit.md): 58-test inherited baseline, severity-classified findings.
- [Remediation closure](audits/pre-phase2-remediation.md): implemented corrections and residual debt.
- [Clean install record](audits/clean-install.json): dependency versions and final tested wheel SHA256.
- [Pytest JUnit](audits/pytest-junit.xml) and [console output](audits/pytest-output.txt).
- [Acceptance runner](../scripts/acceptance.py): four installed-wheel modes, migrations, graph/exports and regression evidence.
- [Phase reports](phases/): historical implementation reports followed by dated independent re-audit sections.

The first clean-wheel acceptance attempt exposed an import-order cycle hidden by the existing
test collection order. Lazy agent exports and type-only core dependencies corrected it; six
fresh-process public-module import regressions now pass. Failed intermediate checks were fixed
before phase acceptance. Final totals describe the final tree, not those intermediate attempts.

## Phase completion

“Complete” here means the scoped local V1 implementation and offline acceptance, with the
integration limitations below. It does not mean every possible future connector/deployment exists.

| Phase | Status | Main audited result | Passing tests at phase check |
|---|---|---|---:|
| 0 | Complete | Severity audit, architecture review and ADRs 0004-0007 | 77 |
| 1 | Complete | Typed scientific graph, run/revision storage, composite FKs, migration 0002 | 77 |
| 2 | Complete | Three HTTP adapters, fake adapter, role/profile routing, retry/fallback, actual provider provenance | 81 |
| 3 | Complete | Twenty bounded role contracts/prompts, isolated contexts, injection/tool rejection | 85 |
| 4 | Complete | Deterministic async stages, fenced leases, events, checkpoints and interrupted-run recovery | 88 |
| 5 | Complete | Discovery ports, open connectors, eight query strategies, weighted triage, saturation | 94 |
| 6 | Complete | Located/hash-linked chunks, ranked retrieval, evidence/claim validation, retained conflicts | 97 |
| 7 | Complete | Revision-linked targeted requests, independent attacks, bounded/saturated termination, observed knowledge map | 100 |
| 8 | Complete | Sourced hardware parameters, estimate/measurement distinction, complete experiment proof plans | 103 |
| 9 | Complete | Audit/review/benchmark CLI, nineteen exports, structured attempt traces, root CI configuration | 103 |
| 10 | Complete | Gold/human evaluation, negative regressions, isolated-wheel A-Z acceptance and this audit | 113 |

## Architecture status and corrections

The workflow engine controls bounded execution; agents exchange typed state rather than shared
chat histories. Agents call ModelRouter and allowed typed tools. Vendor HTTP details stay in
provider adapters; agents execute no SQL. Repository protocols exist, although some application
services still depend on the concrete SQLRepository facade.

The validated chain is PAPER -> EVIDENCE -> CLAIM -> GAP -> NOVELTY -> PRIOR ART -> REVIEW ->
DECISION -> EXPERIMENT -> PAPER PLAN. Every checkpoint, including dictionary input, validates
references, duplicate identities, source grounding, candidate revisions and experiment/outline
links before transactional projection. Migration 0002 adds run/revision artifact identities and
same-run composite-FK links; migration 0001 was preserved. Earlier runs/revisions no longer collide.

DeepReader receives ranked bounded chunks with paper/page/offset/source hashes. Exact quotation
grounding yields partial verification, not semantic entailment. Mathematical analysis cannot
label a newly generated conclusion AUTHOR_REPORTED. Hypotheses remain UNVERIFIED. Journal
quartile requires journal, year, category and source rather than reputation-based guesses.

Opposing evidence survives omission both within a state and across replacement checkpoints.
EvidenceConflict records retain severity, support, contradiction and named resolution provenance.
Resolution never verifies the claim. Existing fatal citation conflicts cannot be hidden by a later
positive human attestation. ReviewerTwo cannot mark its own objections resolved. The system
records a trusted local user's review; it cannot prove that a reviewer actually read a publication.

PriorArtHunter and ReviewerTwo receive normalized claims, keywords and minimal evidence without
generator interpretations/confidence/private reasoning. ReviewerTwo prefers a configured different
actual provider and records same-provider fallback explicitly. Provider diversity reduces one
coupling but does not establish scientific independence or eliminate shared model bias.

## Database, checkpoints and novelty loop

SQLite initialization, migration head/base/head, scoped reads, cross-run/revision preservation,
cross-run FK rejection and stale-writer fencing pass. PostgreSQL remains architecturally supported
through SQLAlchemy/optional driver configuration but was not executed. Snapshots are keyed by run,
artifact and candidate revision; this is not an append-only forensic/event-sourcing ledger.

The engine persists stage events and configuration/workflow versions. Resume skips completed
stages; pending targeted search precedes the next revision. Partial-stage failure, cancellation,
lease exclusion, stale ownership and changed configuration are tested. Active workflows and slow
CLI audits renew leases. Abrupt process death can leave incomplete execution records and requires
lease expiry; incompatible workflow/state migrations require explicit future work.

Prior-art search records queries and citation/author chains. Judge REVISE creates typed targeted
search requests. Iteration limit defaults to three. Completed low-information rounds can produce
SEARCH_SATURATED with reasons; connector failure cannot count as saturation. Pending proposals
finish UNRESOLVED, never silently SURVIVE. Current candidate revision and operational attack
executions are rechecked before experiment selection and publication assessment.

The lightweight RF/DSP knowledge map links observed papers/claims/gaps to method families.
Its coverage score measures extraction within that observed node, not universal literature coverage.

## Quality-gate status

- Gate 1 checks source identity, metadata provenance, deduplication and available source text.
  Explicit synthetic fixtures can pass this operational source check; they remain excluded from
  scientific verification and novelty/publication survival.
- Gate 2 requires actual successful hunter/reviewer/judge executions, successful operational
  queries, matching revision, grounded evidence and no unresolved severe attack/conflict. Overlap
  matrices require source-specific evidence. Positive and negative gate fixtures are tested.
- Gate 3 requires traceable verified primary claims and claim-specific human scientific audits,
  hypothesis/baselines/metrics/ablations/statistics/failure/acceptance/reproducibility fields, linked
  experiment/paper plans and limitations. No unverified primary novelty hypothesis may pass.
  Positive explicit-human-review fixtures and fatal-conflict rejection regressions are tested.

A completed workflow may honestly fail Gate 2 or Gate 3. Completion means the bounded workflow
finished, not that its scientific conclusions or publication readiness were verified.

## Provider and connector status

| Integration | Implemented/tested | Live status |
|---|---|---|
| FakeProvider | Structured output, failures, delay/concurrency, usage, all modes | Offline only; no credentials |
| OpenAI Responses | HTTP adapter, schema/usage/error normalization, mocked wire tests | No paid calls; requires OPENAI_API_KEY and account-valid model/prices |
| Anthropic Messages | HTTP adapter, schema/usage/error normalization, mocked wire tests | No paid calls; requires ANTHROPIC_API_KEY and model/prices |
| Gemini generateContent | HTTP adapter, schema/usage/error normalization, mocked wire tests | No paid calls; requires GOOGLE_API_KEY and model/prices |
| Crossref | DOI resolution, discovery and available citation metadata | Mocked; no real literature benchmark in this session |
| OpenAlex | Search/metadata/backward/forward/author/related exploration | Mocked; OPENALEX_API_KEY supported when service/account requires it |
| arXiv | Atom search adapter, serial request spacing, bounded XML, caching | Mocked; no live query in this session |
| Local PDF/TXT/Markdown | Workspace-safe text extraction, bounded inputs, optional identity sidecar | Local parsing tested; no OCR |
| IEEE | Optional injected authenticated-backend boundary; explicit unavailable error | No authenticated backend or restricted-site scraping |
| Semantic Scholar | Search port allows a future adapter | Not implemented; remains an optional extension |

Streaming currently provides an explicitly advertised buffered fallback, not native incremental
token streaming. Live protocol, credentials, schema/model compatibility, quotas and provider billing
require deployment smoke tests. Model prices come from configuration; recorded costs are estimates
and can include conservative reservation bounds. Search-service costs are separate.

## Outputs, observability and evaluation

Every accepted installed-wheel mode generated exactly nineteen files at
`workspace/outputs/RUN_ID/`; all eighteen non-manifest file hashes were verified. The manifest
contains gates, search attempts/saturation, conflicts, targeted requests, observed map, source
chunk locations/hashes, workflow events, token usage and estimated model cost. Claims and evidence
are separate JSONL exports. Hardware and experiment exports preserve complete typed plans.

`workspace/runs/RUN_ID/trace.jsonl` records agent/stage events and per-model provider/model,
start/end, latency, tokens, estimated cost, retry and status. Sensitive provider bodies/keys are
not deliberately logged; document/model content is not a trusted place to store secrets.

Evaluation measures structural citation completeness, labelled identity/existence precision,
grounding, hallucinated references, structured-output success, latest-revision novelty false
positives, source coverage, latency, reported tokens and estimated cost. Zero denominators and
missing independent labels yield null. Human fields cover technical depth, research usefulness,
novelty usefulness, hardware realism and publication readiness. No scientific quality score was
invented from the synthetic acceptance runs.

## Benchmark readiness

**BENCHMARK_READY_BUT_NOT_EXECUTED**

The requested compressed-sensing/FHSS detection, parameter estimation and DOA benchmark is
prepared with 500-1000 hops/s, coherent multi-channel SDR and FPGA/RFSoC/Zynq constraints.
Preparation stores empty findings and measured-results lists. The acceptance suite uses visibly
synthetic fictional sources solely to exercise software. No real benchmark literature review,
novel contribution, FPGA synthesis/utilization or RF measurement is claimed.

## Installation and operator commands

From `D:\AGENTS_RESEARCH\research_council`:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e '.[dev]'
.venv\Scripts\research-council init
.venv\Scripts\research-council run --topic "Synthetic system test" --mode novelty --demo
.venv\Scripts\python scripts/check.py
```

For a release installation, build a wheel and install it into a separate environment:

```powershell
.venv\Scripts\python -m pip wheel . --no-deps --wheel-dir dist
python -m venv .acceptance-env
.acceptance-env\Scripts\python -m pip install 'dist/research_council-1.0.0-py3-none-any.whl[dev]' -c requirements-dev.lock
.acceptance-env\Scripts\python scripts/acceptance.py
```

Use a new environment name if `.acceptance-env` already exists. The actual clean installation
used pip cache downloads but had no inherited development dependencies/system-site packages.

Copy `.env.example` to `.env`, set the desired provider keys, and copy
`config/live.example.yaml` to `config/live.yaml`. Replace every enabled `CONFIGURE_ME` model and
null per-million-token price with values for the operator's account. Keys stay in environment
variables. YAML providers are `openai`, `anthropic`, and `google`; ordered route lists define
fallbacks. One-provider deployments can map every profile to that provider and need only its key.
Role overrides and model-ID environment variables are documented in provider-routing.md.

```powershell
# OpenAI: OPENAI_API_KEY; Anthropic: ANTHROPIC_API_KEY; Gemini: GOOGLE_API_KEY
.venv\Scripts\research-council run --project examples/fhss.yaml --mode deep --config config/live.yaml --live
.venv\Scripts\research-council run --project examples/fhss.yaml --mode novelty --config config/live.yaml --live
.venv\Scripts\research-council resume RUN_ID
.venv\Scripts\research-council status RUN_ID
.venv\Scripts\research-council audit RUN_ID
.venv\Scripts\research-council export RUN_ID
.venv\Scripts\research-council benchmark prepare --project examples/fhss.yaml
```

Replace RUN_ID with the created UUID and pass the same `--workspace` when using a custom
workspace. Resume uses pinned settings. The live example enables human approval points; inspect
the paused state and use `approve RUN_ID` then `resume RUN_ID`. Scientific attestation is a
separate evidence review, described in human-review.md. No approval bypass is built into resume.

## Known limitations, security limitations and next engineering work

1. Live paid LLM APIs, PostgreSQL and the remote Linux/Windows CI matrix were not executed here.
   Run account-specific mocked-to-live smoke tests and a PostgreSQL migration/concurrency matrix.
2. Prompt isolation/tool allowlists and injection fixtures reduce exposure but cannot guarantee
   semantic resistance to all malicious documents. No document-provided code is executed.
3. This trusted local CLI has no multi-user authentication, reviewer identity authentication,
   central audit service, encrypted secret store or distributed worker coordination.
4. Lexical retrieval can miss relevant semantic passages; the small RF/DSP taxonomy and two
   synthetic acceptance sources do not measure scientific recall, novelty validity or usefulness.
   Build independently annotated literature/evidence and adversarial evaluation sets next.
5. Metadata, abstracts and missing full text limit analysis; no OCR, arbitrary URL full-text
   retrieval, licensed IEEE backend or authoritative quartile feed is included. Add authorized
   connector adapters and a Semantic Scholar implementation if required by deployment.
6. Hardware numeric anchoring remains a conservative source check; it does not establish semantic
   entailment, timing closure or measured performance. Experiment execution/result ingestion,
   lab/synthesis integration and verification of new contribution claims remain future work.
7. Resume supports the tested state/workflow version; automatic migration of arbitrary older
   checkpoints, full source-refresh versioning and append-only artifact history are not included.
8. Broader dependency inversion, native streaming, centralized tracing, release signing and
   pinning CI actions to verified commit hashes remain maintenance work. No remote push or CI
   execution was performed; all implementation commits are local.
