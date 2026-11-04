"""
Curated coding problem bank (original problems written for CareerSphere AI).

Each problem is versioned Python data. The bank is seeded into coding_problems by
`python -m scripts.seed_coding_bank` (idempotent: keyed by slug, with a content hash;
any change to a problem clears its verification).

Where expected outputs come from
--------------------------------
Expected outputs are never hand-typed and never produced by an LLM. Each problem
has an `oracle` — trusted Python that computes the output for a test input — and
the seeding step stores oracle(input) as the expected output. A problem is only
published (verified_at set) after real Judge0 execution shows that:

  * every reference solution, in every declared language, is Accepted on every test
    (so independent implementations agree with the stored outputs and the checker);
  * every known-wrong solution is rejected (so the tests actually discriminate);
  * every starter template compiles and runs without a compilation or judge error.

Hidden tests and reference solutions are backend-only: the API never returns them.
"""

from __future__ import annotations

import contextlib
import io
import sys
from dataclasses import dataclass, field
from typing import Callable, Optional

CATEGORIES = ("dsa", "frontend", "backend", "sql", "bash")
DIFFICULTIES = ("EASY", "MEDIUM", "HARD")


@dataclass(frozen=True)
class Test:
    input: str
    hidden: bool = True
    weight: float = 1.0
    explanation: str = ""  # shown for sample tests


@dataclass(frozen=True)
class ProblemSpec:
    slug: str
    title: str
    category: str
    difficulty: str
    summary: str  # one line, used as the interview question text
    roles: tuple[str, ...]
    competencies: tuple[str, ...]
    statement: str
    input_format: str
    output_format: str
    constraints: str
    languages: tuple[str, ...]
    starter_code: dict[str, str]
    reference_solutions: dict[str, str]
    # Programs that must be rejected: (language, source, what is wrong with it).
    wrong_solutions: tuple[tuple[str, str, str], ...]
    tests: tuple[Test, ...]
    oracle: Callable[[str], str]
    checker: dict = field(default_factory=lambda: {"mode": "whitespace"})
    time_limit_seconds: float = 1.0
    memory_limit_kb: int = 128_000
    estimated_minutes: int = 20
    harness: Optional[dict] = None
    instructions: str = ""

    @property
    def samples(self) -> list[Test]:
        return [t for t in self.tests if not t.hidden]


def python_oracle(source: str) -> Callable[[str], str]:
    """Run trusted Python solution source in-process with the given stdin."""
    code = compile(source, "<oracle>", "exec")

    def run(stdin: str) -> str:
        out = io.StringIO()
        saved_stdin = sys.stdin
        sys.stdin = io.TextIOWrapper(io.BytesIO(stdin.encode("utf-8")), encoding="utf-8")  # has .buffer
        try:
            with contextlib.redirect_stdout(out):
                exec(code, {"__name__": "__main__"})
        finally:
            sys.stdin = saved_stdin
        return out.getvalue()

    return run


def all_problems() -> list[ProblemSpec]:
    from app.data.coding_bank import backend, bash, dsa, frontend, sql

    return [*dsa.PROBLEMS, *frontend.PROBLEMS, *backend.PROBLEMS, *sql.PROBLEMS, *bash.PROBLEMS]
