"""
Deterministic output checkers for coding assessments.

The checker is configured per problem (backend-controlled, never by the client):

    {"mode": "exact"}                          byte-exact after CRLF→LF normalisation
    {"mode": "whitespace"}                     per-line trailing whitespace and trailing blank lines ignored (default)
    {"mode": "tokens"}                         same whitespace-separated tokens in the same order
    {"mode": "float", "tolerance": 1e-6}       tokens; numbers equal within absolute OR relative tolerance
    {"mode": "unordered_lines"}                same multiset of (whitespace-normalised) lines, any order
    {"mode": "unordered_tokens"}               same multiset of tokens, any order
    {"mode": "custom", "validator": "<name>", "params": {...}}
                                               a registered Python validator (trusted backend code)

Every checker returns (passed, reason). The reason is generic and safe to show for
public tests; for hidden tests callers must not expose it alongside any data.
"""

from __future__ import annotations

import math
from collections import Counter
from typing import Callable, Optional

CheckResult = tuple[bool, str]
DEFAULT_CHECKER = {"mode": "whitespace"}
MODES = {"exact", "whitespace", "tokens", "float", "unordered_lines", "unordered_tokens", "custom"}


def _normalise_newlines(text: str) -> str:
    return (text or "").replace("\r\n", "\n").replace("\r", "\n")


def _lines(text: str) -> list[str]:
    lines = [line.rstrip() for line in _normalise_newlines(text).split("\n")]
    while lines and lines[-1] == "":
        lines.pop()
    return lines


def _tokens(text: str) -> list[str]:
    return _normalise_newlines(text).split()


def _as_number(token: str) -> Optional[float]:
    try:
        value = float(token)
    except ValueError:
        return None
    return value if math.isfinite(value) else None


def check_exact(expected: str, actual: str, **_) -> CheckResult:
    ok = _normalise_newlines(expected) == _normalise_newlines(actual)
    return ok, "" if ok else "Output does not match exactly."


def check_whitespace(expected: str, actual: str, **_) -> CheckResult:
    ok = _lines(expected) == _lines(actual)
    return ok, "" if ok else "Output differs from the expected output."


def check_tokens(expected: str, actual: str, **_) -> CheckResult:
    ok = _tokens(expected) == _tokens(actual)
    return ok, "" if ok else "Output differs from the expected output."


def check_float(expected: str, actual: str, tolerance: float = 1e-6, **_) -> CheckResult:
    exp, act = _tokens(expected), _tokens(actual)
    if len(exp) != len(act):
        return False, "Output has a different number of values than expected."
    for e, a in zip(exp, act):
        en, an = _as_number(e), _as_number(a)
        if en is None or an is None:
            if e != a:
                return False, "Output differs from the expected output."
            continue
        if not (abs(en - an) <= tolerance or abs(en - an) <= tolerance * max(abs(en), abs(an))):
            return False, f"A value differs by more than the allowed tolerance ({tolerance:g})."
    return True, ""


def check_unordered_lines(expected: str, actual: str, **_) -> CheckResult:
    def norm(text: str) -> Counter:
        return Counter(" ".join(line.split()) for line in _lines(text) if line.strip())

    ok = norm(expected) == norm(actual)
    return ok, "" if ok else "Output lines differ from the expected set of lines."


def check_unordered_tokens(expected: str, actual: str, **_) -> CheckResult:
    ok = Counter(_tokens(expected)) == Counter(_tokens(actual))
    return ok, "" if ok else "Output values differ from the expected set of values."


# ---------------------------------------------------------------------------
# Problem-specific validators: (stdin, expected, actual, params) -> CheckResult
# ---------------------------------------------------------------------------

Validator = Callable[[str, str, str, dict], CheckResult]
VALIDATORS: dict[str, Validator] = {}


def validator(name: str):
    def register(fn: Validator) -> Validator:
        VALIDATORS[name] = fn
        return fn

    return register


@validator("two_sum_indices")
def _two_sum_indices(stdin: str, expected: str, actual: str, params: dict) -> CheckResult:
    """
    Any valid answer is accepted. stdin: n, then n integers, then target.
    The candidate prints two distinct 0-based indices i j with nums[i] + nums[j] == target.
    """
    data = _tokens(stdin)
    try:
        n = int(data[0])
        nums = [int(x) for x in data[1 : 1 + n]]
        target = int(data[1 + n])
        answer = [int(x) for x in _tokens(actual)]
    except (IndexError, ValueError):
        return False, "Output must be two integer indices."
    if len(answer) != 2:
        return False, "Output must be exactly two indices."
    i, j = answer
    if i == j or not (0 <= i < n and 0 <= j < n):
        return False, "Indices must be distinct and within range."
    ok = nums[i] + nums[j] == target
    return ok, "" if ok else "The two values do not add up to the target."


_MODE_FUNCTIONS = {
    "exact": check_exact,
    "whitespace": check_whitespace,
    "tokens": check_tokens,
    "float": check_float,
    "unordered_lines": check_unordered_lines,
    "unordered_tokens": check_unordered_tokens,
}


def validate_checker_config(config: Optional[dict]) -> dict:
    """Normalise and validate a problem's checker config (raises ValueError)."""
    config = dict(config or DEFAULT_CHECKER)
    mode = config.get("mode", "whitespace")
    if mode not in MODES:
        raise ValueError(f"Unknown checker mode: {mode}")
    if mode == "float":
        tolerance = float(config.get("tolerance", 1e-6))
        if not (0 < tolerance < 1):
            raise ValueError("Float tolerance must be between 0 and 1.")
        config["tolerance"] = tolerance
    if mode == "custom" and config.get("validator") not in VALIDATORS:
        raise ValueError(f"Unknown validator: {config.get('validator')}")
    config["mode"] = mode
    return config


def run_checker(config: Optional[dict], *, stdin: str, expected: str, actual: str) -> CheckResult:
    config = validate_checker_config(config)
    mode = config["mode"]
    if mode == "custom":
        try:
            return VALIDATORS[config["validator"]](stdin, expected, actual, config.get("params") or {})
        except Exception:  # a validator bug must never crash judging; treat as not accepted
            return False, "Output could not be validated."
    kwargs = {"tolerance": config["tolerance"]} if mode == "float" else {}
    return _MODE_FUNCTIONS[mode](expected, actual, **kwargs)
