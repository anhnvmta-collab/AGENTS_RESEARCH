# Studio provider compatibility — 2026-10-22

These are offline transport assessments, not successful authentication or scientific validation.
No paid model request was made. Candidate endpoints and thinking behavior remain as recorded
in CANDIDATE_MODEL_COMPATIBILITY.md; this milestone completes the Anthropic adapter work.

Anthropic now moves unsupported scalar/array bounds into field descriptions, preserves them
in the unchanged canonical Pydantic model, encodes typed maps as unique key/value arrays,
decodes them before canonical validation, and rejects malformed/duplicate map entries.
It makes fields required only when the optional-field limit would otherwise be exceeded.
The router reserves against the transformed wire schema and added instructions. The original
schema is never modified. Existing source/claim/review/novelty gates still run afterward.

Schemas exceeding the documented 16-union limit, recursive/external references, untyped maps,
mixed objects/maps or the local grammar-size guard are blocked before any network request.
The router records schema_fallback_<role> and tries the next configured provider. Settings
shows a capability result for every real agent contract. Internal provider grammar limits can
still reject a statically supported schema; the normal route fallback handles those errors.

OpenAI: READY (Responses structured output plus local canonical validation).
Google: READY (GenerateContent JSON schema; explicit Argon thinking level; bounded output).
Anthropic: READY_WITH_SCHEMA_TRANSFORM for supported contracts; the discovery output and
PriorArtReport currently exceed the union limit and require OpenAI/Google fallback. This is
visible per role, not a blanket assertion of Claude support for every scientific artifact.

All providers count reasoning/thinking output in their configured output allowance/cost.
Requests retain the existing configurable 60-second default / 600-second ceiling. First-use
Claude grammar compilation may add latency; no automatic timeout or token-limit increase is
applied. Studio does not implement provider streaming or multi-hop long decode.

Official specifications checked:

- [Claude structured output restrictions and grammar limits](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)
- [Sonnet 5.5 Messages/thinking migration](https://platform.claude.com/docs/en/models/sonnet-5-5/migration-guide)
- [OpenAI GPT-6.1 Sol](https://developers.openai.com/api/docs/models/gpt-6.1-sol)
- [Gemini 4 Argon GenerateContent](https://ai.google.dev/gemini-api/docs/generate-content/latest-model)
