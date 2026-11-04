"""
Program construction for Judge0 executions.

For most languages the candidate's source runs as-is with the test input on stdin.
Two runtimes need the backend to build the program around the candidate's code:

SQLITE  Judge0 runs `cat script.sql | sqlite3 db.sqlite`, so stdin is not read. Each
        test's input is its schema + seed data (SQL), and the executed script is
            output settings  +  test setup SQL  +  candidate SQL
        Every execution gets a fresh, empty SQLite database inside the Judge0 sandbox;
        nothing ever touches the CareerSphere PostgreSQL database. Candidate SQL may not
        contain sqlite3 dot-commands (only SQL statements are assessed).

BASH    Plain problems: the script runs as-is with the test input on stdin.
        Workspace problems (harness {"type": "bash_workspace"}): the test input is JSON
            {"files": {"relative/path": "content", ...}, "stdin": "..."}
        The harness creates those files in an empty ./workspace directory, runs the
        candidate script there with the test stdin, then prints a listing of the final
        workspace (path and size) after the line "== workspace ==", so file operations
        are verified from the real filesystem rather than from the script's own output.

Stderr line numbers for SQL are shifted back so they refer to the candidate's own lines.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Optional

SQL_PRELUDE = ".bail on\n.headers off\n.mode list\n.nullvalue NULL\nPRAGMA foreign_keys = ON;\n"
WORKSPACE_MARKER = "== workspace =="
_SQL_DOT_COMMAND = re.compile(r"^\s*\.", re.MULTILINE)
_SQL_LINE = re.compile(r"(near line |line )(\d+)")
_SAFE_PATH = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_. \-/]*$")  # spaces allowed: names are always single-quoted


class HarnessError(ValueError):
    """The candidate's program or a test fixture is not acceptable for this runtime."""


@dataclass(frozen=True)
class Program:
    source_code: str
    stdin: str
    line_offset: int = 0  # lines the backend placed before the candidate's code


def _quote(text: str) -> str:
    """Single-quote a string for bash (works for any content without NUL bytes)."""
    if "\0" in text:
        raise HarnessError("Content may not contain NUL bytes.")
    return "'" + text.replace("'", "'\\''") + "'"


def validate_source(language: str, source: str) -> None:
    if language == "SQLITE" and _SQL_DOT_COMMAND.search(source or ""):
        raise HarnessError("sqlite3 dot-commands (lines starting with '.') are not allowed. Submit SQL statements only.")


def validate_custom_input(language: str, custom_input: Optional[str]) -> None:
    if language == "SQLITE" and custom_input and _SQL_DOT_COMMAND.search(custom_input):
        raise HarnessError("Custom setup SQL may not contain sqlite3 dot-commands.")


def parse_workspace_input(test_input: str) -> tuple[dict[str, str], str]:
    try:
        data = json.loads(test_input)
    except json.JSONDecodeError as exc:
        raise HarnessError("Workspace input must be JSON: {\"files\": {...}, \"stdin\": \"...\"}.") from exc
    if not isinstance(data, dict):
        raise HarnessError("Workspace input must be a JSON object.")
    files = data.get("files") or {}
    stdin = data.get("stdin") or ""
    if not isinstance(files, dict) or not isinstance(stdin, str):
        raise HarnessError("Workspace input needs a 'files' object and a 'stdin' string.")
    for path, content in files.items():
        if not isinstance(path, str) or not isinstance(content, str):
            raise HarnessError("Workspace file names and contents must be strings.")
        if not _SAFE_PATH.match(path) or ".." in path.split("/") or len(path) > 200:
            raise HarnessError(f"Unsafe workspace path: {path!r}")
    if len(files) > 200:
        raise HarnessError("Too many workspace files.")
    return files, stdin


def _bash_workspace(source: str, test_input: str) -> Program:
    files, stdin = parse_workspace_input(test_input)
    lines = ['__root="$PWD"', "mkdir -p workspace && cd workspace || exit 97"]
    for path, content in sorted(files.items()):
        directory = path.rsplit("/", 1)[0] if "/" in path else ""
        if directory:
            lines.append(f"mkdir -p {_quote(directory)}")
        lines.append(f"printf '%s' {_quote(content)} > {_quote(path)}")
    lines += [
        f'printf \'%s\' {_quote(source)} > "$__root/solution.sh"',
        'bash "$__root/solution.sh"',
        "__status=$?",
        f"echo {_quote(WORKSPACE_MARKER)}",
        "find . -type f | LC_ALL=C sort | while IFS= read -r __f; do "
        "printf '%s %s\\n' \"${__f#./}\" \"$(wc -c < \"$__f\" | tr -d ' ')\"; done",
        "exit $__status",
    ]
    return Program(source_code="\n".join(lines) + "\n", stdin=stdin)


def build_program(language: str, source: str, test_input: str, harness: Optional[dict] = None) -> Program:
    """The exact program and stdin Judge0 executes for one test (or custom input)."""
    if language == "SQLITE":
        validate_source(language, source)
        head = SQL_PRELUDE + (test_input or "").rstrip("\n") + "\n"
        # The trailing ';' completes a final statement written without one; an empty
        # statement is harmless in sqlite3.
        return Program(source_code=head + source.rstrip("\n") + "\n;\n", stdin="", line_offset=head.count("\n"))
    if language == "BASH" and (harness or {}).get("type") == "bash_workspace":
        return _bash_workspace(source, test_input)
    return Program(source_code=source, stdin=test_input or "")


def present_stderr(language: str, stderr: str, line_offset: int) -> str:
    """Make diagnostics refer to the candidate's own line numbers."""
    if not stderr or language != "SQLITE" or line_offset <= 0:
        return stderr

    def shift(match: re.Match) -> str:
        line = int(match.group(2)) - line_offset
        return f"{match.group(1)}{line}" if line >= 1 else match.group(0)

    return _SQL_LINE.sub(shift, stderr)
