# Live deployment preflight handoff

LIVE_DEPLOYMENT_READY (operational tooling)

LIVE_BENCHMARK_NOT_EXECUTED

PAID_MODEL_CALLS_MADE = 0

LIVE_BENCHMARK_EXECUTED = false

SCIENTIFIC_READINESS_LEVEL = SRL-0

Base: 4135a6436fab66e540fd904d3a87b19a0faee0e0 on phase-11-live-validation.
No Phase 12 or architecture redesign was performed. Final pushed SHA is verified separately
after committing this handoff. Verified seeds, scientific readiness and all existing gates
were retained. Public documentation was read, but no real provider smoke, scholarly health
check or scientific benchmark was executed. Mock HTTP requests in tests are not paid calls.

## Audit and verification

Audited both live examples, .env.example, ModelRouter, provider HTTP adapters, six-field
budget admission/persistence, scientific consent, validate-science, pinned resume and workflow
approval points. Runtime already supports OpenAI/Anthropic/Gemini together, ReviewerTwo
provider avoidance and explicit same-provider fallback. NoveltyJudge already accepts an
independent role override. Source metadata failures remain distinct from prior-art absence.

Added configuration-only preflight that detects missing explicit profiles before Settings
fills defaults. Added enabled/disabled routes and optional per-route pricing review dates;
disabled routes do not trigger model substitution, key/price requirements or inference.
All effective task/role routes must still be complete. Existing single-provider fallback
remains allowed with warnings. Missing prices block cost reservation; review dates warn.

Reproduced a Gemini accounting defect with a mocked response: eight candidate tokens and
twelve reasoning tokens previously reported eight output tokens. The corrected estimate
reports twenty, consistent with separately reported reasoning-token billing. No real request
was needed. Existing provider endpoints and scientific workflow were not redesigned.

Verification: Ruff format --check, Ruff check and mypy pass (103 source files). **179 offline
tests pass, zero fail, two live tests deselected**: all previous 159 plus 20 new cases. Tests
cover placeholder/key/route/price/budget errors, single-provider diversity warnings, disabled
routes, safe no-client preflight, both consent flags, three-provider mocked smoke with no
retries even on 429, pre-request budget denial, and Gemini reasoning-token accounting.

An installed wheel passes pip check and exposes the preflight CLI. With keys removed from
the child environment, the untouched operator example correctly returns exit 1 and names
required inputs without exposing values. Installed-wheel scientific preparation produces
36 hash-verified exports with zero model executions and SRL-0. All 17 PowerShell blocks in
the setup/runbook parse without executing them. [Machine evidence](audits/live-deployment-preflight-results.json)
and [JUnit](audits/live-preflight-offline.xml) record these results. Phase 11's earlier
159-test artifacts remain historical and unchanged.

## Operator handoff and limits

Copy `config/phase11.operator.example.yaml` to `config/phase11.operator.yaml`. Supply
account-valid model IDs, current prices/review dates and enabled provider keys. Preflight
checks configuration/presence, not model availability or authenticated access. Those inputs
are intentionally unresolved here. Optional IEEE has no wired authenticated backend and is
excluded from the recommended configuration; selecting it produces an explicit blocker.

The [18-step runbook](FIRST_LIVE_RUN.md) provides every command, including separate explicit
paid consent. The [PowerShell guide](LIVE_PROVIDER_SETUP.md) provides session and encrypted
persistent credential options. The [review checklist](LIVE_RUN_REVIEW_CHECKLIST.md) covers
scientific inspection and costs. No software blocker remains for the recommended template;
operator values and real service access still require verification.

Recommended scientific model estimate cap: USD 5, 80 attempts, 1000 scholarly HTTP attempts,
12 CORE papers, 12 deep reads and three novelty iterations. Optional provider smoke is
separate: at most three requests, one per enabled provider, 128 output tokens, no retries or
scholarly requests, maximum USD 0.25 aggregate estimate. These caps use entered prices;
provider invoices/source-service charges remain separate and unqueried. Nothing advances SRL
automatically or converts protocol success into scientific validation.

## Files created

- config/phase11.operator.example.yaml
- docs/LIVE_PROVIDER_SETUP.md
- docs/FIRST_LIVE_RUN.md
- docs/LIVE_RUN_REVIEW_CHECKLIST.md
- docs/LIVE_DEPLOYMENT_PREFLIGHT.md
- docs/audits/live-deployment-preflight-results.json
- docs/audits/live-preflight-offline.xml
- src/research_council/cli/providers.py
- src/research_council/validation/preflight.py
- src/research_council/validation/provider_smoke.py
- tests/test_provider_preflight.py

## Files modified

- .env.example
- .gitignore
- README.md
- docs/PHASE_11_VALIDATION.md
- docs/phases/phase-11.md
- docs/provider-routing.md
- src/research_council/cli/__init__.py
- src/research_council/core/config.py
- src/research_council/core/routing/router.py
- src/research_council/core/runtime.py
- src/research_council/providers/http.py
