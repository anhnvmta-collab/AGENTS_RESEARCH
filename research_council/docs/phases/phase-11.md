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
