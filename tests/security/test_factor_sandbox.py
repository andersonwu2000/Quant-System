"""AK-5.2: Factor sandbox security tests.

Verifies that submit-factor API rejects dangerous code patterns.
The autoresearch agent can submit arbitrary Python code — the sandbox
must prevent OS access, file I/O, dynamic imports, and code execution.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


# Extract forbidden patterns by executing the source's list definition
def _load_forbidden_patterns() -> list[str]:
    """Extract FORBIDDEN_PATTERNS from auto_alpha.py submit_factor."""
    source = Path("src/api/routes/auto_alpha.py").read_text(encoding="utf-8")
    # Find the FORBIDDEN_PATTERNS block and eval it
    lines = source.splitlines()
    collecting = False
    block = []
    for line in lines:
        if "FORBIDDEN_PATTERNS" in line and "[" in line:
            collecting = True
            block.append(line[line.index("["):])
            continue
        if collecting:
            block.append(line)
            if "]" in line:
                break
    if block:
        code = "\n".join(block)
        return eval(code)  # noqa: S307 — safe, we control the source
    return []


FORBIDDEN_PATTERNS = _load_forbidden_patterns()


class TestForbiddenPatterns:
    """Verify all expected dangerous patterns are in the blocklist."""

    def test_blocklist_not_empty(self):
        assert len(FORBIDDEN_PATTERNS) >= 10, (
            f"Expected at least 10 forbidden patterns, got {len(FORBIDDEN_PATTERNS)}"
        )

    @pytest.mark.parametrize("dangerous_code,description", [
        ("import os\nos.system('rm -rf /')", "os module import"),
        ("import subprocess\nsubprocess.run(['ls'])", "subprocess import"),
        ("__import__('os').system('whoami')", "__import__ builtin"),
        ("exec('import os')", "exec() call"),
        ("eval('1+1')", "eval() call"),
        ("import importlib\nimportlib.import_module('os')", "importlib bypass"),
        ("open('/etc/passwd').read()", "open() file read"),
        ("import sys\nsys.exit(1)", "sys module import"),
        ("import socket\nsocket.socket()", "socket import"),
        ("import shutil\nshutil.rmtree('/')", "shutil import"),
    ])
    def test_dangerous_code_blocked(self, dangerous_code, description):
        """Each dangerous pattern must match at least one forbidden regex."""
        matched = any(re.search(pat, dangerous_code) for pat in FORBIDDEN_PATTERNS)
        assert matched, (
            f"Dangerous code NOT blocked: {description}\n"
            f"Code: {dangerous_code!r}\n"
            f"Patterns checked: {len(FORBIDDEN_PATTERNS)}"
        )


class TestSafeCodeAllowed:
    """Verify legitimate factor code is NOT blocked."""

    @pytest.mark.parametrize("safe_code", [
        # Standard factor code
        '''
def compute_factor(symbols, as_of, data):
    results = {}
    for sym in symbols:
        bars = data["bars"].get(sym)
        if bars is None: continue
        results[sym] = float(bars["close"].iloc[-1])
    return results
''',
        # Using numpy/pandas (allowed)
        '''
import numpy as np
import pandas as pd
def compute_factor(symbols, as_of, data):
    return {s: np.mean([1,2,3]) for s in symbols}
''',
        # Using scipy (allowed)
        '''
from scipy.stats import spearmanr
def compute_factor(symbols, as_of, data):
    return {}
''',
    ])
    def test_safe_code_not_blocked(self, safe_code):
        """Legitimate factor code must not trigger any forbidden pattern."""
        blocked_by = [pat for pat in FORBIDDEN_PATTERNS if re.search(pat, safe_code)]
        assert not blocked_by, (
            f"Safe code incorrectly blocked by: {blocked_by}"
        )
