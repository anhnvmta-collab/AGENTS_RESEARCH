import subprocess
import sys


def test_selecting_live_tests_without_confirmation_fails_before_network():
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/live", "-m", "live", "--collect-only", "-q"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 4
    assert "--run-live --confirm-paid-apis" in result.stderr


def test_repository_ignores_secret_files_and_default_ci_is_offline():
    from pathlib import Path

    root = Path(__file__).parents[1]
    assert ".env" in (root / ".gitignore").read_text(encoding="utf-8")
    workflow = (root.parent / ".github/workflows/ci.yaml").read_text(encoding="utf-8")
    assert 'pytest -q -m "not live"' in workflow
    # Scan release source/config/docs for credential literals, not the user's environment.
    import re

    for directory in ("src", "config", "prompts", "benchmarks"):
        for path in (root / directory).rglob("*"):
            if path.is_file() and path.suffix in {".py", ".yaml", ".md"}:
                text = path.read_text(encoding="utf-8")
                assert not re.search(
                    r"(?:sk-(?:proj-|ant-)?[A-Za-z0-9_-]{24,}|AIza[A-Za-z0-9_-]{30,})", text
                ), str(path)
