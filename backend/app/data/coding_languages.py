"""
Supported coding-assessment languages.

Configuration, not code: adding a language means adding an entry here (and
starter templates in the problem bank). Judge0 language IDs are resolved at
runtime from the server's /languages list by name prefix, and the label shown
to candidates is the exact name Judge0 reports — so the UI can never advertise
a runtime version the execution server does not actually provide.

Versions verified on the CareerSphere Judge0 CE 1.13.1 instance (Phase 1):
  C++ (GCC 9.2.0) id 54, compiled with -std=c++17
  Java (OpenJDK 13.0.1) id 62
  Python (3.8.1) id 71
  JavaScript (Node.js 12.14.0) id 63
  Bash (5.0.0) id 46                 — coreutils, GNU sed 4.7, mawk (no gawk, no bc)
  SQL (SQLite 3.27.2) id 82          — runs `cat script.sql | sqlite3 db.sqlite`; stdin is
                                       not used, so test data is built into the program
                                       (see coding_harness)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class CodingLanguage:
    key: str
    judge0_name_prefix: str  # matched against Judge0's /languages names
    fallback_judge0_id: int  # used only if /languages cannot be read
    fallback_label: str
    monaco_language: str
    compiler_options: Optional[str] = None
    # A problem's time limit is the C++ baseline; slower runtimes get a fixed multiplier
    # (JVM/interpreter start-up), capped at the Judge0 server ceiling.
    time_multiplier: float = 1.0
    notes: str = ""


LANGUAGES: tuple[CodingLanguage, ...] = (
    CodingLanguage("CPP", "C++ (GCC", 54, "C++17 (GCC 9.2.0)", "cpp", compiler_options="-std=c++17 -O2"),
    # Judge0 compiles Java as Main.java, so the public class must be named Main.
    CodingLanguage("JAVA", "Java (", 62, "Java 13 (OpenJDK 13.0.1)", "java", time_multiplier=2.0, notes="The public class must be named Main."),
    CodingLanguage("PYTHON", "Python (3", 71, "Python 3.8.1", "python", time_multiplier=3.0),
    CodingLanguage("JAVASCRIPT", "JavaScript (Node", 63, "JavaScript (Node.js 12.14.0)", "javascript", time_multiplier=2.0),
    # Problem-specific runtimes: only problems that declare them offer them.
    CodingLanguage("BASH", "Bash (", 46, "Bash (5.0.0)", "shell", time_multiplier=1.0,
                   notes="awk is mawk (no gawk extensions); bc is not installed."),
    CodingLanguage("SQLITE", "SQL (SQLite", 82, "SQL (SQLite 3.27.2)", "sql", time_multiplier=1.0,
                   notes="SQLite dialect. Write SQL statements only; dot-commands are not allowed."),
)

# General-purpose languages a candidate may choose for algorithmic problems.
GENERAL_LANGUAGES: tuple[str, ...] = ("CPP", "JAVA", "PYTHON", "JAVASCRIPT")

LANGUAGE_BY_KEY: dict[str, CodingLanguage] = {lang.key: lang for lang in LANGUAGES}

# Judge0 host ceilings (MAX_CPU_TIME_LIMIT / MAX_WALL_TIME_LIMIT / MAX_MEMORY_LIMIT in judge0.conf).
MAX_CPU_TIME_SECONDS = 10.0
MAX_WALL_TIME_SECONDS = 15.0
MAX_MEMORY_KB = 512_000
