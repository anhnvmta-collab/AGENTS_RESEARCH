# ADR 0003: Isolate provider protocols behind a routed port

Status: accepted. Use HTTPX adapters and Pydantic schemas rather than agent-specific vendor SDK
calls. Configure ordered routes and token rates per task. Fake providers use the same port and
are test-only/offline options. Tradeoff: wire formats require protocol tests and live deployment
checks; advanced vendor-specific tools are not exposed as implicit agent privileges.
