# Live provider setup: Windows PowerShell

Use `config/phase11.operator.example.yaml` as the first-run template. It contains no real model
IDs or prices. Copy it to the ignored `config/phase11.operator.yaml`, then configure the three
anchored routes. All eight task profiles and the independent NoveltyJudge role reference them.

| Provider | YAML provider | Credential environment variable | Adapter protocol |
|---|---|---|---|
| OpenAI | `openai` | `OPENAI_API_KEY` | Responses API, JSON schema |
| Anthropic | `anthropic` | `ANTHROPIC_API_KEY` | Messages API, JSON schema |
| Google Gemini | `google` | `GOOGLE_API_KEY` | generateContent, JSON schema |

All three can be used in one run. Select account-valid IDs supporting the adapter protocol and
structured output. No model is declared universally best. Gemini IDs must be one path segment,
without a `models/` prefix. Model existence/account access cannot be established offline.
The optional smoke tests one selected route per enabled provider, not every model in a custom
configuration. More than one model per provider requires separate operator compatibility checks.

## Configure routes, fallback and prices

At each anchor, set `model`, `input_cost_per_million`, `output_cost_per_million` and
`pricing_verified_on: YYYY-MM-DD`. Prices are USD per million tokens. Use the applicable
context/tier prices for the actual model; if tiered, use a conservative upper bound for this
run. Missing prices block preflight and live cost reservation. Zero prices produce a warning.
Missing review dates or dates older than 30 days/future dates produce a warning; a fresh date
does not prove the entered price is correct. No price is fetched or invented by preflight.

Review current official [OpenAI pricing](https://developers.openai.com/api/docs/pricing),
[Anthropic pricing](https://platform.claude.com/docs/en/about-claude/pricing), and
[Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing). Actual billing remains external
and separate from token-based estimates. Gemini reasoning tokens count toward output estimates.

The initial preference is generator/OpenAI, reviewer/Google and judge/Anthropic. These are
editable routing choices. ReviewerTwo tries a different configured provider before the
generator's provider. A single enabled provider is allowed with explicit diversity/fallback
warnings; runtime records SAME_PROVIDER_FALLBACK. Set `enabled: false` on unused anchors;
their unresolved model placeholders, prices and absent keys are then ignored. Keep an enabled
route for every profile and role override. Add fallback entries explicitly if customizing.

## Temporary session keys without shell-history literals

Run this locally in the same PowerShell session that will launch the CLI. Values entered at
the secure prompt do not appear in the command text or console output:

```powershell
function Set-CouncilSessionKey {
    param([ValidateSet('OPENAI_API_KEY','ANTHROPIC_API_KEY','GOOGLE_API_KEY','OPENALEX_API_KEY')][string]$KeyName)
    $councilSecureValue = Read-Host "Enter $KeyName" -AsSecureString
    $councilBuffer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($councilSecureValue)
    try {
        [Environment]::SetEnvironmentVariable($KeyName, [Runtime.InteropServices.Marshal]::PtrToStringBSTR($councilBuffer), 'Process')
    } finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($councilBuffer)
        $councilSecureValue.Dispose()
    }
}
Set-CouncilSessionKey OPENAI_API_KEY
Set-CouncilSessionKey ANTHROPIC_API_KEY
Set-CouncilSessionKey GOOGLE_API_KEY
# Recommended for research-scale OpenAlex use:
Set-CouncilSessionKey OPENALEX_API_KEY
```

Skip disabled providers. This application reads keys from the process environment; the
preflight command also loads a local `.env` without overriding existing session variables.
Never print `$env:*API_KEY`, request headers or `.env` contents to verify setup. Preflight
reports credential names and presence booleans only. Keys are not sent anywhere by default.

OpenAI's [official authentication documentation](https://developers.openai.com/api/reference/overview)
directs applications to use environment variables or a server-side key management service.
OpenAlex's [authentication guide](https://help.openalex.org/api/authentication/) recommends a
free key for research-scale queries; availability and limits remain untested here. The runtime
already reads `OPENALEX_API_KEY`. Source usage fees/quotas are separate from the USD 5 LLM cap.
Crossref/arXiv need no model key. IEEE's optional interface has no wired authenticated backend
in this CLI; leave it disabled. Preflight reports it as a blocker if selected, rather than
pretending an IEEE key alone enables it. No paywall bypass or restricted-page scraping is used.

## Persistent setup options

A managed credential vault can inject environment variables at launch. Research Council does
not automatically integrate with a vault. On Windows, another option is a DPAPI-protected
file readable by the same Windows user on the same machine. Microsoft's
[ConvertFrom-SecureString documentation](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.security/convertfrom-securestring)
describes Windows DPAPI encryption when no explicit encryption key is supplied.

Save one prompted key outside the repository (repeat for enabled provider names):

```powershell
$councilCredentialDirectory = Join-Path $env:LOCALAPPDATA 'ResearchCouncil'
[IO.Directory]::CreateDirectory($councilCredentialDirectory) | Out-Null
$councilKeyName = 'OPENAI_API_KEY'
$councilEncryptedPath = Join-Path $councilCredentialDirectory "$councilKeyName.dpapi"
Read-Host "Enter $councilKeyName" -AsSecureString | ConvertFrom-SecureString | Set-Content -LiteralPath $councilEncryptedPath
```

Load it into a new launch session:

```powershell
$councilEncryptedValue = (Get-Content -LiteralPath $councilEncryptedPath -Raw).Trim()
$councilSecureValue = ConvertTo-SecureString -String $councilEncryptedValue
$councilBuffer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($councilSecureValue)
try {
    [Environment]::SetEnvironmentVariable($councilKeyName, [Runtime.InteropServices.Marshal]::PtrToStringBSTR($councilBuffer), 'Process')
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($councilBuffer)
    $councilSecureValue.Dispose()
}
```

Recreate the directory/name/path variables in a fresh session first. DPAPI does not protect
against processes already running as your Windows user; restrict account/device access.
User-scoped environment variables persist in plaintext in the user environment, so a vault
or encrypted file is preferable for durable storage. The application still needs a plaintext
process environment value while making authenticated requests.

An ignored `.env` is a local plaintext convenience, not encrypted storage. `.env`, `.env.*`
(except `.env.example`) and the operator YAML are ignored by Git. Do not commit `.env`, put
keys in YAML, paste secrets into logs, or include them in research outputs. Use the provider
dashboard to revoke/rotate any exposed credential. No real keys are supplied or created here.

Continue with [the first-run runbook](FIRST_LIVE_RUN.md).
