# Research Council

Evidence-first scientific research workflows for RF, DSP, SDR, FPGA, RFSoC and extensible
domains. A deterministic asyncio workflow owns execution; 20 isolated agent roles perform
bounded tasks through typed contracts. Scientific claims must resolve to source evidence.

The local V1 implementation covers phases 0–10 after an independent engineering audit. Validation: **113 offline tests pass**, Ruff
format/lint and mypy pass, dependencies pass `pip check`, and an installed wheel runs a full
synthetic workflow with packaged prompts/migrations. Paid provider endpoints and PostgreSQL
have not been exercised live. See the [final implementation audit](docs/FINAL_IMPLEMENTATION_AUDIT.md),
[acceptance evidence](docs/audits/acceptance-results.json) and [phase reports](docs/phases).

## Install and run

Python >=3.11; validated here on Windows with Python 3.12.10. From this directory:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e '.[dev]'
.venv\Scripts\research-council init
.venv\Scripts\research-council run --topic "Real-time RF sensing" --mode deep
```

The default is an **offline empty-evidence run**. It completes an honest limited report with
no literature findings. To exercise the entire graph with unmistakably synthetic fixtures:

```powershell
.venv\Scripts\research-council run --topic "Synthetic workflow validation" --mode novelty --demo
```

The requested FHSS project is prepared in [examples/fhss.yaml](examples/fhss.yaml):

```powershell
.venv\Scripts\research-council benchmark prepare --project examples/fhss.yaml
```

Preparation records **BENCHMARK_READY_BUT_NOT_EXECUTED** with no findings. The benchmark produces no real research results until real search and model adapters are
explicitly enabled. Synthetic records cannot pass novelty survival or publication readiness.

## Enable real research

Copy [.env.example](.env.example) to `.env` and set only the provider keys you intend to use.
Copy [config/live.example.yaml](config/live.example.yaml), replace `CONFIGURE_ME` with model IDs
available to your account, and enter current input/output prices per million tokens. Each task
profile can use any supported provider (`openai`, `anthropic`, `google`) and ordered fallback
routes. Keep keys out of YAML. A configuration with one provider for every profile needs only
that provider's key.

```powershell
.venv\Scripts\research-council run --project examples/fhss.yaml --mode novelty --config config/live.yaml --live
```

Live runs require explicit `--live`, a real search/local-document source, a configured model
and prices, and at least one enabled provider key. Failed calls retry/fallback without inventing
findings. Missing token usage/timeouts consume a recorded conservative budget reservation.
Budget estimates cover model calls; search-service billing and quotas remain separate.

Search adapters: Crossref, OpenAlex and arXiv, plus workspace-contained local PDF/TXT/Markdown.
IEEE has an optional authenticated-backend boundary, with no restricted-site scraping.
Semantic Scholar remains an extension rather than an implemented connector.
Citation exploration supports backward, forward (OpenAlex), author and related chains. Abstract
retrieval only supports abstract-level extraction. Full text can be provided locally; no paywall
bypass, arbitrary URL downloading or OCR is included.

Local paths are relative to `--workspace`. Optional `paper.pdf.metadata.json` or
`source.txt.metadata.json` supplies publication identity, for example:

```json
{"title":"Title from the source", "authors":["Author name"], "year":2024, "doi":"10.1234/example"}
```

Sidecar metadata is unverified until reviewed/resolved. PDF file creation dates are not treated
as publication years. Missing quartile/retraction data remains unknown.

## Modes, recovery and human review

| Mode | Scope |
|---|---|
| QUICK | Plan and evidence-limited synthesis; two cognitive agent calls |
| REVIEW | Discovery, deduplication, triage, deep reading, citation audit, synthesis |
| DEEP | REVIEW plus mathematical/hardware analysis, gaps, experiment/paper roadmap |
| NOVELTY | Full relevant pipeline with independent prior-art/reviewer attack and bounded revision |
| AUDIT | Discovery/evidence plus attack on an explicit `--claim`; incomplete without a claim |

```powershell
.venv\Scripts\research-council status RUN_ID
.venv\Scripts\research-council resume RUN_ID
.venv\Scripts\research-council export RUN_ID
.venv\Scripts\research-council audit RUN_ID
.venv\Scripts\research-council models benchmark
.venv\Scripts\research-council evaluate RUN_ID
```

Runs pin their configuration and workflow version. Resume continues from checkpoints;
completed stages are not repeated. A run lease prevents concurrent writers. One failed scout
does not kill successful branches. Novelty iterations default to three; unresolved proposals
finish as `UNRESOLVED`, while the run can complete its limited report. Repeated completed searches
with negligible new information stop with `SEARCH_SATURATED`; adapter failures cannot establish saturation.

Set `research.human_approval_required: true` to pause after the plan, before expensive DEEP
work, after gaps, before accepting novelty, and before the final report. Use `approve`, `reject`,
`modify RUN_ID --topic "..."`, and `continue`. Continue cannot bypass a pending approval.
Modification restarts dependent stages. Workflow permission does not verify a scientific claim.

At `before_final_report`, scientific review can be recorded separately using a workspace-relative
JSON file and `attest-claim RUN_ID --attestation review.json`. The reviewer must explicitly
confirm identity, locations, entailment and retraction checks; see
[human-review.md](docs/human-review.md). Fixture, hypothesis and unresolved contradictory claims
cannot be promoted. Gate 3 is recalculated using claim-specific human audits.
Contradictions persist in `EvidenceConflict` records. `resolve-conflict RUN_ID --resolution review.json`
records named, documented human resolution while paused, preserving all opposing evidence.
Resolution itself does not verify the claim. Source identity conflicts continue to block attestation.

## Outputs and observability

Each run exports 19 files to `workspace/outputs/RUN_ID/`:

```text
research_plan.json      search_queries.json        paper_candidates.csv
core_papers.csv         literature_matrix.csv      literature_matrix.json
evidence.jsonl          claims.jsonl               research_gaps.md
novelty_candidates.md   prior_art_report.md        reviewer_report.md
novelty_decisions.md    hardware_feasibility.md    experiment_plan.md
ieee_paper_plan.md      citation_audit.csv         final_report.md
run_manifest.json
```

The final report preserves claim/evidence/paper IDs, DOI/URL, locations and verification
status. Manifest hashes cover all 18 other artifacts; it also records search attempts, saturation,
conflicts, observed knowledge map, chunk hashes, gates, usage, cost and iteration count.
`workspace/runs/RUN_ID/trace.jsonl` records workflow/agent events and every model attempt's
provider, model, start/end, latency, tokens, cost, retry and status. Database tables retain executions.
No shared transcript, vector service, graph database or orchestration framework is required.

Gate 1 checks paper identity, deduplication and retrieved text. Gate 2 checks actual completed
prior-art search, independent review, matching revisions and grounded evidence. Gate 3 requires
verified primary claims, claim-specific scientific audits, hypothesis, baselines, metrics, ablation,
statistics, failure cases, acceptance criteria, reproducibility, linked experiments/paper plan and
limitations. Automatic metadata/quotation matching establishes partial verification only.

## Development and evaluation

```powershell
.venv\Scripts\python scripts/check.py
.venv\Scripts\python -m pip check
.venv\Scripts\python -m pip wheel . --no-deps --wheel-dir dist
```

[pyproject.toml](pyproject.toml) defines accepted dependency ranges;
[requirements-dev.lock](requirements-dev.lock) records exact tested versions. Tests use fake
providers, synthetic papers/evidence and HTTPX mock transports; no paid APIs are required.
A GitHub Actions matrix is supplied for Python 3.11/3.12 on Linux/Windows, but has not been run
remotely from this workspace.

To reproduce clean-wheel acceptance, create a new environment, install the wheel with its dev
extra and run `scripts/acceptance.py` using that interpreter from this directory. The script
checks the installed package, migrations, four modes, exports and the full offline pytest suite.
After independently reviewing the final audit, use `scripts/acceptance.py --finalize docs/audits/acceptance-results.json`.

The evaluation harness measures citation precision/completeness, identity accuracy, evidence
grounding, hallucinated references, structured-output validity, novelty false positives,
latency, token usage and estimated model cost. Human fields include technical depth, research
usefulness, novelty usefulness, hardware realism and publication readiness. Independent labels and scores can be supplied
with `evaluate --gold labels.json --human scores.json`. Unknown/zero-denominator metrics are
`null`; missing annotations do not become perfect scores. Model benchmarks assess every
configured route and preserve the routing configuration.

## Architecture and extension points

[Architecture](docs/architecture.md) · [Workflow](docs/workflow.md) · [Data model](docs/data-model.md) ·
[Agent contracts](docs/agent-contracts.md) · [Provider routing](docs/provider-routing.md) ·
[Quality gates](docs/quality-gates.md) · [Security](docs/security.md) ·
[Implementation plan](docs/implementation-plan.md) · [V1 validation](docs/validation.md).

Ports cover repositories, model providers, search/citation/metadata adapters, workflow,
tracing, exporters and vector retrieval. SQLAlchemy and packaged Alembic migrations support
the local SQLite store; PostgreSQL is an optional driver/engine integration. An in-memory
vector store is available without embedding/network dependencies.

V1 is a single-user local CLI. Native incremental token streaming, OCR, licensed IEEE full-text
retrieval, authoritative quartile feeds, adaptive routing, distributed workers and authenticated
multi-user deployment remain future integrations. Source snapshots are reused to preserve
evidence reproducibility; automatic source refresh/version migration is not included.

## Phase 11 scientific validation

Phase 11 extends the offline baseline with the CS_FHSS_DOA_FPGA benchmark, identity/coverage
and evidence metrics, bounded live budgets, expert review exports, model disagreement and
evidence-backed scientific readiness. Start with preparation only:

```powershell
research-council validate-science --workspace workspace/phase11-prepare
```

Status: **PHASE_11_IMPLEMENTED / LIVE_VALIDATION_NOT_YET_EXECUTED / SRL-0**.
159 offline tests pass; two live tests are excluded by default and in CI. No paid benchmark
was run. See the [operator guide and A–V acceptance](docs/PHASE_11_VALIDATION.md),
[phase report](docs/phases/phase-11.md) and [generated preparation report](LIVE_SCIENTIFIC_VALIDATION.md).
Live execution requires both `--live --confirm-paid-apis` and an operator-configured model/pricing
file. Credentials alone do not authorize it. Existing Phase 0–10 audit results remain historical.

For the first real run, copy `config/phase11.operator.example.yaml` to the ignored
`config/phase11.operator.yaml`, configure the three provider anchors, then check without network:

```powershell
research-council providers preflight --config config/phase11.operator.yaml
```

[Provider/PowerShell setup](docs/LIVE_PROVIDER_SETUP.md), [18-step runbook](docs/FIRST_LIVE_RUN.md)
and [expert checklist](docs/LIVE_RUN_REVIEW_CHECKLIST.md) cover the complete handoff. Optional
provider smoke uses both execution flags and its own USD 0.25 aggregate estimate cap. The
operational preflight adds 20 offline regression cases; current suite: 179 passed, zero failed,
two live deselected. The Phase 11 audit above records the preceding 159-test handoff.
