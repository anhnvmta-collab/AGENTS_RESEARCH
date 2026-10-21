# Phase 8 implementation report

HardwareArchitect conservatively validates evidence references and required implementation
parameters. Explicit streaming models derive input traffic, AXI utilization and hop deadlines
without presenting estimates as measured performance. Math claims, gaps, novelty references
and final synthesis receive additional validation. Added optional in-memory vector port and
the requested FHSS project input without findings. Formatter, Ruff, mypy and pytest pass
(36 tests). ExperimentDesigner and PaperArchitect retain separate typed contracts/prompts.

## Independent re-audit, 2026-10-21
Hardware parameters now require explicit numeric values and per-parameter evidence references. MEASURED needs verified quotations with numeric anchors; missing provenance downgrades to ESTIMATED/UNKNOWN. GREEN requires the sourced implementation envelope. Derived streaming bounds remain calculations from assumptions. Prompts explicitly cover DDC, FFT/PFB, parallelism and streaming. ExperimentDesigner rejects incomplete hypothesis/baseline/metric/ablation/statistics/failure/acceptance/reproducibility contracts and enforces ordered Simulation, Synthetic IQ, Recorded IQ, SDR, FPGA/RFSoC stages when hardware is present.

Modified: hardware validator, hardware/experiment agents, prompts, demo fixtures, graph validation and tests. Decision: conservative numeric anchors plus separate semantic attestation; no inference of measured utilization from plausible numbers. Checks: formatter, lint, mypy (80 source files), pytest **103 passed, 0 failed**. Added numeric-provenance, invalid-parameter and progression tests. Architecture review: scientific gates remain deterministic; fixture results do not verify science; no provider coupling or reviewer leakage introduced; resume remains covered. Limits/debt: numeric anchoring cannot establish semantic entailment; resource envelope is conservative for FPGA-oriented studies; no synthesis tool or radio lab execution. Next: CLI audit, complete exports, traces and benchmark preparation.
