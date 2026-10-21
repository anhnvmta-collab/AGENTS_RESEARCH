"""Run the required phase checks; fail before progressing to another phase."""

import subprocess
import sys

for args in (
    ["ruff", "format", "."],
    ["ruff", "check", "."],
    ["mypy"],
    ["pytest", "-q"],
):
    subprocess.run([sys.executable, "-m", *args], check=True)
