# Phase 9 implementation report

Connected the deterministic mode pipelines, parallel discovery/reading/math/hardware and
novelty attacks. Checkpoints now project domain artifacts and stage state in one transaction.
Added Typer/Rich commands, pinned run settings, explicit live/demo opt-in, all 14 requested
exports, manifest hashes and JSONL tracing. Formatter, Ruff, mypy and pytest pass (42 tests).

CLI smoke tests completed: all help commands load; the FHSS NOVELTY system test finishes
offline with no papers/evidence/findings; a separate synthetic demonstration exercises two
concurrent branches, evidence linkage and three unresolved novelty iterations. The fixture run
is conspicuously labelled and fails publication readiness. No paid APIs have been called.

## Independent re-audit, 2026-10-21
Added audit RUN_ID, resolve-conflict and benchmark prepare commands. Audit reruns citation checks without LLM conclusions, retains previous audits, demotes contradicted claims and refreshes Gate 3. Publication and experiment selection independently re-evaluate current novelty revisions. Exports now contain all 19 required files under workspace/outputs/RUN_ID, with 18 file hashes and structured saturation/conflict/map/event/chunk records in the manifest. Every model attempt emits provider/model/start/end/latency/tokens/cost/retry/status traces. Prepared FHSS benchmark reports BENCHMARK_READY_BUT_NOT_EXECUTED with empty findings. Moved GitHub CI to repository root and configured package working directory.

Modified: CLI, benchmark, routing/tracing/runtime, agents, gates, human review, pipeline, exporter, example, security docs, CI and tests. Decisions: review commands hold the run lease; workflow status is preserved; export readiness is recalculated from current evidence. Checks: formatter, lint, mypy (81 source files), pytest **103 passed, 0 failed**. Expanded CLI and pipeline tests verify repeat audit retention, exact export count/hashes, trace token accounting and benchmark honesty. Architecture review: no paid calls by offline commands, no confidence bypass, deterministic orchestration and reviewer isolation retained. Limits/debt: live audit can call the run's explicitly enabled scholarly metadata adapters; local JSONL traces are not a centralized observability backend; CI matrix is configured but not executed remotely in this session. Next: independent labels, clean-wheel installation and full acceptance evidence.
