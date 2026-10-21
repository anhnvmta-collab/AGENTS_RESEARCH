# Candidate-model adapter compatibility

Checked 2026-10-21 against base commit `4aaed7d82ed3eebd3875431936aac24392a03a4f`.
Official specifications and offline HTTP mocks only. No authenticated API request, paid model
call, provider smoke or scientific benchmark was executed. SRL remains 0.

**The three-model scientific run is not cleared:** the Anthropic endpoint/model is supported,
but several existing research output schemas violate its native structured-output rules.
The small patch below fixes response/deadline handling; it does not claim full schema
portability or real account access. Architecture, data contracts, gates and budgets are retained.

## Endpoint and JSON-output compatibility

| Model | Endpoint used by this adapter | JSON output | Assessment |
|---|---|---|---|
| `gpt-6.1-sol` | POST `https://api.openai.com/v1/responses` | `text.format` with `type: json_schema`, `strict: false`; full local Pydantic validation | Documented endpoint and response-format shape supported. Non-strict mode is not a server guarantee of every constraint. |
| `claude-sonnet-5-5` | POST `https://api.anthropic.com/v1/messages`, `anthropic-version: 2023-06-01` | `output_config.format` with `type: json_schema` | Supported for compatible schemas; current raw research schemas have blockers described below. |
| `gemini-4-argon` | POST `https://generativelanguage.googleapis.com/v1beta/models/gemini-4-argon:generateContent` | `generationConfig.responseMimeType: application/json` and `responseJsonSchema` | Documented GenerateContent interface/subset supported; local validation remains required. Interactions is not required for this single-request path. |

OpenAI confirms this exact model, Responses and structured output support in its
[model page](https://developers.openai.com/api/docs/models/gpt-6.1-sol). The
[Responses reference](https://developers.openai.com/api/reference/resources/responses/methods/create)
distinguishes strict schema adherence from the adapter's explicit non-strict mode.
Anthropic's [migration guide](https://platform.claude.com/docs/en/models/sonnet-5-5/migration-guide)
confirms the current Claude API ID without a date suffix. Google's
[GenerateContent reference](https://ai.google.dev/api/generate-content) documents the REST
endpoint/JSON fields; [structured output guidance](https://ai.google.dev/gemini-api/docs/generate-content/structured-output)
documents its schema subset. A supported wire shape is not proof of live model availability.

## Thinking and token handling

| Model | Current request behavior | Token parameter/accounting | Limits and caveats |
|---|---|---|---|
| OpenAI | No reasoning override: documented `medium` default. `low`, `medium`, `high`, `xhigh`, `max` exist; `none`/`minimal` are unsupported for this model. Parser reads output text, not reasoning summaries. | `max_output_tokens` bounds reasoning plus visible output. Usage output_tokens is already the inclusive total. | Provider ceiling 128,000; application routes allow 128–32,768, default 4,096. No effort control is exposed by Route/LLMRequest. |
| Anthropic | Omitting thinking uses adaptive thinking; thinking text is omitted by default. Parser selects content blocks with type=text. No forced tool choice or unsupported sampling override is sent. | `max_tokens` covers thinking and final text. usage.output_tokens is inclusive, so it is not counted twice. | Sonnet ceiling 128K; application cap 32,768. Disabling up-front thinking requires between_tools, not disabled; neither override is currently exposed. |
| Gemini | Base omitted thinking config; patch explicitly sends the documented MEDIUM default for this exact model. Low/medium/high exist; thinking cannot be disabled. Thought-marked parts are excluded. | `maxOutputTokens` includes thinking plus answer. Candidate + thoughts tokens are summed for output cost, as already fixed at the base commit. | Non-streaming GenerateContent is capped at 32,768 per request. No long-decode/continuation loop, streaming or operator-selectable thinking-level override is implemented. |

Sources: [OpenAI reasoning](https://developers.openai.com/api/docs/guides/reasoning),
[Claude thinking](https://platform.claude.com/docs/en/build-with-claude/thinking),
[Gemini GenerateContent thinking](https://ai.google.dev/gemini-api/docs/generate-content/thinking),
and [Gemini long decode](https://ai.google.dev/gemini-api/docs/generate-content/long-decode?hl=en).
Google's general model page lists a broader output capability; the endpoint-specific
non-streaming cap above is the relevant limit for this adapter.

The Google thinking guide calls thinkingLevel required for Gemini 4 while also documenting
medium as the fallback when omitted. Sending MEDIUM explicitly removes that ambiguity without
increasing the intended reasoning level. No deprecated thinkingBudget is sent. The current
adapters perform single-turn structured tasks; provider thinking signatures are not retained
or replayed for multi-turn model-driven tool loops.

Small caps are valid requests, but can exhaust their tokens before any complete JSON answer.
The operator template's 4,096 and smoke's 128 are not evidence of suitability for these
reasoning workloads. OpenAI suggests an initial 25,000-token reasoning/output allowance;
Google's [GenerateContent migration guidance](https://ai.google.dev/gemini-api/docs/generate-content/latest-model)
advises 32,768 for existing lower caps. Those are workload recommendations, not request
minimums. No caps, prices or cost budgets were automatically increased.

## Timeout requirements and the reproducible deadline defect

At the base commit, Runtime's HTTP client and ModelRouter accepted the configured timeout,
but BaseResearchAgent imposed min(60, configured_timeout). Thus a configured 180 or 600
seconds still became 60 for every ordinary agent. Offline capture tests reproduced both.

The patch changes the default role ceiling to 600, matching Settings' existing upper bound.
The default configured timeout remains 60 seconds. An operator-selected 180/600 now reaches
the router; a deliberately shorter role-specific deadline still applies. No request waits
were used to test this and no timeout setting was silently raised in operator configuration.

No fixed model-specific minimum timeout was established by these sources. Thinking, output
length and first-use schema compilation affect latency. All adapters remain synchronous;
long-running workloads can exceed a chosen deadline. OpenAI's
[Python SDK](https://developers.openai.com/api/reference/python) uses a configurable ten-minute
default, but this project uses HTTPX rather than that SDK. Claude's thinking guide recommends
streaming for long requests; its SDK's >21,333 max_tokens streaming check is a client rule,
not a REST API restriction. Very long/batch/background generation remains outside this adapter
path. A timeout/retry can still incur provider cost; software estimates are not invoices.

## Anthropic schema blocker remains explicit

According to [Anthropic's structured-output specification](https://platform.claude.com/docs/en/build-with-claude/structured-outputs),
native JSON output rejects unsupported numeric/string constraints, non-false additionalProperties
and excessive grammar complexity. Its documented counts include at most 24 optional parameters
and 16 union parameters. This project submits raw Pydantic schemas without SDK transformation.

Examples measured locally (counts include schema definitions; not a live API response):

| Output contract | Concrete issue |
|---|---|
| PaperScore / PaperTriage | Score minimum/maximum constraints are present. |
| ResearchPlan / ResearchPlanner | subquestions is an arbitrary-key dictionary; also contains unsupported bounds. |
| ReadingOutput / DeepReader | Unsupported bounds; 27 optional properties across definitions. |
| HardwareAssessment / HardwareArchitect | Five arbitrary-key dictionary schemas. |
| PriorArtReport / PriorArtHunter | Unsupported bounds, dictionaries, 76 optional properties and 29 unions. |

The machine audit lists all 20 role schemas. These findings are a static incompatibility
with the published rules, not an observed paid HTTP 400. A simple compatible schema passes
the offline Anthropic protocol test; that test does not certify the real extraction schema.

Removing bounds alone does not repair dictionaries/complexity. Forcing additionalProperties
to false on a dictionary would lose valid scientific fields; a prompt-only JSON fallback
would alter the native structured-output guarantee. Neither change was introduced. Full
Anthropic research-role support needs a deliberate, reversible wire-schema adaptation while
retaining original local validation. That representation work is outside this small patch.
OpenAI non-strict and Gemini subset output also rely on the unchanged original local validators.

## Small patch and verification

- BaseResearchAgent honors the already-supported configured timeout range.
- Gemini sends explicit MEDIUM for Argon and ignores thought-marked text; final answer text
  is kept even if its part also has a thoughtSignature. The signature itself is not retained.
- ModelRouter rejects CONTINUATION even if a partial hop happens to contain valid JSON;
  it does not start unbudgeted continuation requests.

The new tests first reproduced four failures against the base (thinking text, continuation,
180-second deadline, 600-second deadline). After the patch: **188 offline passed, zero failed,
two live tests deselected**; all previous 179 cases remain passing. Nine new cases check the
three exact candidate wire contracts, token totals, parser isolation, incomplete-result
rejection, configured deadlines and explicit shorter role deadlines. Ruff format/check and
mypy (103 source files) pass. [JUnit](audits/candidate-model-compatibility-offline.xml) and
[static schema audit](audits/candidate-model-compatibility.json) provide the evidence.

No configured model/provider choices, default reasoning level, pricing, operator YAML, scientific data, migrations, workflow
architecture, research gates, spending caps or paid-consent policy were changed. No scientific
benchmark, real provider smoke, authenticated model lookup or SRL advancement was performed.
