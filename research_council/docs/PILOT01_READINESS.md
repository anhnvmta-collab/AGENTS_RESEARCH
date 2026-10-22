# Pilot 01 preparation readiness

Prepared on 2026-10-22 from `research-council-studio` at `487105bd0b3c75457df5fc24439fe3fd01bb4dec`. This report concerns offline preparation only.

```text
PILOT_CONFIG_READY = true (template, routing and project complete)
STUDIO_READY = true (offline workflow verified)
PRACTICE_MODE_PASS = true
PROVIDER_CONFIG_READY = false
BLOCKERS = operator account-valid model IDs, current token prices, credentials/access verification
PAID_CALLS = 0
LIVE_PILOT_EXECUTED = false
SRL = 0
```

`config/pilot01.example.yaml` intentionally cannot launch as supplied. It contains model-ID environment placeholders and null prices, with no credential values or unverified candidate model IDs. Do not interpret template readiness as provider readiness. No paid smoke, real literature discovery, scientific benchmark or live pilot was executed.

## Prepared configuration and project

The config explicitly routes all eight task profiles. Search/citation use OpenAI → Google; extraction uses Anthropic → OpenAI where compatible; math/synthesis use OpenAI → Anthropic; hardware uses OpenAI → Google; novelty generation uses OpenAI; adversarial review uses Google. NoveltyJudge uses Anthropic → Google → OpenAI. PaperScout, CitationScout, LocalDocumentScout and PriorArtHunter explicitly use OpenAI → Google because their canonical output contracts are Anthropic-blocked. Local schema transformations and canonical validation remain unchanged.

Caps: **USD 5 estimated model cost, 80 model attempts, 500 search calls, 12 CORE papers, 10 deep reads, 3 novelty iterations**. The canonical USD config field is `live_research_budget.max_total_cost`. Reservations and failures consume caps; no promise is made that every stage fits. Source-service fees and actual billing are not measured by this cap. Retries are zero; configured cross-provider fallbacks remain possible and visible. Human approval and review of each novelty iteration are enabled. The 180-second timeout is bounded and still requires review against the operator's chosen models.

Current analysis attempts one deep read per eligible CORE paper. Selecting 11–12 papers can exhaust the 10-read limit before gaps/novelty; targeted follow-up reads also share that limit. Before importing settings, the operator can reduce `research.max_core_papers` below the 12-paper ceiling to leave revision headroom. This delivery preserves the requested caps and does not silently enlarge them or promise a complete result within them.

`config/pilot01.project.yaml` contains the topic, all ten research questions, and the five hardware/design constraints explicitly labeled as user constraints rather than conclusions. A project-only import has been performed locally into `workspace/studio-pilot01`, project ID `72918e68-7b9e-5fb9-b74d-a01200000001`. It created **no research run**, made no network request and left existing operator settings unchanged. This ignored local workspace is not a Git artifact; the command below reproduces it on another machine.

## Verification and small fixes

Baseline: 206 offline backend tests and both original browser workflows passed. Pilot preparation reproduced missing per-iteration novelty reviews, missing role routes in preflight, absent ordinary fallback reasons, and a missing standalone cost export. Changes are limited to these requirements, a small six-service status table, safe unconfigured model defaults, role-override editing, and an offline project/settings import command. Studio layout and provider architecture are preserved.

The opt-in novelty review checkpoints persist the current stage and resume after named approval without regenerating reviewed candidates. Interrupted review checkpoints restore PAUSED status. Existing Practice behavior keeps its seven reviews; an additional full synthetic Studio run exercised **ten human reviews, all 20 agent classes, no paid provider and SRL-0**. Rejected or exhausted novelty remains REJECT/UNRESOLVED; canonical Gate 2 is not bypassed. Synthetic advisory experiment/paper drafts remain separate.

Validation commands, from `research_council` unless otherwise stated:

```powershell
.venv\Scripts\python.exe -m pytest -q -m 'not live'
.venv\Scripts\python.exe -m ruff check src tests
.venv\Scripts\python.exe -m mypy src
# From studio/frontend:
npm run build
npm run lint
npm test
npm run e2e
```

Final verification results are recorded in `docs/audits/pilot01-offline.json`; browser results are in `docs/audits/pilot01-playwright.json`. Browser checks cover startup, Practice, provider settings, six-service readiness, role-route editing, preflight/confirmation display, Cost, named reviews, pause/resume/cancel, localization and export. Outbound Python HTTP is blocked in the browser test server; browser external requests are also blocked. Offline provider tests use mocks/fakes. Two live tests remain deselected.

The six-service panel lists OpenAI, Anthropic, Google, Crossref, OpenAlex and arXiv, distinguishing configuration, credential presence and access testing. Nothing marks access successful from a key alone. Preflight shows providers, exact configured models, profile/role routes, Anthropic-blocked roles and their explicit alternatives, sources, budget/caps, approval status and per-revision reviews before the **START REAL RESEARCH** confirmation. No secret values are returned.

Agents/operational summaries expose role, task, provider, model, papers, evidence counts, tokens, latency, estimated cost, retries and fallback reasons. Workflow/Reviews exposes gate status. No hidden chain-of-thought is displayed.

The export contract is tested, including SHA-256 hashes for every ZIP member except the manifest itself:

| Requested content | Export file |
| --- | --- |
| Research plan | `research_plan.json` |
| Paper matrix | `literature_matrix.csv`, `literature_matrix.json` |
| Evidence / claims | `evidence.jsonl`, `claims.jsonl` |
| Gaps / novelty candidates | `research_gaps.md`, `novelty_candidates.md` |
| Prior art / reviewer reports | `prior_art_report.md`, `reviewer_report.md`, `novelty_decisions.md` |
| Hardware assessment | `hardware_feasibility.md` |
| Experiment plan / paper roadmap | `experiment_plan.md`, `ieee_paper_plan.md` |
| Citation audit / cost report | `citation_audit.csv`, `cost_report.json` |
| Manifest / named decisions | `run_manifest.json`, `studio_human_decisions.json` |

Incomplete or blocked science exports its explicit limitations and empty sections rather than invented findings. See `PILOT01_REVIEW_GUIDE.md` for gate-specific inspection and `PILOT01_SMOKE_TEST_PLAN.md` for the unexecuted minimal smoke plan.

## Exact next operator actions

1. From `research_council`, prepare the project on a fresh machine if needed:

   ```powershell
   .venv\Scripts\research-council.exe studio prepare-pilot --workspace workspace/studio-pilot01 --project config/pilot01.project.yaml
   Copy-Item -LiteralPath config/pilot01.example.yaml -Destination config/pilot01.operator.yaml
   ```

   Copy only when the operator file does not already exist. Re-import preserves an existing project's edits. The operator YAML is gitignored.
2. Set local `OPENAI_MODEL_ID`, `ANTHROPIC_MODEL_ID`, `GOOGLE_MODEL_ID` to IDs verified in the relevant accounts. Set the three `*_API_KEY` variables locally; never paste keys into configuration/UI. Edit the three anchors' actual current token prices and dates. Check model endpoint/token/structured-output/timeout support and current scholarly-source account requirements. No paid access verification has been performed.
3. Run the configuration-only preflight command in the smoke plan. If ready, apply the validated routing without creating or starting a run:

   ```powershell
   .venv\Scripts\research-council.exe studio prepare-pilot --workspace workspace/studio-pilot01 --project config/pilot01.project.yaml --config config/pilot01.operator.yaml
   .venv\Scripts\research-council.exe studio --workspace workspace/studio-pilot01
   ```

   The locally built frontend is ready. On a fresh clone, run `npm ci` and `npm run build` from `studio/frontend` first. Open `http://127.0.0.1:8765`. Review Providers & models, all explicit role fallbacks, source selection, caps and readiness; model access remains NOT_TESTED.
4. Review the smoke plan and authorize it separately if desired. **Stop before its paid command until authorized.** Inspect protocol/usage/latency/cost evidence; do not infer scientific readiness from a pass. No smoke is executed as part of this delivery.
5. Only after the operator authorizes the scientific pilot, open the prepared real project, inspect the complete preflight and press **START REAL RESEARCH**. Run creation pins the reviewed configuration; starting/resuming performs the work. Review the plan, core papers, gaps, initial candidate, each revision, novelty acceptance, experiment plan and final readiness using the guide. There is no automatic approval.
6. Watch Cost and fallback/error records; pause or reject when evidence, scope or budget is inadequate. Export the final or partial results and retain the manifest. Treat measured scientific evidence and explicit scientific attestations separately from configuration and workflow completion. SRL stays 0 throughout this preparation.

Delivery branch: **research-council-studio**. The final response supplies the pushed commit SHA and verifies it against local HEAD; this file avoids a self-referential commit hash.
