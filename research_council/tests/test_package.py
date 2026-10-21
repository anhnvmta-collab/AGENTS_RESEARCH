import subprocess
import sys

import pytest

from research_council import __version__


def test_version() -> None:
    assert __version__ == "1.0.0"


@pytest.mark.parametrize(
    "module",
    [
        "core.grounding",
        "core.integrity",
        "core.gates",
        "core.orchestration.state",
        "cli",
        "agents.contracts",
    ],
)
def test_public_entry_points_import_in_fresh_process(module):
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            f"import importlib; importlib.import_module('research_council.{module}')",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
