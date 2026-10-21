# Agent contracts

Every BaseResearchAgent declares name, role, allowed_tools, task_profile, max_retries,
timeout and provider_policy, and implements validate_input, build_context, run and validate_output. Typed
inputs contain task, only relevant state, evidence and minimal summaries. Every role has its
own external prompt. Tool registry checks permissions at deterministic invocation. Unexpected
model tool calls are rejected before they can dispatch any tool.

| Agent | Input → output | Tools |
|---|---|---|
| ResearchDirector | question → run policy | none |
| ResearchPlanner | question/constraints → plan | none |
| PerspectiveGenerator | plan → perspectives | none |
| QueryPlanner | plan → search queries | none |
| PaperScout | queries → candidates | search |
| CitationScout | seed papers/direction → candidates | citation search |
| LocalDocumentScout | local paths → candidates | local read |
| PaperTriage | candidates → component scores | none |
| DeepReader | ranked located chunks → extractions/evidence/claims | paper read |
| MathDSPAnalyst | evidence → supported analysis/explicit derivations | evidence read |
| HardwareArchitect | evidence/constraints → traffic-light assessment | evidence read |
| GapMiner | matrix/evidence → gaps | evidence/matrix read |
| NoveltyGenerator | gaps → testable candidates | evidence/matrix read |
| PriorArtHunter | normalized claim/keywords/minimal evidence → ranked overlap matrix | search/citation search/evidence read |
| ReviewerTwo | normalized claim/keywords/minimal evidence → skeptical review | evidence read |
| NoveltyJudge | candidate/reports/evidence → decision | evidence read |
| ExperimentDesigner | gaps/approved candidates → baselines/metrics/experiments | evidence read |
| PaperArchitect | experiments/claims → paper roadmap | evidence read |
| CitationAuditor | papers/claims/evidence → scoped audits | metadata verification/evidence read |
| FinalSynthesizer | verified artifacts → traceable synthesis | verified read |

The reviewer input schema excludes generator rationale, persuasive analysis and chat history.
An allowlist projection is used; field blacklists are insufficient. No role can directly promote
its own evidence to verified; deterministic validation and audit own this transition.
