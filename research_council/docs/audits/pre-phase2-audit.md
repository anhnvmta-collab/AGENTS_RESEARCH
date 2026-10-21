# Independent engineering audit before remediation

Date: 2026-10-21 (Asia/Bangkok). Scope: the actual working tree of
`anhnvmta-collab/AGENTS_RESEARCH`, including inherited uncommitted implementation.
Git baseline: `e6418f2` (`first commit`); remote/main and local main point there. The working
tree already contains substantial phases 3–10 beyond that commit. Existing changes are retained.
No implementation was rewritten before this review.

## Method and baseline evidence

Inspected package/dependency/configuration files; all schema and persistence boundaries;
the Alembic initial revision; orchestration, checkpoint/lease, routing/provider, agent/context,
discovery/reading/audit, gates, hardware, export/evaluation paths; role prompts, ADRs and tests.
Ran the existing formatter, lint, mypy and pytest: all passed; **58 tests passed**, mypy checked
68 source files. Passing existing tests does not establish the newly requested acceptance criteria.
The supplied GitHub repository identity/default branch was confirmed through the GitHub connector.

Severity: CRITICAL risks unsupported scientific verification or breaks the core provenance chain;
HIGH undermines isolation, integrity or required gates; MEDIUM affects architecture/completeness;
LOW is maintainability; GOOD records verified strengths. Required means remediate before extending.

## Findings

### C01 — CRITICAL: persistence validates only the beginning of the scientific chain

**Problem:** Checkpoint projection validates paper/evidence/claim edges, then writes gaps, novelty,
reviews and matches as independent JSON payloads. There is no complete graph validator. Decisions,
experiment-to-candidate and paper-plan-to-experiment/claim edges are not represented relationally.
Duplicate IDs within one state can also be silently collapsed by dict construction.

**Why it matters:** Dangling or wrong-revision artifacts can be persisted as if traceable.
**Affected files:** `storage/projector.py`, `repositories/store.py`, `schemas/models.py`,
`agents/contracts.py`, `core/orchestration/state.py`.
**Correction:** Validate the entire typed graph at every checkpoint; use revision-aware identities;
persist run-specific graph snapshots and FK-backed links. Add negative tests for every edge.
**Required before continuing:** yes.

### C02 — CRITICAL: human attestation can ignore an existing contradictory citation audit

**Problem:** Attestation creates a new VERIFIED audit without examining earlier CONTRADICTED
identity/location audits or a structured conflict/resolution record.
**Why it matters:** A human confidence checkbox can hide a known fatal conflict rather than resolve it.
**Affected files:** `core/human_review.py`, `core/gates/__init__.py`, `tools/audit.py`.
**Correction:** Preserve conflicts explicitly; prohibit attestation while high-severity conflicts
remain open/unresolved; require documented resolution without deleting contradicting evidence.
**Required before continuing:** yes.

### H01 — HIGH: cross-run and cross-revision primary-key collisions

**Problem:** Domain tables key by artifact UUID alone and `_put` updates `run_id` and payload.
Synthetic reusable evidence IDs and repeated candidate revisions overwrite earlier rows.
**Why it matters:** Run-scoped queries can lose another run's records and candidate history.
**Affected files:** `storage/database.py`, `storage/projector.py`, `repositories/store.py`, migration 0001.
**Correction:** Add run/revision snapshot identity and edges with a new migration; preserve historical
snapshots and keep library identity separate from run membership. Do not edit migration 0001.
**Required before continuing:** yes.

### H02 — HIGH: Gate 2 trusts completion flags and selection ignores revision

**Problem:** The gate accepts `complete=True` plus query strings without successful search attempts.
`experiments()` selects candidates by candidate UUID, potentially including rejected older revisions.
**Why it matters:** An unevaluated candidate revision can reach experiment/paper planning.
**Affected files:** `core/gates/__init__.py`, `core/orchestration/pipeline.py`, `novelty.py`.
**Correction:** Require operational search history, exact candidate revision and grounded sources;
derive current survivors from matching reports/decisions, not cached gate flags alone.
**Required before continuing:** yes.

### H03 — HIGH: Gate 3 omits newly mandatory experimental requirements

**Problem:** Baselines, metrics and procedures suffice; ablations, hypothesis, failure cases,
acceptance criteria and reproducibility are optional/unvalidated, and there is no roadmap linkage.
**Why it matters:** Publication readiness can pass without the requested experiment proof plan.
**Affected files:** `schemas/models.py`, `agents/experiment_designer.py`, `agents/paper_architect.py`,
`agents/contracts.py`, `core/gates/__init__.py`.
**Correction:** Add explicit typed experiment/roadmap links and deterministic requirements,
including ablation. Missing information fails closed; no invented measurements.
**Required before continuing:** yes.

### H04 — HIGH: CitationAuditor does not validate individual claim support

**Problem:** It checks excerpts grouped by paper but not every claim's referenced evidence IDs,
support-paper agreement, missing support or explicit contradiction.
**Why it matters:** Correct metadata can accompany an unsupported claim without being flagged.
**Affected files:** `tools/audit.py`.
**Correction:** Audit each claim-to-evidence edge; report structural contradictions/unknown support
separately from semantic entailment; preserve independent unknown quartile/retraction status.
**Required before continuing:** yes.

### H05 — HIGH: source-integrity metadata confidence is not enforced

**Problem:** A title, arbitrary author/year and URL can pass Gate 1 without a recorded identity check.
**Why it matters:** LLM/local metadata guesses may enter analysis as accepted source identities.
**Affected files:** `core/gates/__init__.py`, `schemas/models.py`, `tools/local.py`.
**Correction:** Distinguish resolved metadata, explicitly supplied local identity, synthetic fixtures
and unknown identity; scope test fixtures and reject unknown live identity.
**Required before continuing:** yes.

### H06 — HIGH: schema trust and UTC invariants are incompletely enforced

**Problem:** Naive/non-UTC timestamps are accepted; mutated/model_copy objects can bypass model
validators when persistence serializes them directly. Scientific floats can accept infinity in
some unconstrained fields.
**Why it matters:** Verification invariants can differ between construction and persistence.
**Affected files:** `schemas/models.py`, `repositories/store.py`, `storage/projector.py`.
**Correction:** Normalize aware timestamps to UTC, reject naive timestamps and non-finite numbers;
revalidate serialized artifacts at persistence boundaries.
**Required before continuing:** yes.

### H07 — HIGH: contradiction state is missing and reviewer can self-resolve severe objections

**Problem:** Claims list contradictory IDs, but there is no EvidenceConflict lifecycle. A reviewer
can emit `resolved=True` for its own high-severity objection.
**Why it matters:** Conflicts may disappear through regeneration or model assertions.
**Affected files:** `schemas/models.py`, `core/orchestration/state.py`, `agents/reviewer_two.py`, gates.
**Correction:** Persist conflicts and resolution provenance; do not trust model-provided resolution.
**Required before continuing:** yes.

### M01 — MEDIUM: incomplete repository ports

**Problem:** GapRepository, NoveltyRepository and ExecutionRepository are absent; ResearchRepository
does not expose the requested RunRepository name. Agents depend on the concrete router's repository.
**Why it matters:** Replacing infrastructure requires avoidable changes.
**Affected files:** `repositories/store.py`, `agents/base.py`, routing/orchestration constructors.
**Correction:** Provide operational typed ports/adapters and move persistence access behind them.
**Required before continuing:** yes for domain/storage contracts; broader dependency inversion is incremental.

### M02 — MEDIUM: configuration and reviewer independence are incomplete

**Problem:** `${MODEL_ENV}` placeholders are not expanded; partial profile dictionaries discard
defaults; no role overrides or alternate-provider preference exist for ReviewerTwo.
**Why it matters:** Supplied configuration examples are not fully supported and model bias isolation
cannot be assessed.
**Affected files:** `core/config.py`, `core/routing/router.py`, agent/pipeline routing.
**Correction:** Safe model-variable expansion, validated route defaults/role overrides, recorded actual
provider provenance and alternate-provider preference without passing generator reasoning.
**Required before continuing:** yes before provider phase acceptance.

### M03 — MEDIUM: scientific retrieval is truncation rather than ranked evidence retrieval

**Problem:** DeepReader receives a leading text/page window; there are no located chunks, ranking
or query-aware retrieval. Large contexts otherwise fail and degrade to empty outputs.
**Why it matters:** Important late sections can be missed systematically.
**Affected files:** `agents/deep_reader.py`, `agents/contracts.py`, context and discovery/evidence layers.
**Correction:** Add deterministic located chunking and ranked retrieval behind owned interfaces.
**Required before continuing:** before phase 6 acceptance.

### M04 — MEDIUM: search, hardware and evaluation requirements are incomplete

**Problem:** No SearchSaturationDetector, TargetedSearchRequest, explicit estimate/measurement
classification, configurable triage weights, full-text/IEEE ports, overlap matrix or benchmark
readiness status. Human scoring omits research usefulness/hardware realism/publication readiness;
evaluation omits aggregate token usage.
**Why it matters:** Current phase-completion documentation overstates the expanded acceptance scope.
**Affected files:** schemas/configuration, discovery/novelty/hardware/evaluation, benchmark example.
**Correction:** Implement/test these bounded capabilities; label the unexecuted real benchmark
`BENCHMARK_READY_BUT_NOT_EXECUTED`.
**Required before continuing:** respective phase acceptance.

### M05 — MEDIUM: checkpoint version/lease failure handling is incomplete

**Problem:** The engine checks a hard-coded workflow version but not state.schema_version. Lease
loss is checked before a stage, leaving a window for a stale worker to commit its result.
**Why it matters:** An incompatible or stale checkpoint can replace valid state.
**Affected files:** `core/orchestration/engine.py`, repository checkpoint API.
**Correction:** Validate state versions and fence checkpoint writes by lease ownership inside the
transaction. Keep migration/recovery explicit.
**Required before continuing:** yes before workflow acceptance.

### M06 — MEDIUM: observability/output/CI gaps

**Problem:** TraceEvent lacks provider/model/tokens/retry/start/end; requested standalone claims,
queries, core papers, reviewer and decision exports and `audit RUN_ID` command are absent. CI is
under `research_council/.github`, which GitHub does not discover at repository root.
**Why it matters:** Operators cannot use all required audit outputs or the intended remote checks.
**Affected files:** tracing, CLI/exporters, nested CI workflow.
**Correction:** Complete structured traces and the 19-file output set under `outputs/{run_id}`;
add audit command; place CI at root with explicit project working directory.
**Required before continuing:** respective phase acceptance.

### M07 — MEDIUM: incomplete regression proof

**Problem:** No migration downgrade, cross-run/revision integrity, injected-document override,
clean environment dependency install or late-section retrieval test exists. Earlier installed-wheel
smoke reused the development environment's dependencies.
**Why it matters:** Packaging and security claims need stronger proof.
**Affected files:** tests, check/build scripts, validation documentation.
**Correction:** Add meaningful regressions and clean-venv acceptance runner with persisted results.
**Required before continuing:** phase 10 acceptance.

### L01 — LOW: docs and checks need revision for the new scope

**Problem:** Old reports are brief and omit changed files, debt and next dependencies. CI actions
are unpinned by commit. The initial architecture's planned tree differs from packaged migrations.
**Why it matters:** Maintenance/release evidence is harder to assess.
**Affected files:** docs/phases, architecture/ADRs, workflow file.
**Correction:** Preserve original history; add current self-review sections, new ADRs and truthful
final audit. Pin CI action commits after verification where practical.
**Required before continuing:** no for initial code remediation; yes for final documentation.

## GOOD — verified strengths to preserve

* Own deterministic stage engine, bounded novelty loop and explicit operational failure records.
* Typed role modules and external prompts; no provider SDK imports in agents.
* Restricted reviewer input excludes generator persuasion; tools use allowlists and structured data.
* Fake/offline/live are explicit; synthetic sources cannot pass the existing publication gate.
* Exact short quotation grounding, DOI normalization and conservative conflicting-DOI deduplication.
* Alembic revision 0001, atomic state/artifact writes, database FK/WAL configuration and local-path checks.
* Bounded provider retry/fallback and pre-request persisted usage/budget reservations.
* CSV injection escaping, unknown metrics reported as null, manifest hashes and offline test fixtures.

## Remediation order

1. Preserve the inherited working tree and record this audit.
2. Repair C01–C02/H01–H07 plus architectural M01/M05; add failing-then-passing regressions.
3. Run format/lint/mypy/tests and record `pre-phase2-remediation.md`.
4. Complete routing/context/workflow/discovery/evidence/novelty/hardware/CLI/evaluation additions,
   reviewing and checking after each coherent phase.
5. Run clean-install acceptance and produce `FINAL_IMPLEMENTATION_AUDIT.md` with actual results.
