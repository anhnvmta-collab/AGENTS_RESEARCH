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
