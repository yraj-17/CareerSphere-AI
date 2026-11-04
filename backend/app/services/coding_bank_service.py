"""
Seeding and verification of the curated coding problem bank.

seed_bank(db)        Idempotent upsert keyed by slug. Each problem's stored content hash
                     covers everything that affects correctness (statement, tests and
                     their oracle outputs, checker, limits, harness, starters, references,
                     wrong solutions). Unchanged problems are left untouched; a changed
                     problem is updated and its verification is cleared, so it is not
                     served again until it is re-verified. Bank problems that were removed
                     are deactivated (never deleted: submissions reference them).

verify_bank(db)      Runs coding_service.verify_problem on real Judge0 for each problem:
                     references Accepted, known-wrong solutions rejected, starters run.
                     Only verified problems are ever assigned to interviews.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from app.data.coding_bank import CATEGORIES, DIFFICULTIES, ProblemSpec, all_problems
from app.data.coding_languages import LANGUAGE_BY_KEY, MAX_CPU_TIME_SECONDS, MAX_MEMORY_KB
from app.data.interview_roles import ROLE_BY_SLUG
from app.db.models import CodingProblem, CodingTestCase
from app.services import coding_harness
from app.services.coding_checkers import validate_checker_config

logger = logging.getLogger(__name__)

CATEGORY_KIND = {"sql": "sql"}  # every other category is answered as a coding slot
# Judge0 truncates stdout at 64 KiB (coding_verdicts.JUDGE0_STDOUT_LIMIT_BYTES); expected
# outputs stay below this margin so a correct program is never cut off.
MAX_EXPECTED_OUTPUT_BYTES = 60_000


def practical_kind(category: str) -> str:
    return CATEGORY_KIND.get(category, "coding")


# ---------------------------------------------------------------------------
# Validation (pure; also used by tests)
# ---------------------------------------------------------------------------


def validate_spec(spec: ProblemSpec) -> list[str]:
    errors: list[str] = []
    where = spec.slug
    if spec.category not in CATEGORIES:
        errors.append(f"{where}: unknown category {spec.category}")
    if spec.difficulty not in DIFFICULTIES:
        errors.append(f"{where}: unknown difficulty {spec.difficulty}")
    for field_name in ("title", "summary", "statement", "input_format", "output_format", "constraints"):
        if not str(getattr(spec, field_name) or "").strip():
            errors.append(f"{where}: {field_name} is empty")
    if not spec.languages:
        errors.append(f"{where}: no languages")
    for language in spec.languages:
        if language not in LANGUAGE_BY_KEY:
            errors.append(f"{where}: unknown language {language}")
        if language not in spec.reference_solutions:
            errors.append(f"{where}: missing reference solution for {language}")
        if language not in spec.starter_code:
            errors.append(f"{where}: missing starter code for {language}")
    for language in [*spec.reference_solutions, *spec.starter_code]:
        if language not in spec.languages:
            errors.append(f"{where}: {language} code given but not declared")
    if not spec.wrong_solutions:
        errors.append(f"{where}: needs at least one known-wrong solution")
    for language, _source, note in spec.wrong_solutions:
        if language not in spec.languages or not note:
            errors.append(f"{where}: invalid wrong solution ({language})")
    if not spec.samples:
        errors.append(f"{where}: needs at least one sample test")
    if not any(t.hidden for t in spec.tests):
        errors.append(f"{where}: needs at least one hidden test")
    if not spec.roles:
        errors.append(f"{where}: no target roles")
    for role_slug in spec.roles:
        role = ROLE_BY_SLUG.get(role_slug)
        if role is None:
            errors.append(f"{where}: unknown role {role_slug}")
            continue
        kind = practical_kind(spec.category)
        if not any(c.id in spec.competencies and c.practical == kind for c in role.competencies):
            errors.append(f"{where}: role {role_slug} has no {kind} competency among {spec.competencies}")
        if kind == "coding" and role.languages and not set(role.languages) & set(spec.languages):
            errors.append(f"{where}: role {role_slug} cannot use any of {spec.languages}")
    if not 0 < spec.time_limit_seconds <= MAX_CPU_TIME_SECONDS:
        errors.append(f"{where}: time limit out of range")
    if not 0 < spec.memory_limit_kb <= MAX_MEMORY_KB:
        errors.append(f"{where}: memory limit out of range")
    try:
        validate_checker_config(spec.checker)
    except ValueError as exc:
        errors.append(f"{where}: {exc}")
    for language, source in {**spec.reference_solutions, **spec.starter_code}.items():
        try:
            coding_harness.validate_source(language, source)
        except coding_harness.HarnessError as exc:
            errors.append(f"{where}: {language}: {exc}")
    if spec.harness and spec.harness.get("type") == "bash_workspace":
        for test in spec.tests:
            try:
                coding_harness.parse_workspace_input(test.input)
            except coding_harness.HarnessError as exc:
                errors.append(f"{where}: {exc}")
    return errors


def validate_bank(specs: Iterable[ProblemSpec]) -> list[str]:
    specs = list(specs)
    errors: list[str] = []
    slugs = [s.slug for s in specs]
    for slug in {s for s in slugs if slugs.count(s) > 1}:
        errors.append(f"duplicate slug {slug}")
    for spec in specs:
        errors.extend(validate_spec(spec))
    return errors


# ---------------------------------------------------------------------------
# Seeding
# ---------------------------------------------------------------------------


def expected_outputs(spec: ProblemSpec) -> list[str]:
    return [spec.oracle(test.input) for test in spec.tests]


def _examples(spec: ProblemSpec, outputs: list[str]) -> list[dict]:
    return [
        {"input": test.input, "output": output, "explanation": test.explanation or None}
        for test, output in zip(spec.tests, outputs)
        if not test.hidden
    ]


def _content(spec: ProblemSpec, outputs: list[str]) -> dict:
    return {
        "title": spec.title,
        "category": spec.category,
        "difficulty": spec.difficulty,
        "statement": spec.statement,
        "input_format": spec.input_format,
        "output_format": spec.output_format,
        "constraints": spec.constraints,
        "instructions": spec.instructions or None,
        "examples": _examples(spec, outputs),
        "starter_code": dict(spec.starter_code),
        "languages": list(spec.languages),
        "checker": dict(spec.checker),
        "time_limit_seconds": spec.time_limit_seconds,
        "memory_limit_kb": spec.memory_limit_kb,
        "roles": list(spec.roles),
        "competencies": list(spec.competencies),
        "estimated_minutes": spec.estimated_minutes,
        "reference_solutions": dict(spec.reference_solutions),
        "harness": dict(spec.harness) if spec.harness else None,
    }


def content_hash(spec: ProblemSpec, outputs: Optional[list[str]] = None) -> str:
    outputs = outputs if outputs is not None else expected_outputs(spec)
    payload = {
        **_content(spec, outputs),
        "tests": [[t.input, o, t.hidden, t.weight] for t, o in zip(spec.tests, outputs)],
        "wrong_solutions": [list(w) for w in spec.wrong_solutions],
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def seed_bank(db: Session, specs: Optional[Iterable[ProblemSpec]] = None) -> dict:
    """Seed the given problems (default: the whole bank). Only a full-bank seed deactivates removed problems."""
    full_bank = specs is None
    specs = list(specs if specs is not None else all_problems())
    errors = validate_bank(specs)
    if errors:
        raise ValueError("Problem bank is invalid:\n" + "\n".join(errors))

    created, updated, unchanged = [], [], []
    for spec in specs:
        outputs = expected_outputs(spec)
        too_big = [i for i, o in enumerate(outputs, start=1) if len(o.encode("utf-8")) > MAX_EXPECTED_OUTPUT_BYTES]
        if too_big:
            raise ValueError(f"{spec.slug}: expected output of test(s) {too_big} exceeds {MAX_EXPECTED_OUTPUT_BYTES} bytes")
        digest = content_hash(spec, outputs)
        problem = db.query(CodingProblem).filter(CodingProblem.slug == spec.slug).first()
        if problem is not None and problem.content_hash == digest and problem.is_active:
            unchanged.append(spec.slug)
            continue
        if problem is None:
            problem = CodingProblem(slug=spec.slug)
            db.add(problem)
            created.append(spec.slug)
        else:
            updated.append(spec.slug)
            for test in list(problem.test_cases):
                db.delete(test)
            db.flush()
        for key, value in _content(spec, outputs).items():
            setattr(problem, key, value)
        problem.content_hash = digest
        problem.is_active = True
        problem.verified_at = None  # new or changed content must be verified on Judge0 again
        problem.verification = None
        db.flush()
        for ordinal, (test, output) in enumerate(zip(spec.tests, outputs), start=1):
            db.add(CodingTestCase(
                problem_id=problem.id, ordinal=ordinal, input=test.input, expected_output=output,
                is_hidden=test.hidden, weight=test.weight, is_required=True,
            ))
    deactivated = []
    if full_bank:
        bank_slugs = {s.slug for s in specs}
        for problem in db.query(CodingProblem).filter(CodingProblem.is_active.is_(True)).all():
            if problem.content_hash is not None and problem.slug not in bank_slugs:
                problem.is_active = False
                deactivated.append(problem.slug)
    db.commit()
    return {"created": created, "updated": updated, "unchanged": unchanged, "deactivated": deactivated}


# ---------------------------------------------------------------------------
# Verification on Judge0
# ---------------------------------------------------------------------------


async def verify_bank(
    db: Session,
    specs: Optional[Iterable[ProblemSpec]] = None,
    *,
    only: Optional[set[str]] = None,
    force: bool = False,
) -> dict[str, dict]:
    from app.services.coding_service import verify_problem

    report: dict[str, dict] = {}
    for spec in specs if specs is not None else all_problems():
        if only and spec.slug not in only:
            continue
        problem = db.query(CodingProblem).filter(CodingProblem.slug == spec.slug).first()
        if problem is None:
            report[spec.slug] = {"verified": False, "error": "not seeded"}
            continue
        if problem.verified_at is not None and not force:
            report[spec.slug] = {**(problem.verification or {}), "skipped": True}
            continue
        try:
            report[spec.slug] = await verify_problem(db, problem, wrong_solutions=spec.wrong_solutions, check_starters=True)
        except Exception as exc:  # report and continue with the rest of the bank
            db.rollback()
            logger.warning("[CodingBank] verification of %s failed: %s", spec.slug, type(exc).__name__)
            report[spec.slug] = {"verified": False, "error": f"{type(exc).__name__}: {exc}"}
    return report
