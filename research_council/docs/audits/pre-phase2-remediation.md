# Pre-phase-2 remediation

Date: 2026-10-21. Baseline preserved in commit `4e78781` on `engineering-audit-v1`.
The inherited 58-test suite was not treated as proof of the expanded requirements.

## Corrected foundation findings

| Finding | Correction and evidence |
|---|---|
| C01 | Complete graph validator runs before checkpoint projection; rejects 12 tested broken-edge/duplicate cases; decision/report and roadmap links are explicit |
| C02 | Human attestation refuses existing contradictory source/claim audits; regression confirms the contradiction is retained |
| H01 | Alembic 0002 adds run/revision scientific snapshots and composite-FK edges; tests preserve two runs and candidate revisions and reject cross-run links |
| H02 | Gate 2 requires successful query attempts, actual matching model execution records, grounded source text and exact revision; experiment selection uses revision keys |
| H03 | Experiment/roadmap contracts link artifacts; Gate 3 requires hypothesis, ablation, statistics, acceptance/failure/reproducibility fields and a linked roadmap |
| H04 | CitationAuditor checks missing support and claim/evidence consistency; unsupported claims remain UNVERIFIED |
| H05 | Gate 1 requires resolved metadata or explicitly supplied local identity; synthetic scope remains separately labelled |
| H06 | Aware timestamps normalize to UTC; naive/non-finite data is rejected; persistence round-trips schemas to catch mutation/copy bypasses |
| H07 | EvidenceConflict is retained and synchronized at checkpoints; high unresolved conflicts affect gates; ReviewerTwo cannot self-resolve objections |
| M01 | Operational Gap/Novelty/Run/Execution repository protocols and run-scoped reads added |
| M05 | Lease operations moved behind repository methods; checkpoint writes fence stale owners inside the transaction; state version is validated |

Modified: domain schemas/contracts; repository/store; storage database/projector and new graph
projection/migration; integrity policy; gates; workflow/novelty; operational execution stamping;
experiment/paper agents; citation/human review; regression fixtures/tests. Migration 0001 is unchanged.
New ADRs cover checkpoint state, source adapters, novelty isolation and configured routing.

## Actual checks

`python scripts/check.py`: formatter PASS; Ruff PASS; mypy PASS (71 source files);
pytest **77 passed**. Migration upgrade/downgrade/upgrade from an empty database passes.
The four initial regressions after tightening gates were corrected with complete proof fixtures,
not by weakening the new gates.

## Remaining phase work

M02–M04/M06–M07 remain scheduled for their respective phase acceptance: routing preferences and
safe environment configuration; context retrieval; saturation/query expansion/adapter ports;
hardware labels; complete outputs/trace/CLI/evaluation; clean install and security acceptance.
No live provider, PostgreSQL or scientific benchmark result is claimed. The foundation is healthy
enough to continue; remaining integrations cannot bypass the corrected graph/gate policies.
