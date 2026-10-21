# ADR 0007: Configuration owns task and role routing

Status: accepted. Task profiles provide ordered provider/model routes; optional role overrides
and safe model-ID environment placeholders support deployment-specific policy. Routes and model
prices are operator inputs, never constants in research logic. Metrics record the route actually
used and conservative budget reservations when usage is unavailable. Benchmarking assesses routes
without silently changing configuration. Adaptive selection is deferred until measured evaluation
justifies it. API keys are environment-only and cannot be expanded into persisted configuration.
