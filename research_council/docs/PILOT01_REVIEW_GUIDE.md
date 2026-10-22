# Pilot 01 researcher review guide

Prepared for the CS / FHSS UAV / coherent SDR / FPGA / RFSoC topic. This is an operator checklist, not a literature review or a scientific result. Before live research, **SRL = 0**.

## Approval behavior

Use the named review form in **Reviews** at each checkpoint. Read the linked artifacts, enter a reviewer name and a specific comment, and choose Approve, Reject or Revise. Approve authorizes continuation; it does not verify a claim, pass a scientific gate or certify publication readiness. Resume is a separate action. Never approve an unseen novelty revision.

Revise appends the instructions to the research question and restarts dependent stages from the plan; it is not an inline edit of one candidate. Existing costs remain consumed. Export before revision if you need a snapshot of the previous analysis. Changing global provider settings does not change a run's pinned configuration. Reject terminates the run; Pause is cooperative and takes effect at an execution checkpoint.

Pilot configuration enables `research.novelty_review_each_revision`. Each generated batch receives prior-art, ReviewerTwo and judge assessments, then pauses **before another targeted search or revision**. There is one review per iteration, covering every candidate in that batch. A three-iteration run has `novelty_candidate_review_1`, `novelty_revision_review_2` and `novelty_revision_review_3`. Early rejection, saturation, a surviving candidate or exhausted resources may end the loop earlier. Human approval never converts REJECT/UNRESOLVED into SURVIVE or bypasses Gate 2.

## Review checkpoints

| Checkpoint / Studio record | Inspect before continuing |
| --- | --- |
| Research Plan — `after_plan`, then `before_expensive_deep` | In Overview/Workflow inspect the plan, RQ1–RQ10, perspectives and search queries. Define CS, FHSS, DOA, detection vs estimation, hop dwell vs end-to-end latency, and spectrum-angle joint estimation. Keep UAV-specific evidence distinguishable from generic FHSS. Check synonyms, negative controls, date filters and accessible sources. |
| Core Paper Selection — `after_core_selection` | In Papers inspect titles, identities, DOI/source URLs, deduplication, relevance and the reasons for inclusion/exclusion. Balance seminal methods with recent results through the actual search date. Do not infer quality from citations, recency or venue alone. With at most 12 CORE papers, identify uncovered RQs explicitly. |
| Evidence — reviewed with core papers, gaps and every novelty gate | In Evidence follow each claim to paper ID, evidence ID, verbatim excerpt and source location. Check page, section, table/figure or an explicit abstract-only location. Confirm that the accessible text supports the exact scope of the claim. Metadata or an abstract cannot support unobserved implementation details. Inspect contradiction/conflict and identity-audit records. |
| Research Gaps — `after_gaps` | In Gaps check supporting limitations, counterexamples and search scope. Replace “nobody has studied this” with “not found in these sources, queries, dates and accessible texts.” Distinguish an evidence/access gap from an algorithmic, real-time, hardware or experimental gap. |
| Novelty Candidate — `novelty_candidate_review_1` | In Novelty inspect the normalized contribution, linked gap/evidence IDs, closest prior art, overlap, search failures, judge verdict and Gate 2 reasons. A new combination of terms is insufficient. State precisely what differs and which observation could refute it. |
| Every Novelty Revision — `novelty_revision_review_N` | Compare the revision with its predecessor. Check the new evidence, targeted queries/results, attack-triggering prior art and remaining risks. Verify that the strongest objection was answered by evidence or a narrower claim. Stop if the revision merely rephrases the same unsupported novelty claim. |
| Novelty acceptance — `before_accepting_novelty` | Confirm that the latest candidate and its attacks match by ID/revision and satisfy canonical Gate 2. Inspect the **strongest ReviewerTwo objection**, rather than just its overall verdict. Check different-provider review and the independent judge route; read any fallback reason. An unresolved high-severity objection must remain visible. |
| Hardware — inspected before accepting novelty and experiment design | In Hardware separate **sourced** author-reported results, **derived** calculations with units/assumptions, and **estimated** proposals. Check sample rate/bandwidth, channels, array calibration/coherence, SNR, hop timing, latency vs throughput, memory/bus transfers, FPGA resources, power and clock rate. Identify measurement platform and whether results were simulation, software, FPGA or RFSoC measurements. |
| Experiment Plan — `after_experiment_plan` | In Experiments require a falsifiable hypothesis, strong matched baselines, metrics, ablations, statistical plan, reproducible seeds/data/configuration and acceptance/failure criteria. Compare detection/Pd/Pfa, parameter error, DOA error/resolution, end-to-end latency, sustained hop throughput and hardware resource costs under matched conditions. Use simulation → SDR → FPGA only where justified. If Gate 2 blocks the plan, inspect that limitation; an empty placeholder is not a validated experiment. |
| Final Publication Readiness — `before_final_report` | In Paper, Reviews and Evidence inspect claim-to-source traceability, citation/identity audits, conflicting evidence, remaining objections, experiment proposals versus actual measurements, and the paper roadmap. Record limitations and missing evidence. Final report completion does not establish publication acceptance, journal quartile, universal novelty or SRL advancement. |

## User constraints versus findings

The prepared project records coherent multi-channel reception; FPGA/RFSoC/Zynq targets; approximately **500–1000 hops/s**; desired real-time processing; and possible **ADRV9009/Zynq and RFSoC** platforms as **USER CONSTRAINT, NOT A FINDING**. Do not cite them as demonstrated performance. Channel count, bandwidth, sample rate, calibration method, resource budget and acceptable latency still need operator definitions and evidence.

## Observe and export

Agents shows role/task, provider/model, tokens, latency, estimated cost, retries and routing reason. Open the agent's operational summary for papers, evidence counts, active tools and typed outputs. Overview/Workflow/Reviews shows the current gate. These are execution records and evidence summaries, not hidden chain-of-thought. Cost shows reserved/spent/remaining amounts, call counts, 50/75/90% warnings and hard stops. Read failed-attempt records and `ROUTE_FALLBACK:<provider>:<error class>` when a configured fallback is used.

The ZIP includes the research plan, paper matrix, evidence, claims, gaps, novelty candidates, prior-art/reviewer reports, hardware assessment, experiment plan, paper roadmap, citation audit, cost report, named decisions and a manifest. Verify the manifest hashes. Preserve run ID, configuration fingerprint, source/query logs, candidate revisions and gate failures. Estimates are not billing receipts; proposed experiments are not measured results.

Practice exports retain synthetic labels and separate advisory experiment/paper drafts from canonical scientific outputs. Neither Practice nor provider smoke can advance SRL.
