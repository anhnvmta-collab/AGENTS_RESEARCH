# First live scientific run: operator runbook

Preparation status: LIVE_DEPLOYMENT_READY (tooling); LIVE_BENCHMARK_NOT_EXECUTED; SRL-0.
The example deliberately fails preflight until the operator supplies model IDs, prices and
credentials. No provider access or scientific result has been validated. This is Phase 11
operational preparation, not Phase 12.

## Step 1 — Checkout the correct branch

```powershell
Set-Location D:\AGENTS_RESEARCH
$councilGit = 'C:\Program Files\Git\cmd\git.exe'
& $councilGit fetch origin
& $councilGit switch phase-11-live-validation
& $councilGit pull --ff-only origin phase-11-live-validation
& $councilGit rev-parse HEAD
Set-Location research_council
```

The task starts at `4135a6436fab66e540fd904d3a87b19a0faee0e0`; the preflight preparation is a
descendant on the same branch. Record the actual checkout SHA with the run evidence.

## Step 2 — Install/update the environment

```powershell
if (-not (Test-Path .venv\Scripts\python.exe)) { py -3.12 -m venv .venv }
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
$council = (Resolve-Path .venv\Scripts\research-council.exe).Path
```

## Step 3 — Run offline verification

```powershell
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe -m pytest -q -m "not live"
```

Stop if any check fails. Live tests remain excluded. No keys are required for this suite.

## Step 4 — Copy the operator configuration

```powershell
Copy-Item config\phase11.operator.example.yaml config\phase11.operator.yaml
```

Keep one operator YAML. It enables human approvals and explicitly defines all eight profiles,
fallbacks, and a third-provider judge preference. [Provider setup](LIVE_PROVIDER_SETUP.md)
explains the three YAML anchors and how to disable an unavailable provider.

## Step 5 — Configure model IDs

Replace CONFIGURE_ME at each enabled anchor with an account-valid model supporting the
existing provider protocol/JSON schema. No current model ID is assumed. Disabled routes may
retain placeholders. A single-provider configuration is permitted with visible warnings.

## Step 6 — Configure pricing

Enter verified USD input/output prices per million tokens and `pricing_verified_on` at each
enabled anchor. Check the actual model/context tier with the provider. Missing prices prevent
live cost estimation and block preflight; stale/missing review dates produce warnings.

| First-run cap | YAML field | Limit |
|---|---|---|
| Model estimate | max_total_cost | USD 5 |
| Model attempts, including retries/fallbacks | max_model_calls | 80 |
| Scholarly HTTP attempts, including metadata/retries | max_search_calls | 1000 |
| CORE papers | max_core_papers | 12 |
| Deep reads | max_deep_reads | 12 |
| Novelty iterations | max_novelty_iterations | 3 |

The stricter research/live budget applies. Budget exhaustion preserves partial results and is
terminal for that run. Resuming does not reset counters. These are software admission caps
based on operator prices and conservative token reservations; provider invoices, source-service
charges and account balances are external. Never treat the estimate as a reconciled invoice.

## Step 7 — Set API keys

Follow [the PowerShell guide](LIVE_PROVIDER_SETUP.md). Set OPENAI_API_KEY, ANTHROPIC_API_KEY,
GOOGLE_API_KEY for enabled providers. OPENALEX_API_KEY is recommended for research-scale source
use. Neither YAML nor research outputs should contain credentials.

## Step 8 — Run the non-paid preflight

```powershell
& $council providers preflight --config config/phase11.operator.yaml
```

This command creates no HTTP client, research run or inference request. It checks syntax,
explicit profiles, enabled routes, key presence, placeholders, fallback/diversity, price dates,
budgets, approvals and scholarly-source configuration. Exit 1 means resolve errors first;
warnings require operator review. It cannot verify model IDs/access or scientific coverage.
Crossref/OpenAlex/arXiv are CONFIGURED_NOT_TESTED, not SERVICE_REACHABLE or SCIENTIFICALLY_VALIDATED.
The optional IEEE backend is not wired and blocks preflight if enabled.

## Step 9 — Optional minimal paid provider smoke

Only the operator should run this, after reviewing the configuration and the separate cap:

```powershell
& $council providers preflight --config config/phase11.operator.yaml --workspace workspace/provider-smoke --live --confirm-paid-apis
```

Both flags are mandatory; either alone fails before execution. The smoke uses one request per
enabled provider (up to three), 128 output tokens, no retries/fallback requests, no scholarly
requests and a maximum USD 0.25 aggregate model estimate (or the lower configured cap).
If admission exceeds the cap it makes no extra request. Results/usage are stored in a separate
smoke workspace. A failure may reflect unsupported model/schema or output truncation; inspect
it without automatically rerunning or raising caps. A successful protocol smoke proves neither
scientific quality nor compatibility of every model in a custom configuration. It never runs
research stages, produces scientific findings or advances the scientific benchmark SRL.

## Step 10 — Prepare the scientific benchmark

```powershell
& $council validate-science --project examples/fhss.yaml --config config/phase11.operator.yaml --workspace workspace/phase11-prepare
```

This is preparation only. Inspect its printed report path. The CS_FHSS_DOA_FPGA benchmark uses
10 RQs, 14 perspectives and query families. Its verified seeds are unchanged. FHSS 500–1000
hops/s, coherent SDR, FPGA/RFSoC/Zynq, compressed sensing/sparse recovery, parameter estimation
and DOA are research constraints, not findings. Empty/unmeasured metrics remain null.

## Step 11 — Launch only after explicit paid approval

Review the step-8 results and budget first. The operator explicitly authorizes paid execution
by issuing this command; this preparation task does not execute it:

```powershell
& $council validate-science --project examples/fhss.yaml --config config/phase11.operator.yaml --workspace workspace/phase11-live --live --confirm-paid-apis
```

The prepared offline run is separate and cannot be converted into a live run.

## Step 12 — Record RUN_ID

```powershell
$runId = 'REPLACE_WITH_PRINTED_LIVE_RUN_UUID'
```

Retain the checkout SHA, config hash and report path. Keep the original workspace/database.

## Step 13 — Inspect the workflow pause

```powershell
& $council status $runId --workspace workspace/phase11-live
```

Human approvals pause after_plan, before_expensive_deep, after_gaps,
before_accepting_novelty, and before_final_report. Inspect the plan/scope, then the evidence,
gaps and adversarial reports appropriate to each checkpoint. A permission approval is separate
from scientific evidence verification. At after_gaps, use [claim-specific expert attestation](human-review.md)
for source premises when justified; hypotheses/identity conflicts remain blocked.

## Step 14 — Approve the current checkpoint deliberately

```powershell
& $council approve $runId --workspace workspace/phase11-live
```

Approval allows continuation. It does not certify novelty, clear contradictions or advance SRL.
Use reject/modify if the current scope or evidence is unacceptable. Do not batch-auto-approve.

## Step 15 — Resume with explicit flags and pinned configuration

```powershell
& $council validate-science --resume $runId --workspace workspace/phase11-live --live --confirm-paid-apis
```

Settings/consent/counters are stored in the run. Editing the operator YAML does not change a
pinned run. Budget/identity/provenance and approval checks remain enforced after resume.

## Step 16 — Repeat until bounded termination

Repeat inspection, deliberate approval and resume only as each pause is reached. COMPLETED,
FAILED, REJECTED and BUDGET_EXHAUSTED require review; COMPLETED alone does not prove readiness.
Transient failed stages retain checkpoints; a paid resume may consume remaining budget.
Do not erase the workspace to disguise exhaustion or substitute connector failure for absence.

## Step 17 — Export/refresh the scientific reports without network

```powershell
& $council validate-science --resume $runId --workspace workspace/phase11-live
```

Without both live flags this refreshes exports only. Inspect
`workspace/phase11-live/outputs/RUN_ID/LIVE_SCIENTIFIC_VALIDATION.md`, the eight human_review
files, scientific_metrics/reproducibility JSON, model_benchmark/provider_independence CSVs,
hardware assumptions, search rounds and the run manifest. Use the [review checklist](LIVE_RUN_REVIEW_CHECKLIST.md).
Independent review import and evidence-backed SRL requests are documented in
[Phase 11 validation](PHASE_11_VALIDATION.md).

## Step 18 — Inspect scientific readiness

```powershell
& $council science-readiness $runId --workspace workspace/phase11-live
```

Omitting --proof is read-only. No automatic SRL increase occurs. Every advancement requires
sequential, named review, factual prerequisites and hashed proof artifacts. This preparation
leaves the project at SRL-0. Experiment/replication ingestion for SRL-8/9 is not implemented.
