# Research Council

Evidence-first scientific research workflows for RF, DSP, SDR, FPGA, RFSoC and extensible
domains. A deterministic asyncio workflow owns execution; 20 isolated agent roles perform
bounded tasks through typed contracts. Scientific claims must resolve to source evidence.

The local V1 implementation covers phases 0–10. Validation: **58 offline tests pass**, Ruff
format/lint and mypy pass, dependencies pass `pip check`, and an installed wheel runs a full
synthetic workflow with packaged prompts/migrations. Paid provider endpoints and PostgreSQL
have not been exercised live. See [validation.md](docs/validation.md) and [phase reports](docs/phases).

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
.venv\Scripts\research-council run --project examples/fhss.yaml --mode novelty
```

This system test produces no real research results until real search and model adapters are
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

Search adapters: Crossref and OpenAlex, plus workspace-contained local PDF/TXT/Markdown.
IEEE discovery uses compliant indexed metadata queries, with no restricted-site scraping.
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
.venv\Scripts\research-council models benchmark
.venv\Scripts\research-council evaluate RUN_ID
```

Runs pin their configuration and workflow version. Resume continues from checkpoints;
completed stages are not repeated. A run lease prevents concurrent writers. One failed scout
does not kill successful branches. Novelty iterations default to three; unresolved proposals
finish as `UNRESOLVED`, while the run can complete its limited report.

Set `research.human_approval_required: true` to pause after the plan, before expensive DEEP
work, after gaps, before accepting novelty, and before the final report. Use `approve`, `reject`,
`modify RUN_ID --topic "..."`, and `continue`. Continue cannot bypass a pending approval.
Modification restarts dependent stages. Workflow permission does not verify a scientific claim.

At `before_final_report`, scientific review can be recorded separately using a workspace-relative
JSON file and `attest-claim RUN_ID --attestation review.json`. The reviewer must explicitly
confirm identity, locations, entailment and retraction checks; see
[human-review.md](docs/human-review.md). Fixture, hypothesis and unresolved contradictory claims
cannot be promoted. Gate 3 is recalculated using claim-specific human audits.

## Outputs and observability

Each run exports to `workspace/runs/RUN_ID/exports/`:

```text
research_plan.json       paper_candidates.csv      literature_matrix.csv
literature_matrix.json  evidence.jsonl             research_gaps.md
novelty_candidates.md   prior_art_report.md        hardware_feasibility.md
experiment_plan.md      ieee_paper_plan.md         citation_audit.csv
final_report.md         run_manifest.json
```

The final report preserves claim/evidence/paper IDs, DOI/URL, locations and verification
status. Manifest hashes cover all 13 other artifacts; it also records queries/search attempts,
gates, token usage, estimated model cost and iteration count. `trace.jsonl` records structured
stage/agent events. Database tables retain per-attempt model metrics and agent executions.
No shared transcript, vector service, graph database or orchestration framework is required.

Gate 1 checks paper identity, deduplication and retrieved text. Gate 2 checks actual completed
prior-art search, independent review, matching revisions and grounded evidence. Gate 3 requires
verified primary claims, claim-specific scientific audits, baselines, metrics, experiments and
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

The evaluation harness measures citation precision/completeness, identity accuracy, evidence
grounding, hallucinated references, structured-output validity, novelty false positives,
latency and estimated model cost. Independent gold labels and human scores can be supplied
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
