# Security

Secrets come from environment variables and are excluded from persisted configuration, traces,
exceptions and reports. Log only enumerated event fields and sanitized error classes. Do not
persist raw HTTP requests or response bodies in failure traces. Pricing and model IDs are not secrets.

Documents, metadata, abstracts and model outputs are untrusted data. Prompts explicitly prohibit
following source instructions. Source text is bounded and wrapped as data. Registry allowlists
apply to all tool invocations; unexpected model tool calls are rejected. Deterministic agent code
invokes only typed tools from its allowlist.
No shell or unrestricted browser tools are exposed to agents.

Resolve file paths against the configured workspace and reject absolute/path traversal and
symlink escapes outside it. Bound file sizes, pages and extracted characters. PDFs are text-only;
no embedded JavaScript, macros or attachments are executed. V1 has no OCR. Export paths stay
inside the workspace; CSV cells beginning with spreadsheet formula characters are escaped.

Network adapters use fixed HTTPS origins, no arbitrary full-text URL fetch or unrestricted
redirects. Metadata URL presence is not retrieval proof. API and search adapters are opt-in.
No IEEE scraping; the optional IEEE boundary requires an injected authenticated backend.

SQLite is a single-user local store. Production multi-user deployment needs authentication,
authorization, encryption/backups, retention rules and infrastructure hardening outside this CLI.
