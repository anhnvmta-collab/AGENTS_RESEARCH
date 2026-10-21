# Research Council

Evidence-first scientific research workflows for RF, DSP, SDR, FPGA and extensible domains.
Python >=3.11. Architecture and implementation plan are in [docs](docs/architecture.md).

## Development

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e '.[dev]'
.venv\Scripts\python scripts/check.py
```

Phases 0–1 establish documented boundaries, typed domain models, migrations and repositories. See
[the phase plan](docs/implementation-plan.md) and phase reports for implementation status.
