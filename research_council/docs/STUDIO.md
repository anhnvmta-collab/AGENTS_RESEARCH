# Research Council Studio

Local workstation UI for the existing Research Council engine. Start with **Practice with
demo**. The synthetic FHSS/DOA project exercises all 20 real agent classes, seven named
review gates, evidence inspection, adversarial novelty revisions and the final export.
Practice uses FakeProvider and fixture sources; it cannot establish scientific novelty.

## Install and launch (PowerShell, from research_council/)

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
cd studio/frontend
npm ci
npm run build
cd ../..
.\.venv\Scripts\research-council.exe studio
```

Open http://127.0.0.1:8765. The Python server serves the built frontend directly. No cloud,
remote fonts or hosted assets are required. Data persists in `workspace/studio/` by default.
Run `studio --workspace <directory> --port <port>` to choose another local workspace/port.
This initial release is launched from the repository checkout; build the frontend before
launching. A standalone Python wheel does not currently bundle the frontend build.

## Development (two terminals)

```powershell
# Terminal 1, research_council/
.\.venv\Scripts\research-council.exe studio backend
# Terminal 2, research_council/studio/frontend/
npm run dev
```

Open http://127.0.0.1:5173. Vite proxies /api to the local backend. Both ports bind loopback.

## Operating the workspace

Create a project in Vietnamese or English, set its topic/scope/mode and budget, and open a
run. **Start** begins work; **Pause** requests a stop at the next durable stage boundary.
**Resume** uses pinned settings/checkpoints. **Cancel** cooperatively terminates the run as
REJECTED and cannot resume it. No process is killed. After each approval, explicitly Resume.
Closing/restarting the server retains checkpoints; a restarted worker may need the existing
45-second lease to expire after an unclean shutdown.

Use Papers to upload up to ten PDFs (20 MB each), see parsing status and inspect source data.
Parsed documents join a run before its first Start, or a subsequent new run. An already
executed run retains its source configuration. Encrypted/image-only PDFs are visibly blocked;
OCR is not included. Arbitrary local directories are not exposed through the browser.

Agents → role opens the real contract, allowed tools, execution history, usage, safe input /
output counts, inspected paper IDs and related evidence. Discussion executes the selected
role as advisory work and does not update the scientific checkpoint. Action creates a typed
proposal tied to the checkpoint hash. Approving it by name executes that role, restarts
canonical planning with the approved instruction, and invalidates downstream state/approvals.
The UI states this effect before approval. Actions require an active human review gate;
completed runs remain available for discussion. All model work counts against the run budget.

Novelty revisions link back through gaps, claims and evidence to source papers. The Battle
view shows structured attacks/reviews/decisions, including provider-independence limitations.
Hardware numbers retain SOURCE_REPORTED / DERIVED / ESTIMATED / MEASURED provenance;
unknown values stay unknown. Experiment and paper edits are named, immutable application
revisions. Researcher approval of a draft is separate from scientific source attestation.
The initial paper builder creates evidence-bound section roadmaps, not publication-ready prose.
Missing or unverified support remains visible; references come only from recorded papers.

## Practice and scientific gates

Synthetic excerpts may be PARTIALLY_VERIFIED when their source location matches; that does
not make the underlying science verified. Canonical Gate 2/3 and SRL remain blocked/0.
Because the canonical NOVELTY pipeline correctly refuses experiment adoption without Gate 2,
Studio executes ExperimentDesigner and PaperArchitect as explicitly **ADVISORY_SYNTHETIC**
learning artifacts after the approved novelty stage. These are real agent executions, stored
separately and exported with their scope. They never enter the canonical accepted experiment
list or certify a contribution. All other practice stages use the unchanged workflow engine.

## Real research (operator configuration only during implementation)

Set provider keys in the local environment or ignored `.env`, then configure Providers &
models: models, current token prices, ordered routes, sources, timeout and six budget caps.
Keys are never accepted or returned by the settings API. The UI shows presence booleans.
Each of eight profiles and NoveltyJudge needs an enabled compatible route. Claude discovery
and prior-art output schemas currently need OpenAI/Google fallback; see
[provider compatibility](STUDIO_PROVIDER_COMPATIBILITY.md).

Create a project with Practice unchecked. Studio displays a preflight with models/sources,
budget/call caps and required approvals. Creating the run requires the exact **START REAL
RESEARCH** confirmation. Start is then a separate explicit action. Saved configuration does
not alter existing pinned runs. No live research or paid model call was run for this release.

## Verification

```powershell
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy src
.\.venv\Scripts\python.exe -m pytest -q -m "not live"
cd studio/frontend
npm run lint
npm run typecheck
npm run test
npm run build
npx playwright install chromium
npm run e2e
```

Playwright starts an isolated fixture server with outbound Python HTTP disabled, exercises
the production build, and writes screenshots and machine-readable audit results under docs/.
This is a local single-operator application, without multi-user authentication or cloud hosting.
