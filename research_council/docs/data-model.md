# Data model

All public contracts use Pydantic v2 with unknown fields forbidden. UUIDs identify artifacts;
timestamps are timezone-aware UTC internally. Human-facing schedules use the client's timezone.

Project → Run → question/plan/queries/checkpoint. Paper → metadata/scores → evidence → claims.
Gap links evidence and claims; candidate links gaps/evidence; prior art and review link candidates.
Decision links independently completed reports; gates record checks and reasons.

Evidence includes a short excerpt (maximum 500 characters), normalized statement,
interpretation, extractor, page/section/table/figure, confidence and verification scope.
Metadata matches cannot verify scientific claims. DERIVED claims require premises and a
derivation description. HYPOTHESIS claims cannot be VERIFIED. VERIFIED requires evidence IDs;
repository validation checks every referenced artifact and paper identity.

Tables: projects, research_runs, papers, paper_metadata, paper_scores, search_queries, evidence,
claims, gaps, novelty_candidates, prior_art_matches, reviews, citation_audits, agent_executions,
model_executions, quality_gate_results, artifacts and approvals. Artifact payloads use JSON;
relationships use indexed relational IDs and validated references. Runs isolate fixture and live
provenance. DOI is normalized to lowercase without resolver prefix; non-DOI identity uses title,
author/year and conservative fuzzy matching. Conflicting DOIs never merge through title alone.

Knowledge maps are recursive JSON nodes containing topic/subtopics and paper/claim/gap IDs,
with explicit coverage scores. Vector retrieval is optional and is never a source of truth.
