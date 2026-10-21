# ADR 0004: Validate and fence scientific checkpoints

Status: accepted. An explicit stage cursor and typed state own scheduling. Every scientific
checkpoint revalidates the complete paper/evidence/claim/gap/novelty/review/experiment/roadmap
graph before persisting state and relational projections in one transaction. Migration 0002
adds run/revision snapshots and FK-backed edges; global paper identity is separate from run scope.
Lease ownership and expiry are checked in the write transaction to fence stale workers.
Unknown state/workflow versions fail with an explicit compatibility error.

Tradeoff: legacy checkpoints may export for inspection but cannot resume if they violate new
invariants. Migration 0001 remains unchanged. PostgreSQL deployment remains independently testable.
