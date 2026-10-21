# Phase 11: live scientific validation and research-quality benchmark

Base: b992b9fbb6125cd1ec177b49b3a4e604291386bb, engineering-audit-v1.
Initial inspection covered FINAL_IMPLEMENTATION_AUDIT, architecture, workflow, routing, gates,
security, human review and the implementation boundaries. Baseline checks: formatting/lint/mypy
passed (81 source files); 113 tests passed. No architecture rewrite is planned. New typed
measurement/reporting extensions retain all V1 gates. No paid API operation is authorized by
credential presence; preparation and explicit paid execution are separate.

## 11A benchmark framework
Added packaged benchmark configuration, ten persisted ResearchQuestions, fourteen complementary
perspectives, stable query-family IDs and provenance, coverage vocabularies and a weak novelty
control. Planner/perspective/query roles extend their existing contracts only when the benchmark
is explicitly configured. Seed list remains empty until primary-source curation in 11I. No
scientific conclusion or readiness advancement is produced by configuration.
11A checks: formatter/lint/mypy passed (83 source files); 115 offline tests passed, 0 failed. Existing 113 regressions remain passing.

## 11B identity, coverage and shortlist
Added typed metadata-only PaperIdentityAudit, explicit DOI/title/year/author/venue conflicts,
pre-dedup observation retention and a second identity check before scientific CORE selection.
Diversity selection reserves older, recent low/unknown-citation and implementation papers where
slots permit. Seed recall, lexical method/concept coverage and explicitly labelled citation-edge
recall have denominators and null for unmeasured cases. No scalar confidence clears a conflict.
Checks: formatter/lint/mypy passed (86 source files); 122 offline tests passed, 0 failed.

## 11C scientific quality metrics
Added grounded/location metrics, independently labelled entailment/support/contradiction metrics,
reproducible real-evidence sampling and per-number hardware provenance. Missing human labels
remain null. Source-reported numbers and proposed estimates cannot become benchmark measurements.
Extended typed gap/candidate fields and extraction/math/hardware prompts without relaxing V1 gates.
Checks: formatter/lint/mypy passed (87 source files); 125 offline tests passed, 0 failed.

## 11D model disagreement and task comparison
Added execution-validated model positions, preserved opposing positions and explicit named-human
resolution. Novelty reviewer/judge disagreements are projected from actual reports/executions,
not inferred from generator proposals. High unresolved disagreement additionally blocks publication.
Model comparison reports all configured task profiles with nullable independent human scores and
actual billed cost; no universal model ranking is inferred. Checks: formatter/lint/mypy passed
(89 source files); 127 offline tests passed, 0 failed.

## 11E human review package and search-round measurements
Added all eight expert-review artifacts, a seeded random evidence sample with blank human
judgments, component/aggregate/core-selection records, closest-prior-art matrix, hardware
assumptions and model comparison CSVs. Search rounds record query/result/new-core counts and
explicit lexical method-family/citation-seed proxies. No coverage or measured-data claim is
inferred from an empty package. Checks: formatter/lint/mypy passed (90 source files);
128 offline tests passed, 0 failed.

## 11F scientific readiness levels
Added SRL-0 through SRL-9, explicit prerequisite facts, sequential evidence history, named
operator review and artifact/reference verification. Creating a benchmark does not advance SRL.
Human-sampling, gap review, independent review models and experimental/replication facts are
required at their respective levels. Checks: formatter/lint/mypy passed (91 source files);
130 offline tests passed, 0 failed.

## 11G live cost and operation controls
Added persistent LiveResearchBudget admission for conservative model-cost reservations, each
model attempt, each scholarly HTTP attempt (including metadata/retries), CORE selection, deep
reads and novelty iterations. Lease-fenced budget artifacts survive resume; stage wrappers retain
partial successful results before BUDGET_EXHAUSTED. Scientific live creation/runtime requires a
stored explicit paid-API confirmation. Provider billing remains external; estimates and unknown
actual billed costs are distinguished. Checks: formatter/lint/mypy passed (92 source files);
136 offline tests passed, 0 failed, including concurrent admission and partial-stage recovery.

## 11H live test separation and secret controls
Default pytest and CI explicitly exclude the live marker. Selecting live tests without both
--run-live and --confirm-paid-apis fails during collection before network access. Two real-service
smoke tests are opt-in only; operator configuration is required for the paid route. Source/config
credential-literal scanning and .env-ignore regressions pass. Checks: formatter/lint/mypy passed
(92 source files); 138 offline tests passed, 0 failed; 2 live tests deselected, not executed.

## 11I benchmark preparation, real controls and reproducibility
Curated three nonexhaustive seed identities from primary arXiv/publisher pages, with provenance,
version/date caveats and short known-answer excerpts. Curation is not counted as live benchmark
execution or a retrieved finding. Added exact-title rejection, missing-prior-art coverage control,
a weak unchanged-OMP control with raw model verdict separate from deterministic policy, four-risk
candidate contracts and revision explanations. Added directed citation observations, an observed
(not forced) taxonomy, prompt/context/evidence/source hashes and Git/config provenance.
validate-science prepares all reports and expert artifacts with no Runtime/provider instantiation
unless both --live and --confirm-paid-apis are present. SRL remains zero until explicit reviewed
advancement. Partial/failed/paused live execution can be resumed and reviewed without inventing
results. Checks: formatter/lint/mypy passed (99 source files); 151 offline tests passed, 0 failed;
2 live tests deselected. Primary curation sources are linked in the benchmark README/seed file.
