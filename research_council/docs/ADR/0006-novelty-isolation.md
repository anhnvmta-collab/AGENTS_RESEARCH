# ADR 0006: Adversarial review has a separate input and routing policy

Status: accepted. Hunter and ReviewerTwo receive an allowlist projection: normalized claim,
technical keywords and minimal source evidence, excluding generator arguments/private reasoning.
Generator provider provenance is operational routing metadata, never persuasive model context.
ReviewerTwo prefers a different configured provider when available. Single-provider fallback is
explicitly recorded, not described as provider independence. Logical input isolation remains
mandatory regardless of provider availability. Matching revision and actual completed execution
records are required at the novelty gate; confidence never overrides deterministic checks.
