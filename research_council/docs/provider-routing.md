# Providers and routing

BaseLLMProvider exposes generate, generate_structured and stream, a typed tool-call envelope,
usage, nullable cost estimate, latency and retry metadata. OpenAI Responses, Anthropic Messages
and Gemini generateContent HTTP adapters are the only vendor-aware modules. HTTPX provides
timeouts and mock transports; provider SDK dependencies are unnecessary.

ModelRouter selects ordered routes by task profile from YAML. All configured model IDs are
operator supplied (CONFIGURE_ME is rejected). Profiles: SEARCH_PLANNING, PAPER_EXTRACTION,
MATH_REASONING, HARDWARE_REASONING, SYNTHESIS, NOVELTY_GENERATION, ADVERSARIAL_REVIEW,
CITATION_VERIFICATION. Deterministic fallback never silently changes live data to fixture data.

Retries cover transient timeouts, 429/5xx and invalid structured output. Backoff is bounded,
exponential with jitter and respects Retry-After. Authentication and bad configuration fail fast.
Each attempt persists valid-output status, usage when returned, latency, retry number and error
class. Costs are null unless configured token rates exist; zero is reserved for known-free fake
calls. Human evaluation scores can be attached later. Benchmarks do not alter routes automatically.

The shared schema is validated locally even with provider structured output. Tool calls are
data, never executed automatically. Initial stream implementations may buffer a full response;
this capability is advertised, not presented as native token streaming.

Official protocol references, checked 2026-10-21:
* [OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses)
* [Anthropic structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)
* [Gemini structured outputs](https://ai.google.dev/gemini-api/docs/structured-output)
* [Crossref REST API](https://www.crossref.org/documentation/retrieve-metadata/rest-api/)
