"""The quickstart never contacts a provider without explicit opt-in."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_quickstart_needs_live_opt_in_even_when_api_key_exists() -> None:
    root = Path(__file__).resolve().parents[3]
    script = root / "integrations/llm_http_transport/examples/quickstart.py"
    environment = os.environ.copy()
    environment.pop("AI_INFRASTRUCTURE_LIVE_TEST", None)
    environment["OPENAI_API_KEY"] = "test-key-never-used"

    # The executable, script, cwd, and environment are assembled from trusted
    # local paths and constants; no user-controlled command is interpolated.
    result = (
        subprocess.run(  # noqa: S603 -- fixed Python executable and repository script
            [sys.executable, str(script)],
            cwd=root,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
    )

    assert result.returncode == 0
    assert "Live provider calls are disabled by default" in result.stdout
    assert "AI_INFRASTRUCTURE_LIVE_TEST=1" in result.stdout
    assert "test-key-never-used" not in result.stdout
    assert result.stderr == ""
