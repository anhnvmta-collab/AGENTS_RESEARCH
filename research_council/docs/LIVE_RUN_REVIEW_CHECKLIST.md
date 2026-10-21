# First live run: human review checklist

Run ID: __________  Checkout SHA: __________  Reviewer/date: __________

Use the original publications and `outputs/RUN_ID/` artifacts. A successful software run,
reachable service or high model confidence is not scientific validation. Leave unmeasured
fields blank/null; do not infer expert judgment from model output.

- [ ] **Search coverage:** Inspect all RQs, query families, successful and failed sources;
  check seed/method/concept denominators and scope. Seeds are nonexhaustive; citation recall
  remains null without independently curated expected directed edges.
- [ ] **CORE papers:** Review scalar R/Q/N/M/H/C/F components and diversity selection reasons;
  inspect older seminal, recent low-citation and implementation papers that were excluded.
- [ ] **Paper identities:** Inspect identity audits, source URLs, DOI normalization, title,
  authors, year/version/venue and open conflicts. Check retractions independently.
- [ ] **Evidence locations:** Review the random sample (20 when available); verify each quote,
  page/section/abstract and interpretation against its source. Fill human judgments yourself.
- [ ] **Unsupported claims:** Trace PAPER → EVIDENCE → CLAIM, distinguish source-reported,
  derived analysis and hypotheses. Check missing premises and interpretation overreach.
- [ ] **Contradictions:** Inspect both positions and source excerpts, unresolved severity,
  documented expert resolution and any remaining citation conflicts.
- [ ] **Gap wording:** Require observed evidence, known approaches, limitations/consequences,
  scoped search coverage, confidence and potential counterexamples. Reject universal absence.
- [ ] **Closest prior art:** Inspect component overlap/difference/risk and source-specific
  evidence. Changed source snapshots or failed connectors cannot support novelty survival.
- [ ] **Novelty revisions:** Check four risk classes, v1–v3 changes/reasons/triggering prior art,
  mathematical/implementation changes, falsification tests and negative-control raw verdict.
- [ ] **ReviewerTwo objections:** Inspect every high-severity objection and independence/fallback
  record. Workflow approval cannot silently resolve scientific disagreement.
- [ ] **Hardware assumptions:** Check per-number SOURCE_REPORTED/DERIVED/ESTIMATED/MEASURED labels,
  bandwidth/coherence/clock/latency/resources, fixed-point assumptions and source arithmetic.
- [ ] **Experiment design:** Inspect baselines, ablations, noise/signal/array models, datasets,
  acceptance/failure criteria, statistical plan, reproducibility and falsification conditions.
- [ ] **Model disagreement:** Retain opposing positions, provider/model/execution IDs and
  severity. Record named human resolution, never replace disagreement with an averaged score.
- [ ] **Cost:** Inspect attempts, retries/fallbacks, token usage (including reasoning), budget
  reservations/exhaustion and price-review dates. Reconcile actual provider billing separately.
- [ ] **Search saturation:** Inspect per-round queries, papers/new unique/CORE, method-family,
  evidence and citation-seed proxies. Any saturation is under the configured strategy only.
- [ ] **SRL:** Inspect the explicit evidence chain and current level. Publication readiness
  requires its gates; experimental validation/replication cannot be inferred from a roadmap.

Decision: CONTINUE / REVISE / STOP / INSUFFICIENT_EVIDENCE: __________

Unresolved issues, source artifacts and follow-up owner: ______________________________
