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
class. Live routes require configured token rates. Missing usage, timeouts and interrupted calls
retain a conservative reservation with `cost_basis=reserved_upper_bound`; known-free fake calls
cost zero. Metrics persist before each request so an interrupted call remains observable and
budgeted on resume. Human evaluation scores can be attached later. Benchmarks assess each
configured route without altering saved routing configuration. Budgets cover model calls,
excluding search-service billing.

The shared schema is validated locally even with provider structured output. Tool calls are
data, never executed automatically. Initial stream implementations may buffer a full response;
this capability is advertised, not presented as native token streaming.

Official protocol references, checked 2026-10-21:
* [OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses)
* [Anthropic structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)
* [Gemini structured outputs](https://ai.google.dev/gemini-api/docs/structured-output)
* [Crossref REST API](https://www.crossref.org/documentation/retrieve-metadata/rest-api/)

Scientific source references checked 2026-10-21: [arXiv API manual](https://info.arxiv.org/help/api/user-manual.html) and [arXiv API terms](https://info.arxiv.org/help/api/tou.html). The adapter serializes metadata requests with a minimum three-second interval. IEEE official documentation could not be retrieved in this session; its authenticated backend remains optional rather than an unverified endpoint implementation.
