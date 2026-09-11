"""Integration test suite executing the 25 reviewed semantic queries in pytest."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_q1_to_q25_sempath_queries_suite():
    """Execute docs/test_sempath_queries.py and verify 25/25 pass."""
    script_path = Path(__file__).resolve().parent.parent / "docs" / "test_sempath_queries.py"
    res = subprocess.run(
        [sys.executable, str(script_path)],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, f"Query suite failed:\n{res.stdout}\n{res.stderr}"
    assert "ALL 25 QUERIES PASS" in res.stdout
