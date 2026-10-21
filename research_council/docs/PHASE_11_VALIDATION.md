# Phase 11 implementation and operator guide

Status: **PHASE_11_IMPLEMENTED / LIVE_VALIDATION_NOT_YET_EXECUTED / SRL-0**.

For the current operational handoff, use [FIRST_LIVE_RUN.md](FIRST_LIVE_RUN.md) and
`config/phase11.operator.example.yaml`. The verification below records the Phase 11
implementation checkpoint; the subsequent preflight suite adds 20 cases (179 total).

This extends baseline `b992b9fbb6125cd1ec177b49b3a4e604291386bb` on
`phase-11-live-validation`. Phase 0–10 reports and FINAL_IMPLEMENTATION_AUDIT remain the
historical engineering baseline. No real scientific result, novelty survival, measured hardware
performance, human judgment or readiness advancement is claimed by this delivery.

## Verification

The final offline suite contains the unchanged 113 baseline tests and 46 Phase 11 cases:
159 passed, zero failed, two live tests deselected. Ruff format/check and mypy (100 source
files) pass. See [JUnit evidence](audits/phase11-offline.xml) and
[installed-wheel preparation evidence](audits/phase11-results.json). The installed wheel
contains the benchmark YAML, prompts, migrations and validation CLI. Its preparation run
exports all 23 report sections and eight human-review files without instantiating Runtime.
The archived package is in [phase11-prepared](audits/phase11-prepared/).

No Phase 11 live adapter test, paid provider request or live benchmark was executed.
Benchmark model/search calls: 0; estimated model cost: USD 0; paid cost incurred by this
benchmark execution: USD 0. No billing statement was queried; actual billed cost fields
remain null. Public arXiv/publisher pages were consulted to curate three seed references.
Those public source checks are not counted as a scientific benchmark run.

## Implementation acceptance A–V

These are software acceptance results, not scores for scientific validity.

| Criterion | Result | Evidence |
|---|---|---|
| A Existing 113 tests | PASS | All original test modules retained and included in the final offline suite. |
| B New offline tests | PASS | 46 cases in `tests/test_science_*.py`. |
| C No offline API keys | PASS | Fake providers/mock transports; preparation test forbids Runtime construction. |
| D Real benchmark structure | PASS | `benchmarks/cs_fhss_doa_fpga/`, 10 RQs, 14 perspectives, query provenance. |
| E No fabricated seeds | PASS | Three primary-source identities with version/year notes and provenance URLs. |
| F Seed recall | PASS | DOI/title-author-year matching, explicit denominator and null when unmeasured. |
| G Method coverage | PASS | Observed lexical family/concept probes; not semantic or universal recall. |
| H Evidence metrics | PASS | Location/grounding plus independent human entailment/support/contradiction labels. |
| I Identity conflicts | PASS | DOI/title/year/author/venue conflicts retained before dedup and CORE selection. |
| J Disagreements | PASS | Actual execution references, both positions, severity and named resolution retained. |
| K Negative control | PASS | Unchanged OMP application control; raw model verdict preserved beside policy result. |
| L Hallucinated reference | PASS | Invented-title regression returns NOT_FOUND_IN_SEARCHED_SOURCES without metadata. |
| M Expert package | PASS | All eight files exported; human judgment cells remain blank. |
| N Readiness levels | PASS | Typed SRL-0 through SRL-9 with persisted evidence history. |
| O Evidence before SRL | PASS | Sequential advancement, record references, artifact digest, prerequisites and named reviewer. |
| P Budget | PASS | Six bounds; persisted reservations/admission; partial checkpoints on exhaustion. |
| Q Explicit live consent | PASS | Both CLI flags required; stored confirmation checked again by Runtime. |
| R Saturation measurement | PASS | Search-round counts and labelled method/citation proxies, scoped saturation wording. |
| S Bounded attack | PASS | Maximum three iterations; revision IDs, changes, reasons and triggering prior art. |
| T Existing gates | PASS | Baseline regressions pass; scientific checks additionally reject missing coverage/evidence. |
| U Provenance | PASS | Commit/dirty state, actual source/prompt hashes, queries, identities, evidence, budget/cost. |
| V Scientific report | PASS | Generated `LIVE_SCIENTIFIC_VALIDATION.md`, all 23 required sections. |

## Reproduce offline checks and preparation

Run from `research_council` after installing the project with its dev extra:

```powershell
python -m pip install -e ".[dev]"
python -m ruff format --check .
python -m ruff check .
python -m mypy
python -m pytest -q -m "not live"
research-council validate-science --project examples/fhss.yaml --config config/phase11.live.example.yaml --workspace workspace/phase11-prepare
```

The prepare command needs no keys, does not load provider configuration or `.env`, and only
hashes the planned config. Supplying either execution flag alone still prepares only.
The prepared run cannot be converted to live; start a separate explicitly confirmed run.
Outputs are at `workspace/phase11-prepare/outputs/RUN_ID/`. The preparation report has no
retrieved papers/evidence and uses null metrics rather than invented perfect/zero recall.

## Operator-confirmed live execution

Copy `config/phase11.live.example.yaml` to `config/phase11.operator.yaml`. Replace every
`CONFIGURE_ME` with a model available to your account and provide current input/output
prices per million tokens. Configure all eight task profiles, no fake fallback. Select
different generator and adversarial reviewer routes where possible. Role overrides can give
NoveltyJudge a third route. Keep the six budgets and human approval enabled. The example
limits are USD 5 model estimate, 80 model attempts, 1000 scholarly HTTP attempts, 12 CORE
papers, 12 deep reads and three novelty iterations. These are caps, not expected usage.

Set `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` and/or `GOOGLE_API_KEY` in the operator environment
for the providers actually configured. Keys belong only in the environment or ignored `.env`.
Do not insert keys into YAML. Then the operator may explicitly execute:

```powershell
research-council validate-science --project examples/fhss.yaml --config config/phase11.operator.yaml --workspace workspace/phase11-live --live --confirm-paid-apis
```

Record the printed run ID. The command pauses for configured workflow approvals. Inspect
status and exports, approve only the current checkpoint, then resume with both flags:

```powershell
$runId = "REPLACE_WITH_PRINTED_LIVE_RUN_UUID"
research-council status $runId --workspace workspace/phase11-live
research-council approve $runId --workspace workspace/phase11-live
research-council validate-science --resume $runId --workspace workspace/phase11-live --live --confirm-paid-apis
```

Repeat as the workflow reaches each approval. Resume uses the original pinned settings and
persistent budget; it does not reset spending. BUDGET_EXHAUSTED retains partial results and
is terminal for that budget/run. Source failures are recorded and cannot prove absence.

At `after_gaps`, experts may use [claim-specific scientific attestation](human-review.md)
for grounded source premises before the novelty loop. Scientific attestation and workflow
approval are separate. Hypotheses and identity conflicts cannot be attested. The final
publication gate still requires its original claim-specific evidence and experiment plan.

```powershell
research-council attest-claim $runId --workspace workspace/phase11-live --attestation premise-review.json
```

## Independent review and report refresh

Complete the sampled `human_review/evidence_review.csv` manually. A sample uses a stable seed
and contains 20 real evidence objects when available, otherwise all available real objects.
Import judgments using workspace-relative JSON, with actual IDs from that run:

```json
{
  "reviewer": "Named domain expert",
  "note": "Describe the independent source and scientific checks actually performed.",
  "evidence": [],
  "contradiction_labels": [],
  "claim_support_labels": {},
  "gap_reviews": {},
  "novelty_reviews": [],
  "model_scores": [],
  "model_positions": [],
  "disagreement_resolutions": {}
}
```

This empty example grants no scientific approval. Evidence entries have `evidence_id`,
`reviewer`, three nullable booleans `human_location_correct`, `human_entailment_correct`,
`human_interpretation_correct`, and `notes`. Gap reviews map gap UUIDs to APPROVE/REJECT/
UNRESOLVED. Novelty entries require `candidate_id`, `revision`, `verdict` and a note of at
least 20 characters. Model scores identify an actual `execution_id` and named `reviewer`;
optional scores range 0–1. Model positions identify the actual execution/provider/model,
subject/task, stance SUPPORT/OPPOSE/UNCERTAIN and the observed position. Disagreement
resolutions map existing disagreement UUIDs to a substantive human explanation; original
positions and execution references remain. These imported measurements do not automatically
attest claims or advance SRL.

```powershell
research-council validate-science --resume $runId --workspace workspace/phase11-live --human-reviews expert-review.json
research-council science-readiness $runId --workspace workspace/phase11-live
```

Report refresh without both live flags makes no network/model calls. To request one SRL
advancement, create a workspace-relative JSON `ReadinessEvidence` object containing run_id,
numeric target (current + 1), actual record_ids, artifact_path, artifact_sha256, named reviewer,
statement and source_kind. Use LIVE_SYSTEM for levels 1–3/6 and HUMAN_REVIEW for 4/5/7.
The artifact must exist inside the workspace; all preceding factual prerequisites must hold.

```powershell
research-council science-readiness $runId --workspace workspace/phase11-live --proof readiness-proof.json
research-council validate-science --resume $runId --workspace workspace/phase11-live
```

## Optional live smoke tests

These commands are for the operator; they were not executed for this delivery:

```powershell
$env:RESEARCH_COUNCIL_LIVE_CONFIG = (Resolve-Path config/phase11.operator.yaml).Path
python -m pytest -q -m live --run-live --confirm-paid-apis
```

The model smoke permits one model attempt with a USD 0.25 estimate cap and no scholarly
requests; the other test resolves a known Crossref DOI. Selecting live tests without both
test confirmations fails during collection. CI explicitly selects `-m "not live"`.

## Limits that require live or expert evidence

- The three seed references are nonexhaustive, emphasizing selected foundational/implementation
  concepts. They do not establish FHSS/UAV/DOA coverage. Expected directed citation edges
  remain empty until independently curated; citation-chain recall therefore remains null.
- Known-answer tests use real, short source excerpts and fake model outputs to test contracts.
  They do not establish DeepReader/CitationAuditor capability with a real model.
- Lexical method/concept coverage and citation-seed clusters are explicit proxies. Metadata
  agreement is identity checking, not scientific entailment or authoritative retraction review.
- Prior-art source quotes remain PARTIALLY_VERIFIED; changed retained snapshots invalidate
  unsupported overlap records. No abstract-only quote proves full-text methodology/results.
- The weak-control policy rejects unchanged-method reuse independently. Its raw LLM verdict
  is retained so policy enforcement cannot be credited as successful model discrimination.
- Hardware numbers are source-reported/derived/estimated unless independently measured.
  No experiment-result ingestion or replication verification is provided in this phase; the
  CLI cannot currently establish SRL-8/9 prerequisites. Typed future transitions remain gated.
- Model costs are conservative estimates based on operator prices and token reservations,
  not an external billing guarantee. Source service fees and actual invoices are not measured.
- Human review is a local trusted-user record, not authenticated expert identity or proof
  that the reviewer read the source. No scientific outcome is inferred from software tests.

The archived preparation manifest identifies the source commit used before the final artifact
commit. Its hashes describe that execution; the final pushed commit SHA is reported separately.
