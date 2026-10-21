# ADR 0001: Own a deterministic asyncio workflow

Status: accepted. Use an explicit stage machine, bounded novelty iterations and independent
semaphores. A workflow protocol and typed checkpoint isolate the engine. No LangGraph dependency
is needed in V1. This reduces runtime surface and prevents an LLM from scheduling indefinite work.
Tradeoff: checkpoint, approval and retry behavior must be implemented and tested locally.
