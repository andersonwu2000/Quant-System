"""AST-based safety checker for research factor code (AP-6).

Checks factor source code before dynamic loading to prevent:
- Arbitrary imports (only numpy/pandas/math/scipy allowed)
- File/network/process access
- eval/exec/compile
- Dunder attribute access (except __init__, __name__)
"""

from __future__ import annotations

import ast
import logging

logger = logging.getLogger(__name__)

# Modules safe for factor computation
ALLOWED_IMPORTS = frozenset({
    "numpy", "np", "pandas", "pd", "math", "scipy",
    "scipy.stats", "collections", "functools", "itertools",
    "dataclasses", "typing",
})

# Blocked function calls
BLOCKED_CALLS = frozenset({
    "open", "exec", "eval", "compile", "__import__",
    "getattr", "setattr", "delattr", "globals", "locals",
    "breakpoint", "input", "print",  # print is noise in factors
})

# Blocked module attribute access
BLOCKED_MODULES = frozenset({
    "os", "sys", "subprocess", "socket", "http", "urllib",
    "shutil", "pathlib", "importlib", "pickle", "shelve",
    "ctypes", "signal", "threading", "multiprocessing",
})


class SafetyViolation:
    def __init__(self, line: int, col: int, message: str):
        self.line = line
        self.col = col
        self.message = message

    def __str__(self) -> str:
        return f"Line {self.line}: {self.message}"


def check_factor_code(source: str) -> list[SafetyViolation]:
    """Check factor source code for safety violations.

    Returns list of violations. Empty list = safe to load.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return [SafetyViolation(e.lineno or 0, 0, f"Syntax error: {e.msg}")]

    violations: list[SafetyViolation] = []

    for node in ast.walk(tree):
        # Check imports
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root not in ALLOWED_IMPORTS:
                    violations.append(SafetyViolation(
                        node.lineno, node.col_offset,
                        f"Blocked import: {alias.name} (allowed: {', '.join(sorted(ALLOWED_IMPORTS))})",
                    ))

        elif isinstance(node, ast.ImportFrom):
            if node.module:
                root = node.module.split(".")[0]
                if root not in ALLOWED_IMPORTS:
                    violations.append(SafetyViolation(
                        node.lineno, node.col_offset,
                        f"Blocked import from: {node.module}",
                    ))

        # Check function calls
        elif isinstance(node, ast.Call):
            func_name = ""
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                func_name = node.func.attr
                # Check module access like os.system()
                if isinstance(node.func.value, ast.Name):
                    if node.func.value.id in BLOCKED_MODULES:
                        violations.append(SafetyViolation(
                            node.lineno, node.col_offset,
                            f"Blocked module access: {node.func.value.id}.{func_name}",
                        ))

            if func_name in BLOCKED_CALLS:
                violations.append(SafetyViolation(
                    node.lineno, node.col_offset,
                    f"Blocked function call: {func_name}()",
                ))

        # Check dunder access (except safe ones)
        elif isinstance(node, ast.Attribute):
            if node.attr.startswith("__") and node.attr.endswith("__"):
                safe_dunders = {"__init__", "__name__", "__doc__", "__class__"}
                if node.attr not in safe_dunders:
                    violations.append(SafetyViolation(
                        node.lineno, node.col_offset,
                        f"Blocked dunder access: {node.attr}",
                    ))

    return violations


def is_safe(source: str) -> tuple[bool, list[str]]:
    """Convenience wrapper. Returns (safe, list_of_violation_strings)."""
    violations = check_factor_code(source)
    return len(violations) == 0, [str(v) for v in violations]
