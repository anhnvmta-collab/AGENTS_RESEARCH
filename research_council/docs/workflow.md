# Workflow and recovery

```mermaid
flowchart TD
  Director --> Planner
  Planner --> Perspectives
  Planner --> Queries
  Perspectives --> Discovery
  Queries --> Discovery
  Discovery[Parallel broad / IEEE metadata / citation / local scouts] --> Deduplicate
  Deduplicate --> Triage --> G1[Gate 1: source integrity]
  G1 --> Analysis[Parallel deep reading / math / hardware]
  Analysis --> Matrix --> Gaps --> Candidates
  Candidates --> Attack[Parallel prior-art hunter / Reviewer Two]
  Attack --> Judge
  Judge -->|revise or reject: budget remains| TargetedSearch
  TargetedSearch --> Analysis
  Judge -->|survive| G2[Gate 2: novelty survival]
  Judge -->|iteration limit| Unresolved
  G2 --> Experiments --> PaperPlan --> Audit
  Audit --> G3[Gate 3: publication readiness] --> Synthesis
```

An unsuccessful gate is persisted with reasons. A run may finish a limited report while
publication readiness remains false. No failed gate is bypassed by changing wording.
Each novelty iteration searches again, reads new evidence, rebuilds matrix/gaps and revises
candidates before another independent attack. Rejected and unresolved candidates remain visible.

QUICK uses planning and grounded synthesis. REVIEW adds discovery, reading and audit.
DEEP adds math/hardware, matrix, gaps and experiment planning. NOVELTY runs the full graph.
AUDIT runs discovery/reading plus adversarial review and citation audit, requiring an explicit
claim or producing an incomplete audit. Mode budgets bound the graph; an LLM never owns it.

Stages write checkpoints after completion. Resume replays only incomplete stages; completed
stages are idempotent through deterministic artifact identity and transactions. Failed scouts
record errors while successful branches continue. All scouts failing yields a limited report.
Concurrent ownership is prevented by a run lease; abrupt process termination is recoverable
after lease expiry. Config and workflow versions are pinned per run.

Optional human approval pauses after plan, before DEEP, after gaps, before accepting novelty,
and before final report. Approval/rejection/modification is recorded; continue cannot bypass a
pending approval. Rejected work halts. Modified inputs invalidate dependent stages.
