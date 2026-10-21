# Deterministic quality gates

Gate 1 evaluates each paper independently: identity, title/authors/year, deduplication and
retrieved source. A DOI is useful but not mandatory. Rejected papers cannot enter evidence
analysis. An empty accepted corpus cannot pass. An abstract can support abstract-level evidence
only. Missing quartiles are unknown, never inferred from venue reputation.

Gate 2 requires completed prior-art and independent reviewer reports for the exact candidate
revision, a SURVIVE decision, minimum grounded evidence, and no unresolved high-severity
contradiction. Completion cannot be asserted by an LLM. Novelty survival is scoped to the logged
search, never a proof of universal novelty. After three unresolved iterations status is UNRESOLVED.

Gate 3 requires a citation audit for every primary source, VERIFIED primary claims with validated
support, at least one baseline and metric, an experiment plan and stated limitations. Unsupported,
contradicted, hypothesis, fixture, missing or retracted primary evidence fails publication readiness.
Gate results persist the checked IDs and explicit failure reasons. The final report shows all gates
and does not present a limited run as publication ready.

Quotation matching establishes source grounding, not semantic entailment. V1's automatic citation
audit can be PARTIALLY_VERIFIED; human verification is needed to promote scientific entailment.
No model can grant itself a trusted reviewer or metadata verification status.

## Re-audit refinements
Gate 1 requires verified metadata or explicitly supplied local sidecar identity for real sources;
fixtures may pass only the operational source gate and remain excluded from scientific verification.
Gate 2 verifies successful operational query attempts and actual successful model executions for
all three adversarial roles. Prior-art overlap matrices require source-specific evidence. Current
revision survival is recalculated before experiment planning, publication assessment and export.
Cached booleans do not override missing/changed evidence. Search saturation terminates revisions
as UNRESOLVED and retains reasons; failed connectors never count as saturated coverage.
Gate 3 additionally requires ablations, hypothesis, statistics, failure cases, acceptance criteria,
reproducibility and experiment/claim links in the paper outline. Every surviving novelty contribution
must reference a verified primary novelty claim; a proposal hypothesis cannot pass. Historical fatal
citation conflicts remain blocking even after a new positive human audit. Resolved evidence conflicts
retain their opposing quotations and require separate scientific attestation. Re-audit demotes newly
contradicted claims and removes them from synthesized conclusions.
