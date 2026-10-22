# Pilot 01 provider smoke plan — NOT EXECUTED

**PAID_CALLS = 0 for this preparation.** This document describes a later operator action requiring separate authorization. Do not run its paid command during preparation. No live source search, scientific workflow or literature benchmark is part of this smoke.

1. Copy `config/pilot01.example.yaml` to the gitignored `config/pilot01.operator.yaml`. Set `OPENAI_MODEL_ID`, `ANTHROPIC_MODEL_ID` and `GOOGLE_MODEL_ID` locally to model IDs verified in the operator's accounts. Fill the three YAML anchors' current input/output USD-per-million prices and `pricing_verified_on` dates. Keep API keys only in local environment variables or the gitignored `.env`. Do not paste keys into Studio, reports or configuration.
2. Review the chosen models' endpoint access, structured-output support, token limits and timeout behavior in their official documentation and account console. No account-valid model ID or price has been supplied by this preparation. Adapter/schema offline compatibility is not model access verification.
3. Run configuration-only preflight, without paid flags:

   ```powershell
   .venv\Scripts\research-council.exe providers preflight --config config/pilot01.operator.yaml
   ```

   Resolve errors. Review zero/stale price warnings, fallback routing, source configuration and all six budget fields. A ready result establishes local configuration only.
4. Only after the operator authorizes the separately capped smoke, stop the Studio server and ensure no research worker is active. The **future paid command, not executed here**, is:

   ```powershell
   .venv\Scripts\research-council.exe providers preflight --config config/pilot01.operator.yaml --workspace workspace/studio-pilot01 --live --confirm-paid-apis
   ```

   Both flags are mandatory. The existing smoke runner performs one structured request per enabled provider, no retries and no fallback across providers. With this template that means at most **3 attempts**, each asking only for `{"ok":true}`, with **128 maximum output tokens**. It reserves estimated cost before each request and caps the separate smoke at **USD 0.25 or the lower configured limit**. A conservative reservation may block a request before all three providers run. Provider errors still consume their conservative reservation when usage is unavailable. Never increase caps automatically.
5. Inspect the JSON summary and the persisted model execution records in the same workspace. Reopen Studio afterward. A `PROVIDER_SMOKE_ONLY` run is a protocol record, not a scientific pilot. Saving the smoke in a different workspace leaves this Studio's access status NOT_TESTED.

| Purpose | Evidence required |
| --- | --- |
| Authentication and model access | Successful response for the exact configured provider/model. Missing credentials and access/model errors stay BLOCKED or unverified. |
| Minimal structured output | Canonical validation of `{"ok":true}` succeeds; no refusal, tool call or truncated completion is accepted. This does not prove compatibility with all 20 full agent contracts. |
| Usage parsing | Inspect nonmissing usage, input/output token counts and `cost_basis=usage`. Reserved-upper-bound accounting alone does not verify usage parsing. |
| Latency and timeout | Inspect start/end/latency and timeout/error class. The template uses an operator-reviewable 180-second per-attempt timeout. A timeout is not evidence that authentication failed. |
| Cost accounting | Compare token counts and reviewed prices to estimated cost and ledger reservations. Actual billed cost remains unknown until checked against the provider's billing records. Source-service fees are unmeasured. |

The deliberately small 128-token output cap can exhaust a reasoning model's budget before JSON is returned. Record that failure as inconclusive; do not silently enlarge the cap or rerun. Do not log credentials, raw provider error payloads or hidden reasoning.

The readiness panel distinguishes local CONFIGURED, CREDENTIAL_PRESENT, historical model-specific SMOKE_TESTED, NOT_TESTED and BLOCKED. It only recognizes successful live-provenance `ProviderPreflight_<provider>` records for every currently configured model of that provider; synthetic records and a changed model ID do not qualify. A credential or prior smoke is not a guarantee of current availability. Crossref, OpenAlex and arXiv remain NOT_TESTED until their access is separately verified; this provider smoke never contacts them. Check their current account/rate-limit requirements, including OpenAlex credentials where required, before research.

The smoke's cap is separate from the pilot's USD 5 estimated model budget; these are per-run caps, not a shared account spending limit. If the operator wants a combined USD 5 estimate ceiling, reduce the subsequent pilot cap by the smoke allocation before import and confirmation. Config/smoke alone leaves **LIVE_PILOT_EXECUTED=false and SRL=0**. Do not start the pilot as an automatic next step.
