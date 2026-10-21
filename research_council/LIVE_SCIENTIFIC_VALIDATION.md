# LIVE SCIENTIFIC VALIDATION

## 1 Executive Summary

PHASE_11_IMPLEMENTED

LIVE_VALIDATION_NOT_YET_EXECUTED

Run d5146df9-2786-4176-9c3a-280dffbfc505: CREATED. Recorded readiness remains SRL-0. Software test success and curated references are not scientific validation.

## 2 Benchmark Configuration

```json
{
  "identifier": "CS_FHSS_DOA_FPGA",
  "question": {
    "topic": "Compressed Sensing for Real-Time Detection, Parameter Estimation and DOA of FHSS UAV Signals on Coherent SDR/FPGA Platforms",
    "constraints": [
      "FHSS approximately 500–1000 hops/s",
      "Coherent multi-channel receiver",
      "Real-time processing",
      "SDR/FPGA implementation",
      "FPGA / RFSoC / Zynq-class platform",
      "Cross-channel coherence and sparse recovery",
      "Compressed Sensing",
      "DOA estimation"
    ],
    "audit_claim": null
  },
  "subquestions": {
    "RQ1": "topic='What compressed sensing approaches exist for wideband or FHSS signal detection?' constraints=[] audit_claim=None",
    "RQ2": "topic='Which sparse recovery algorithms have demonstrated sufficient complexity for real-time implementation?' constraints=[] audit_claim=None",
    "RQ3": "topic='Which methods estimate carrier frequency, hop timing, duration, sequence and band occupancy jointly or sequentially?' constraints=[] audit_claim=None",
    "RQ4": "topic='Which methods combine sparse sensing with direction-of-arrival estimation?' constraints=[] audit_claim=None",
    "RQ5": "topic='Which approaches support coherent multi-channel receivers?' constraints=[] audit_claim=None",
    "RQ6": "topic='Which approaches have FPGA, SDR, GPU or RFSoC implementations?' constraints=[] audit_claim=None",
    "RQ7": "topic='What are the primary computational and memory bottlenecks?' constraints=[] audit_claim=None",
    "RQ8": "topic='Which prior work specifically targets UAV communication signals?' constraints=[] audit_claim=None",
    "RQ9": "topic='Which work operates near 500-1000 hops/s and under what assumptions?' constraints=[] audit_claim=None",
    "RQ10": "topic='Which scoped scientific gaps remain after the closest prior art is considered?' constraints=[] audit_claim=None"
  },
  "constraints_are_inputs": true,
  "budget": {
    "max_total_cost": 5.0,
    "max_model_calls": 80,
    "max_search_calls": 1000,
    "max_core_papers": 12,
    "max_deep_reads": 12,
    "max_novelty_iterations": 3
  }
}
```

## 3 Providers Used

```json
[]
```

Empty means no real provider was exercised. Credential availability is not execution.

## 4 Search Sources

```json
{
  "configured": [],
  "attempts": [],
  "failures": []
}
```

## 5 Search Coverage

```json
{
  "measurement_status": "NOT_EXECUTED",
  "seed_paper_recall": {
    "numerator": 0,
    "denominator": 0
  },
  "method_family_recall": {
    "numerator": 0,
    "denominator": 0
  },
  "concept_coverage": {
    "numerator": 0,
    "denominator": 0
  },
  "citation_chain_recovery": {
    "numerator": 0,
    "denominator": 0
  },
  "matched_seeds": [],
  "observed_method_families": [],
  "observed_concepts": [],
  "limitation": "Nonexhaustive seed set; lexical family/concept proxies within observed metadata/evidence, not universal completeness."
}
```

See search_rounds.csv. Method families are lexical proxies; citation clusters are explored-seed proxies. Any saturation is under the configured search strategy, never universal completeness.

## 6 Seed Paper Recall

Curated nonexhaustive seeds available: 3. Measured recall: UNMEASURED. Seeds are not automatically counted as discovered papers.

## 7 Literature Taxonomy

```json
{}
```

Only observed metadata/evidence contributes; starter families are not forced into empty branches.

## 8 Core Papers

```json
[]
```

See human_review/top_core_papers.csv for identity status, component scores and diversity reasons.

## 9 Evidence Quality

```json
{
  "evidence_location_rate": {
    "numerator": 0,
    "denominator": 0,
    "value": null
  },
  "evidence_grounding_rate": {
    "numerator": 0,
    "denominator": 0,
    "value": null
  },
  "evidence_entailment_accuracy": {
    "numerator": 0,
    "denominator": 0,
    "value": null
  },
  "human_location_accuracy": {
    "numerator": 0,
    "denominator": 0,
    "value": null
  },
  "evidence_contradiction_detection_rate": {
    "numerator": 0,
    "denominator": 0,
    "value": null
  },
  "unsupported_claim_rate": {
    "numerator": 0,
    "denominator": 0,
    "value": null
  },
  "structurally_unsupported_claim_rate": {
    "numerator": 0,
    "denominator": 0,
    "value": null
  }
}
```

```json
{
  "evidence_location_rate": "Traceable page/section/abstract/offset location availability; not human correctness.",
  "evidence_grounding_rate": "Quote found at the recorded source location, not semantic entailment.",
  "evidence_entailment_accuracy": "Positive independently completed human entailment judgments / completed judgments.",
  "human_location_accuracy": "Correct human-reviewed locations / completed location judgments.",
  "evidence_contradiction_detection_rate": "Detected gold-positive contradictory claims / human-labelled contradictory claims.",
  "unsupported_claim_rate": "Human-labelled unsupported primary claims / independently labelled primary claims.",
  "structurally_unsupported_claim_rate": "Primary claim support missing from actual evidence / primary non-hypothesis claims."
}
```

## 10 Claim Quality

```json
[]
```

Human entailment/support judgments remain unmeasured until independently supplied. Hypotheses are not verified claims.

## 11 Contradictions

```json
[]
```

Opposing evidence and historical identity conflicts remain visible.

## 12 Research Gaps

```json
[]
```

Absence claims apply only within recorded search coverage. Expert gap judgments are required.

## 13 Novelty Candidates

```json
[]
```

Prepared weak control: Apply the existing OMP algorithm to UAV FHSS data without a mathematical or implementation contribution.

A prepared control is NOT_EXECUTED until the attack/review workflow actually runs.

## 14 Prior-Art Attacks

```json
[]
```

See closest_prior_art_matrix.csv. Missing/failing search means INSUFFICIENT_SEARCH_COVERAGE, not novelty.

## 15 ReviewerTwo Findings

```json
[]
```

Provider independence and same-provider fallback are recorded in provider_independence.csv. Reviewer inputs exclude generator private reasoning.

## 16 Novelty Decisions

```json
[]
```

Raw model verdicts and deterministic policy overrides are separate; policy rejection is not credited as a model's successful scientific judgment.

## 17 Hardware Feasibility

```json
[]
```

See hardware_assumptions.csv. SOURCE_REPORTED, DERIVED and ESTIMATED are distinct. No new benchmark measurements are manufactured.

## 18 Experiment Plan

```json
[]
```

These are proposed protocols, not executed experiments. The linked IEEE roadmap is in ieee_paper_plan.md.

## 19 Model Comparison

See model_benchmark.csv for attempts, failures, retries, validity, latency, reported tokens, estimated cost and optional human scores. Unexecuted tasks and absent judgments stay blank. No model is universally best from one run.

```json
{
  "model_calls": 0,
  "search_calls": 0,
  "core_papers": 0,
  "deep_reads": 0,
  "novelty_iterations": 0,
  "estimated_cost": 0,
  "reserved_cost": 0,
  "exhausted": false,
  "reasons": []
}
```

## 20 Model Disagreements

```json
[]
```

No opposing position is silently averaged away. High unresolved disagreement requires human review.

## 21 Human Review Requirements

Review human_review/ and human_evidence_review_template.csv. At least 20 real evidence objects are sampled when available, otherwise all available evidence. Human location, entailment and interpretation fields are blank by design. Use independently completed review bundles and explicit SRL evidence; workflow approval is not scientific attestation.

## 22 Known Limitations

This report cannot establish universal coverage, mathematical correctness, actual FPGA performance or publication readiness from metadata/quotes alone. Lexical retrieval may miss terminology; abstracts may omit implementation details. APIs may fail or require credentials. Human identities are trusted local attestations, not authenticated expert certification. Source-reported synthesis is not an RF/FPGA measurement by this benchmark. Native experiment/replication ingestion is not implemented, so CLI readiness cannot claim SRL-8/9.

```json
[
  "LIVE_VALIDATION_NOT_YET_EXECUTED",
  "Curated seeds are not counted as retrieved benchmark findings."
]
```

## 23 Scientific Readiness Decision

SRL-0: Software only. No automatic advancement occurred. Evidence-backed sequential operator review is required.

LIVE_VALIDATION_NOT_YET_EXECUTED

Reproducibility: scientific_reproducibility.json records source/config/prompt/evidence hashes, actual executions, queries, timestamps, source revision and dirty-tree status.
