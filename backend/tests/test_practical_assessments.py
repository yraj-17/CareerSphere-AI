"""
Phase 3 — problem bank and role-specific practical assessments.

Bank integrity and seeding, SQL/Bash program harness, deterministic network
calculations, curated scenarios, practical supply in the blueprint, problem
selection, and the calculation / scenario answer flows through the interview API.
Real execution of the bank on Judge0 is covered by `python -m scripts.seed_coding_bank --verify`.
"""

from __future__ import annotations

import ipaddress
import json
import math
import uuid
from collections import Counter
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.data import practical_scenarios as scenarios
from app.data.coding_bank import ProblemSpec, Test, all_problems, python_oracle
from app.data.coding_languages import LANGUAGE_BY_KEY
from app.data.interview_roles import ROLE_BY_SLUG
from app.db.models import CodingProblem, CodingTestCase, InterviewQuestion
from app.db.session import SessionLocal
from app.main import app
from app.services import coding_bank_service as bank
from app.services import coding_harness as harness
from app.services import interview_blueprint as blueprints
from app.services import interview_role_service as roles
from app.services import interview_service as svc
from app.services import network_calc as calc
from app.services import practical_service as practicals
from tests.test_coding_assessment import FakeJudge0, judge  # noqa: F401 — fixture
from tests.test_interviews import FakeModel, model, other_user, user  # noqa: F401 — fixtures

client = TestClient(app)
PROBLEMS = all_problems()


# ---------------------------------------------------------------------------
# Problem bank
# ---------------------------------------------------------------------------


def test_bank_is_valid_and_has_the_required_distribution():
    assert bank.validate_bank(PROBLEMS) == []
    assert Counter(p.category for p in PROBLEMS) == {"dsa": 8, "frontend": 4, "backend": 4, "sql": 4, "bash": 4}
    assert len({p.slug for p in PROBLEMS}) == 24
    dsa = [p for p in PROBLEMS if p.category == "dsa"]
    assert {p.difficulty for p in dsa} == {"EASY", "MEDIUM"}  # fresher-SDE mix


@pytest.mark.parametrize("spec", PROBLEMS, ids=lambda p: p.slug)
def test_every_problem_is_complete(spec: ProblemSpec):
    for field in ("title", "summary", "statement", "input_format", "output_format", "constraints"):
        assert getattr(spec, field).strip()
    assert spec.roles and spec.competencies and spec.estimated_minutes > 0
    assert spec.samples and any(t.hidden for t in spec.tests)
    assert spec.wrong_solutions
    assert set(spec.reference_solutions) == set(spec.starter_code) == set(spec.languages)
    assert 0 < spec.time_limit_seconds <= 10 and 0 < spec.memory_limit_kb <= 512_000
    assert "leetcode" not in (spec.statement + spec.title).lower()
    outputs = bank.expected_outputs(spec)
    assert all(o.strip() for o, t in zip(outputs, spec.tests) if not t.hidden), "samples must show an output"
    # Judge0 truncates stdout at 64 KiB: every expected output stays below the bank margin.
    assert max(len(o.encode("utf-8")) for o in outputs) <= bank.MAX_EXPECTED_OUTPUT_BYTES


def test_languages_match_what_each_category_can_really_run():
    general = {"CPP", "JAVA", "PYTHON", "JAVASCRIPT"}
    for spec in PROBLEMS:
        expected = {"dsa": general, "backend": general, "frontend": {"JAVASCRIPT"}, "sql": {"SQLITE"}, "bash": {"BASH"}}[spec.category]
        assert set(spec.languages) == expected, spec.slug
    assert LANGUAGE_BY_KEY["JAVA"].fallback_label == "Java 13 (OpenJDK 13.0.1)"
    assert LANGUAGE_BY_KEY["SQLITE"].fallback_label == "SQL (SQLite 3.27.2)"
    assert LANGUAGE_BY_KEY["BASH"].fallback_label == "Bash (5.0.0)"


@pytest.mark.parametrize(
    "spec", [p for p in PROBLEMS if any(w[0] == "PYTHON" and "time limit" not in w[2] for w in p.wrong_solutions)],
    ids=lambda p: p.slug,
)
def test_tests_reject_known_wrong_python_solutions(spec: ProblemSpec):
    expected = bank.expected_outputs(spec)
    for language, source, note in spec.wrong_solutions:
        if language != "PYTHON" or "time limit" in note:
            continue
        wrong = python_oracle(source)
        assert any(wrong(t.input).split() != e.split() for t, e in zip(spec.tests, expected)), note


def test_truncated_output_is_reported_clearly():
    from app.services import coding_verdicts as verdicts
    from app.services.judge0_client import ExecutionResult

    import base64

    stdout = base64.b64encode(b"x" * 65536).decode()
    result = ExecutionResult.from_api({"token": "t", "status": {"id": 3, "description": "Accepted"}, "stdout": stdout})
    outcome = verdicts.evaluate_test(result, ordinal=1, stdin="", expected="y", checker=None, memory_limit_kb=1000)
    assert outcome.verdict == verdicts.WRONG_ANSWER and "64 KB" in outcome.reason


def test_oracles_are_deterministic():
    for spec in PROBLEMS:
        assert bank.content_hash(spec) == bank.content_hash(spec)


def _temp_spec(slug: str, statement: str = "Print the sum of two integers.") -> ProblemSpec:
    source = "import sys\nprint(sum(map(int, sys.stdin.read().split())))\n"
    return ProblemSpec(
        slug=slug, title="Temp Sum", category="dsa", difficulty="EASY", summary="Sum two integers.",
        roles=("software-development-engineer",), competencies=("algorithms",), statement=statement,
        input_format="Two integers.", output_format="Their sum.", constraints="Small.",
        languages=("PYTHON",), starter_code={"PYTHON": "print(0)\n"}, reference_solutions={"PYTHON": source},
        wrong_solutions=(("PYTHON", "print(0)\n", "always zero"),),
        tests=(Test("1 2\n", hidden=False), Test("5 7\n")), oracle=python_oracle(source),
    )


def test_seeding_is_idempotent_and_content_changes_force_reverification():
    slug = f"test-temp-{uuid.uuid4().hex[:8]}"
    db = SessionLocal()
    try:
        first = bank.seed_bank(db, [_temp_spec(slug)])
        assert first["created"] == [slug] and first["deactivated"] == []
        problem = db.query(CodingProblem).filter_by(slug=slug).one()
        assert [t.expected_output for t in problem.test_cases] == ["3\n", "12\n"]  # computed by the oracle
        assert [t.is_hidden for t in problem.test_cases] == [False, True]
        assert problem.examples == [{"input": "1 2\n", "output": "3\n", "explanation": None}]

        problem.verified_at = svc.utcnow()
        db.commit()
        again = bank.seed_bank(db, [_temp_spec(slug)])
        assert again["unchanged"] == [slug]
        db.refresh(problem)
        assert problem.verified_at is not None and db.query(CodingTestCase).filter_by(problem_id=problem.id).count() == 2

        changed = bank.seed_bank(db, [_temp_spec(slug, statement="Print the sum of the integers.")])
        assert changed["updated"] == [slug]
        db.refresh(problem)
        assert problem.verified_at is None and problem.verification is None
        assert db.query(CodingProblem).filter_by(slug=slug).count() == 1
    finally:
        db.query(CodingProblem).filter_by(slug=slug).delete()
        db.commit()
        db.close()


def test_invalid_bank_entries_are_rejected():
    spec = _temp_spec("bad")
    broken = ProblemSpec(**{**spec.__dict__, "roles": ("frontend-developer",), "languages": ("PYTHON", "RUST"), "wrong_solutions": ()})
    errors = bank.validate_spec(broken)
    assert any("unknown language RUST" in e for e in errors)
    assert any("known-wrong" in e for e in errors)
    assert any("frontend-developer" in e for e in errors)


# ---------------------------------------------------------------------------
# Program harness (SQLite / Bash)
# ---------------------------------------------------------------------------


def test_sql_program_builds_a_fresh_database_per_test():
    program = harness.build_program("SQLITE", "SELECT name FROM t;", "CREATE TABLE t(name TEXT);\nINSERT INTO t VALUES ('a');\n")
    assert program.stdin == ""
    assert program.source_code.startswith(harness.SQL_PRELUDE)
    assert "INSERT INTO t VALUES ('a');\nSELECT name FROM t;" in program.source_code
    assert program.line_offset == program.source_code.split("SELECT name")[0].count("\n")


def test_sql_dot_commands_are_rejected():
    for source in (".shell cat /etc/passwd", "SELECT 1;\n  .system ls", ".read other.sql"):
        with pytest.raises(harness.HarnessError):
            harness.build_program("SQLITE", source, "")
    harness.validate_source("SQLITE", "SELECT '.not a command' AS x;")  # dots inside SQL are fine


def test_sql_error_lines_refer_to_the_candidate_code():
    program = harness.build_program("SQLITE", "SELECT 1;\nSELEC 2;", "CREATE TABLE t(a);\n")
    stderr = f"Error: near line {program.line_offset + 2}: near \"SELEC\": syntax error"
    assert harness.present_stderr("SQLITE", stderr, program.line_offset).startswith("Error: near line 2:")
    assert harness.present_stderr("PYTHON", "line 9", 5) == "line 9"


def test_bash_workspace_harness_creates_files_and_lists_them():
    spec = {"files": {"my file.txt": "it's here\n", "logs/a.log": "x"}, "stdin": "hello\n"}
    program = harness.build_program("BASH", "echo done", json.dumps(spec), {"type": "bash_workspace"})
    assert program.stdin == "hello\n"
    assert "printf '%s' 'it'\\''s here\n' > 'my file.txt'" in program.source_code
    assert "mkdir -p 'logs'" in program.source_code
    assert harness.WORKSPACE_MARKER in program.source_code
    plain = harness.build_program("BASH", "cat", "abc")
    assert plain.source_code == "cat" and plain.stdin == "abc"


@pytest.mark.parametrize("files", [{"../escape": "x"}, {"/abs": "x"}, {"a/../../b": "x"}, {"bad\nname": "x"}])
def test_bash_workspace_rejects_unsafe_paths(files):
    with pytest.raises(harness.HarnessError):
        harness.parse_workspace_input(json.dumps({"files": files, "stdin": ""}))
    with pytest.raises(harness.HarnessError):
        harness.parse_workspace_input("not json")


# ---------------------------------------------------------------------------
# Deterministic network calculations
# ---------------------------------------------------------------------------


def test_subnet_details_including_boundaries():
    assert calc.subnet_details("192.168.10.77/26") == {
        "network_address": "192.168.10.64", "broadcast_address": "192.168.10.127", "first_host": "192.168.10.65",
        "last_host": "192.168.10.126", "usable_hosts": "62", "subnet_mask": "255.255.255.192",
    }
    assert calc.subnet_details("10.1.2.3/30")["usable_hosts"] == "2"
    slash31 = calc.subnet_details("10.0.0.0/31")
    assert slash31["usable_hosts"] == "2" and slash31["broadcast_address"] == "none" and slash31["first_host"] == "10.0.0.0"
    slash32 = calc.subnet_details("10.0.0.9/32")
    assert slash32["usable_hosts"] == "1" and slash32["first_host"] == slash32["last_host"] == "10.0.0.9"
    assert calc.subnet_details("172.20.200.1/12")["network_address"] == "172.16.0.0"
    assert calc.subnet_details("10.0.0.1/8")["usable_hosts"] == str(2 ** 24 - 2)


def test_subnet_split():
    assert calc.subnet_split("192.168.1.0/24", 5, 3) == {
        "new_prefix": "27", "subnet_count": "8", "hosts_per_subnet": "30",
        "nth_subnet": "192.168.1.64/27", "nth_broadcast": "192.168.1.95",
    }
    assert calc.subnet_split("10.0.0.0/22", 4, 4)["nth_subnet"] == "10.0.3.0/24"
    with pytest.raises(ValueError):
        calc.subnet_split("10.0.0.0/29", 4, 1)


@pytest.mark.parametrize("text,expected", [
    ("192.168.1.1", "private"), ("10.255.255.255", "private"), ("172.31.0.1", "private"), ("172.32.0.1", "public"),
    ("8.8.8.8", "public"), ("256.1.1.1", "invalid"), ("1.2.3", "invalid"), ("1.2.3.4.5", "invalid"),
    ("01.2.3.4", "invalid"), ("1.2.3.4 ", "invalid"), ("1..3.4", "invalid"), ("a.b.c.d", "invalid"), ("", "invalid"),
    ("0.0.0.0", "public"),
])
def test_ip_validation_is_strict(text, expected):
    assert calc.classify(text) == expected


def test_same_subnet():
    assert calc.same_subnet("10.0.5.10", "10.0.5.200", "255.255.255.0") == {"same_subnet": "yes", "network_a": "10.0.5.0"}
    assert calc.same_subnet("10.0.5.10", "10.0.6.1", "255.255.255.0")["same_subnet"] == "no"
    assert calc.same_subnet("10.0.5.10", "10.0.6.1", "255.255.252.0")["same_subnet"] == "yes"


@pytest.mark.parametrize("difficulty", ["EASY", "MEDIUM", "HARD"])
def test_generated_tasks_are_deterministic_and_well_formed(difficulty):
    seen_types = set()
    for i in range(60):
        task = calc.generate_task(f"seed-{i}", difficulty)
        assert task == calc.generate_task(f"seed-{i}", difficulty)
        assert task["type"] in calc.TYPES_BY_DIFFICULTY[difficulty]
        seen_types.add(task["type"])
        answers = calc.expected_answers(task)
        view = calc.public_view(task)
        assert [f["key"] for f in view["fields"]] == list(answers)
        assert view["label"].startswith("Auto-graded")
        if task["type"] == "subnet_details":
            low, high = calc.PREFIX_RANGE[difficulty]
            assert low <= int(task["params"]["cidr"].split("/")[1]) <= high
        if task["type"] == "ip_validation":
            assert {"invalid", "private", "public"} >= set(answers.values()) and "invalid" in answers.values()
        assert calc.grade(task, answers)["score"] == 100
    assert len(seen_types) >= 2
    assert calc.generate_task("x", difficulty, avoid_types=("subnet_details",))["type"] != "subnet_details" or difficulty == "XX"


def test_public_view_never_contains_answers():
    task = {"type": "subnet_details", "params": {"cidr": "192.168.10.77/26"}, "difficulty": "MEDIUM"}
    rendered = json.dumps(calc.public_view(task))
    for value in calc.expected_answers(task).values():
        assert value not in rendered


def test_grading_normalises_reasonable_formats_and_rejects_unknown_fields():
    task = {"type": "subnet_details", "params": {"cidr": "192.168.10.77/26"}, "difficulty": "MEDIUM"}
    answers = {
        "network_address": " 192.168.10.64 ", "broadcast_address": "192.168.10.127", "first_host": "192.168.10.65",
        "last_host": "192.168.10.126", "usable_hosts": "62", "subnet_mask": "/26",
    }
    assert calc.grade(task, answers)["score"] == 100
    partly = calc.grade(task, {**answers, "usable_hosts": "64", "first_host": "192.168.010.65"})
    assert partly["score"] == 67 and partly["correct"] == 4
    assert calc.grade(task, {})["score"] == 0
    with pytest.raises(calc.CalcAnswerError):
        calc.grade(task, {"admin": "1"})
    split = {"type": "subnet_split", "params": {"network": "192.168.1.0/24", "at_least": 5, "index": 3}, "difficulty": "MEDIUM"}
    good = {"new_prefix": "/27", "subnet_count": "8", "hosts_per_subnet": "30", "nth_subnet": "192.168.1.64/27", "nth_broadcast": "192.168.1.95"}
    assert calc.grade(split, good)["score"] == 100
    assert calc.grade(split, {**good, "nth_subnet": "192.168.1.65/27"})["score"] == 80  # host bits set: not a network


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------


def test_scenarios_are_validated_for_their_roles():
    ids = [s.id for s in scenarios.SCENARIOS]
    assert len(ids) == len(set(ids)) >= 24
    for s in scenarios.SCENARIOS:
        assert sum(c.points for c in s.rubric) == 100 and len({c.id for c in s.rubric}) == len(s.rubric)
        assert s.context.strip() and s.tasks
        for slug in s.roles:
            role = ROLE_BY_SLUG[slug]
            assert any(c.id in s.competencies and c.practical == "scenario" for c in role.competencies), (s.id, slug)
    assert scenarios.LABEL == "AI-reviewed — not executed"
    for required in ("net-dns-resolution-failure", "net-static-route-return-path", "devops-container-restart-loop",
                     "devops-k8s-pending-no-endpoints", "devops-ci-pipeline-failure", "sec-auth-log-bruteforce",
                     "sec-code-review-flask", "sec-phishing-account-takeover", "dba-slow-query-plan",
                     "dba-deadlock-transfers", "fe-react-debounced-search"):
        assert required in scenarios.SCENARIO_BY_ID


def test_rubric_score_is_computed_by_the_backend():
    rubric = practicals.scenario_rubric("dba-deadlock-transfers")
    ratings = {c["id"]: 100 for c in rubric}
    assert practicals.rubric_score(rubric, ratings) == 100
    ratings[rubric[0]["id"]] = 0  # 30-point criterion
    assert practicals.rubric_score(rubric, ratings) == 70


# ---------------------------------------------------------------------------
# Supply, blueprint and selection
# ---------------------------------------------------------------------------


def _fake_problem(slug, category, difficulty, roles_, competencies, languages):
    return SimpleNamespace(id=f"id-{slug}", slug=slug, title=slug.title(), category=category, difficulty=difficulty,
                           roles=list(roles_), competencies=list(competencies), languages=list(languages))


FAKE_BANK = [
    _fake_problem("js-easy", "frontend", "EASY", ["frontend-developer"], ["javascript"], ["JAVASCRIPT"]),
    _fake_problem("js-medium", "frontend", "MEDIUM", ["frontend-developer"], ["javascript"], ["JAVASCRIPT"]),
    _fake_problem("sql-q", "sql", "EASY", ["data-analyst", "database-developer"], ["sql-queries"], ["SQLITE"]),
    _fake_problem("dsa-a", "dsa", "MEDIUM", ["software-development-engineer", "java-developer"], ["algorithms", "dsa-java"], ["CPP", "JAVA", "PYTHON"]),
    _fake_problem("dsa-b", "dsa", "MEDIUM", ["software-development-engineer"], ["algorithms"], ["CPP", "JAVA", "PYTHON"]),
]


@pytest.fixture
def fake_bank(monkeypatch):
    bank_list = list(FAKE_BANK)
    monkeypatch.setattr(practicals, "_verified_problems", lambda db: bank_list)
    monkeypatch.setattr(practicals, "_history", lambda db, user_id, exclude: (Counter(), Counter()))
    return bank_list


def _role(slug):
    return roles.from_catalog(ROLE_BY_SLUG[slug], ROLE_BY_SLUG[slug].title)


def test_supply_maps_problems_scenarios_and_calculations_to_roles(fake_bank):
    assert practicals.practical_supply(None, _role("frontend-developer")) >= {("coding", "javascript"), ("scenario", "react")}
    assert ("coding", "javascript") not in practicals.practical_supply(None, _role("backend-developer"))
    assert ("sql", "sql-queries") in practicals.practical_supply(None, _role("data-analyst"))
    assert ("calculation", "ip-subnetting") in practicals.practical_supply(None, _role("network-engineer"))
    assert all(kind != "coding" for kind, _ in practicals.practical_supply(None, _role("network-engineer")))
    custom = roles.ResolvedRole(title="Blockchain Developer", slug=None, canonical_title="Blockchain Developer", source="custom",
                                family="Custom", summary="", competencies=[{"id": "c1", "name": "Core", "focus": "Core", "weight": 1,
                                "practical": "scenario", "description": "", "keywords": []}], practical_kinds=["scenario"], languages=[])
    assert practicals.practical_supply(None, custom) == set()


def test_blueprint_plans_practical_slots_only_where_supplied():
    role = _role("devops-engineer")
    supply = {("scenario", "containers"), ("scenario", "kubernetes")}
    bp = blueprints.build_blueprint(role, interview_type="TECHNICAL", difficulty="MEDIUM", total_questions=6, practical_supply=supply)
    practical = [s for s in bp["question_slots"] if s["kind"] != "question"]
    assert len(practical) == 2 == math.ceil(6 / 3)  # mandatory practical count preserved
    assert all((s["kind"], s["competency_id"]) in supply and s["assessment_available"] for s in practical)
    assert bp["practical_supply_checked"] is True and len(bp["question_slots"]) == 6

    none = blueprints.build_blueprint(role, interview_type="TECHNICAL", difficulty="MEDIUM", total_questions=6, practical_supply=set())
    practical = [s for s in none["question_slots"] if s["kind"] != "question"]
    assert len(practical) == 2 and all(s["assessment_available"] is False for s in practical)

    legacy = blueprints.build_blueprint(role, interview_type="TECHNICAL", difficulty="MEDIUM", total_questions=6)
    assert all("assessment_available" not in s for s in legacy["question_slots"])


def test_focus_areas_are_preferred_within_the_supply():
    role = _role("frontend-developer")
    supply = {("coding", "javascript"), ("scenario", "react"), ("scenario", "html-css")}
    bp = blueprints.build_blueprint(role, interview_type="TECHNICAL", difficulty="EASY", total_questions=3,
                                    focus_areas=["HTML, CSS & Responsive Design"], practical_supply=supply)
    practical = [s for s in bp["question_slots"] if s["kind"] != "question"]
    assert [s["competency_id"] for s in practical] == ["html-css"]


def _session_for(role_slug, difficulty="BEGINNER", questions=()):
    role = _role(role_slug)
    bp = blueprints.build_blueprint(role, interview_type="TECHNICAL", difficulty=difficulty, total_questions=6,
                                    practical_supply=practicals.practical_supply(None, role))
    return SimpleNamespace(id=f"session-{uuid.uuid4().hex[:6]}", blueprint=bp, questions=list(questions))


def test_problem_selection_follows_role_competency_and_difficulty(fake_bank):
    session = _session_for("frontend-developer", "BEGINNER")
    slot = {"position": 2, "kind": "coding", "competency_id": "javascript", "competency": "JavaScript"}
    spec = practicals.assign(None, "user", session, slot)
    assert spec["problem_slug"] == "js-easy" and spec["difficulty_fallback"] is False and spec["languages"] == ["JAVASCRIPT"]

    hard = _session_for("frontend-developer", "ADVANCED")
    spec = practicals.assign(None, "user", hard, slot)
    assert spec["problem_slug"] == "js-medium" and spec["difficulty_fallback"] is True  # nearest difficulty

    taken = SimpleNamespace(problem_id="id-js-easy", practical=None)
    again = practicals.assign(None, "user", _session_for("frontend-developer", "BEGINNER", [taken]), slot)
    assert again["problem_slug"] == "js-medium"  # never repeated within an interview

    java = practicals.assign(None, "user", _session_for("java-developer", "INTERMEDIATE"),
                             {"position": 3, "kind": "coding", "competency_id": "dsa-java", "competency": "DSA in Java"})
    assert java["problem_slug"] == "dsa-a" and java["languages"] == ["JAVA"]


def test_no_unrelated_problem_is_assigned(fake_bank):
    slot = {"position": 2, "kind": "coding", "competency_id": "programming", "competency": "Programming"}
    assert practicals.assign(None, "user", _session_for("backend-developer"), slot) is None


def test_selection_avoids_problems_the_candidate_has_seen(fake_bank, monkeypatch):
    slot = {"position": 2, "kind": "coding", "competency_id": "algorithms", "competency": "Algorithms"}
    picks = Counter(practicals.assign(None, "u", _session_for("software-development-engineer", "INTERMEDIATE"), slot)["problem_slug"]
                    for _ in range(40))
    assert set(picks) == {"dsa-a", "dsa-b"}  # different sessions do not all get the same problem
    monkeypatch.setattr(practicals, "_history", lambda db, user_id, exclude: (Counter({"id-dsa-a": 2}), Counter()))
    assert all(practicals.assign(None, "u", _session_for("software-development-engineer", "INTERMEDIATE"), slot)["problem_slug"] == "dsa-b"
               for _ in range(10))


def test_scenario_and_calculation_assignment(fake_bank):
    session = _session_for("network-engineer", "INTERMEDIATE")
    calc_spec = practicals.assign(None, "u", session, {"position": 2, "kind": "calculation", "competency_id": "ip-subnetting", "competency": "IP"})
    assert calc_spec["type"] == "calculation" and calc_spec["task"]["type"] in calc.TYPES_BY_DIFFICULTY["MEDIUM"]
    scen = practicals.assign(None, "u", session, {"position": 5, "kind": "scenario", "competency_id": "routing-switching", "competency": "R&S"})
    assert calc_spec["task"]["difficulty"] == "MEDIUM"  # INTERMEDIATE interview → MEDIUM task
    assert scen["scenario_id"] in {s.id for s in scenarios.scenarios_for("network-engineer", "routing-switching")}
    assert practicals.assign(None, "u", session, {"position": 5, "kind": "scenario", "competency_id": "nope", "competency": "x"}) is None


# ---------------------------------------------------------------------------
# Interview API: calculation and scenario flows
# ---------------------------------------------------------------------------


@pytest.fixture
def no_bank(monkeypatch):
    """Interview flows below must not depend on which problems happen to be verified in the database."""
    monkeypatch.setattr(practicals, "_verified_problems", lambda db: [])

    async def _noop(session_id, user_id):
        return None

    monkeypatch.setattr(svc, "prepare_remaining_questions", _noop)


def _create(user, **payload):
    res = client.post("/api/interviews", json={"interview_type": "TECHNICAL", "question_count": 3, **payload}, headers=user["headers"])
    assert res.status_code == 201, res.text
    return res.json()


def _practical_question(user, interview):
    """Prepare position 2 (the practical slot of a 3-question technical interview) via navigation."""
    client.post(f"/api/interviews/{interview['id']}/answers",
                json={"question_id": interview["current_question"]["id"], "answer_text": "A conceptual answer."}, headers=user["headers"])
    data = client.post(f"/api/interviews/{interview['id']}/next-question", headers=user["headers"]).json()
    return next(q for q in data["questions"] if q["question_order"] == 2)


def _end(user, interview):
    client.post(f"/api/interviews/{interview['id']}/complete", headers=user["headers"])


def test_network_interview_calculation_is_graded_deterministically(user, model, no_bank):
    interview = _create(user, target_role="Network Engineer", difficulty="INTERMEDIATE")
    try:
        slot = interview["blueprint"]["question_slots"][1]
        assert slot["kind"] == "calculation" and slot["assessment_available"] is True
        question = _practical_question(user, interview)
        assert question["kind"] == "calculation" and question["assessment_available"] is True
        view = question["practical"]
        assert view["label"].startswith("Auto-graded") and view["fields"]

        db = SessionLocal()
        try:
            task = db.get(InterviewQuestion, question["id"]).practical["task"]
        finally:
            db.close()
        expected = calc.expected_answers(task)
        rendered = json.dumps(question)
        assert '"expected"' not in rendered and '"task"' not in rendered and '"params"' not in rendered  # answers never sent

        url = f"/api/interviews/{interview['id']}/answers"
        assert client.post(url, json={"question_id": question["id"], "answer_text": "the answers"}, headers=user["headers"]).status_code == 422
        bad = client.post(url, json={"question_id": question["id"], "structured_answer": {"rogue": "1"}}, headers=user["headers"])
        assert bad.status_code == 422

        calls_before = len(model.calls)
        answers = dict(expected)
        first_key = next(iter(answers))
        answers[first_key] = "definitely wrong"
        res = client.post(url, json={"question_id": question["id"], "structured_answer": answers}, headers=user["headers"])
        assert res.status_code == 201, res.text
        answer = res.json()["answer"]
        grading_calls = [c for c in model.calls[calls_before:] if c["kind"] != "GeneratedFollowUp"]
        assert answer["evaluation_status"] == "COMPLETED" and grading_calls == []  # graded with no model call
        # (the only model call afterwards is the separate follow-up question, generated in the background)
        ev = answer["evaluation"]
        assert ev["method"] == "deterministic" and ev["total"] == len(expected) and ev["correct"] == len(expected) - 1
        assert answer["score"] == round(100 * (len(expected) - 1) / len(expected))
        assert next(f for f in ev["fields"] if f["key"] == first_key)["correct"] is False
    finally:
        _end(user, interview)


def test_devops_scenario_is_ai_reviewed_against_its_rubric(user, model, no_bank):
    interview = _create(user, target_role="DevOps Engineer", difficulty="INTERMEDIATE")
    try:
        slot = interview["blueprint"]["question_slots"][1]
        assert slot["kind"] == "scenario" and slot["assessment_available"] is True  # no verified Bash problem → scenario
        question = _practical_question(user, interview)
        view = question["practical"]
        assert view["label"] == "AI-reviewed — not executed" and view["context"] and view["tasks"]
        assert "expectations" not in json.dumps(view)  # rubric details stay server-side

        db = SessionLocal()
        try:
            scenario_id = db.get(InterviewQuestion, question["id"]).practical["scenario_id"]
        finally:
            db.close()
        rubric = practicals.scenario_rubric(scenario_id)
        model.push("ScenarioEvaluation", {"criteria": [{"id": "made-up", "score": 100, "comment": "x"}], "feedback": "Ten chars at least."},
                   {"criteria": [{"id": c["id"], "score": 50 if i == 0 else 100, "comment": "ok"} for i, c in enumerate(rubric)],
                    "strengths": ["Clear diagnosis"], "improvements": ["Mention rollout"], "feedback": "Solid answer; add verification steps.",
                    "key_points": []})
        res = client.post(f"/api/interviews/{interview['id']}/answers",
                          json={"question_id": question["id"], "answer_text": "Exit 137 means OOM; raise the limit..."}, headers=user["headers"])
        assert res.status_code == 201, res.text
        answer = res.json()["answer"]
        assert model.count("ScenarioEvaluation") == 2  # mismatched criteria ids were rejected and retried
        ev = answer["evaluation"]
        assert ev["method"] == "ai_rubric" and ev["label"] == "AI-reviewed — not executed"
        assert answer["score"] == 100 - rubric[0]["points"] // 2
        assert [c["id"] for c in ev["criteria"]] == [c["id"] for c in rubric]
        assert ev.get("verdict") is None and ev.get("submission_id") is None and "tests_passed" not in json.dumps(ev)  # no fake execution results
        prompt = next(c for c in reversed(model.calls) if c["kind"] == "ScenarioEvaluation")["messages"][1]["content"]
        assert "RUBRIC:" in prompt and "<candidate_answer>" in prompt
    finally:
        _end(user, interview)

    report = client.post(f"/api/interviews/{interview['id']}/report/generate", headers=user["headers"]).json()
    items = report["aggregates"]["sections"]["practical"]["items"]
    assessed = next(i for i in items if i["position"] == 2)
    assert assessed["status"] == "assessed" and assessed["method"] == "ai_rubric"


def test_custom_role_practical_slot_reports_no_verified_assessment(user, model, no_bank):
    interview = _create(user, target_role=f"Quantum Gardener {uuid.uuid4().hex[:4]}")
    try:
        slot = interview["blueprint"]["question_slots"][1]
        assert slot["kind"] != "question" and slot["assessment_available"] is False
        question = _practical_question(user, interview)
        assert question["assessment_available"] is False
        assert question["practical"] == {"type": slot["kind"], "available": False, "reason": practicals.UNAVAILABLE_REASON}
        res = client.post(f"/api/interviews/{interview['id']}/answers",
                          json={"question_id": question["id"], "answer_text": "text"}, headers=user["headers"])
        assert res.status_code == 409
    finally:
        _end(user, interview)


def test_coding_slot_gets_a_verified_problem_and_only_accepts_code(user, model, monkeypatch):
    monkeypatch.setattr(practicals, "_history", lambda db, user_id, exclude: (Counter(), Counter()))

    async def _noop(session_id, user_id):
        return None

    monkeypatch.setattr(svc, "prepare_remaining_questions", _noop)
    db = SessionLocal()
    problem = CodingProblem(
        slug=f"test-js-{uuid.uuid4().hex[:6]}", title="Temp JS", category="frontend", difficulty="EASY", statement="s",
        input_format="", output_format="", constraints="", examples=[], starter_code={"JAVASCRIPT": ""}, languages=["JAVASCRIPT"],
        checker={"mode": "whitespace"}, roles=["frontend-developer"], competencies=["javascript"], reference_solutions={},
        verified_at=None,  # never in the real verified pool, even if left behind; this test patches the pool instead
    )
    db.add(problem)
    db.commit()
    pid = problem.id
    db.close()
    monkeypatch.setattr(practicals, "_verified_problems", lambda db: [db.get(CodingProblem, pid)])
    interview = _create(user, target_role="Frontend Developer", difficulty="BEGINNER")
    try:
        slot = interview["blueprint"]["question_slots"][1]
        assert (slot["kind"], slot["competency_id"]) == ("coding", "javascript") and slot["assessment_available"]
        data = client.post(f"/api/interviews/{interview['id']}/answers",
                           json={"question_id": interview["current_question"]["id"], "answer_text": "A."}, headers=user["headers"])
        data = client.post(f"/api/interviews/{interview['id']}/next-question", headers=user["headers"]).json()
        question = next(q for q in data["questions"] if q["question_order"] == 2)
        assert question["practical"]["problem_id"] == pid and question["practical"]["languages"] == ["JAVASCRIPT"]
        assert question["assessment_available"] is True  # answered in the code editor
        res = client.post(f"/api/interviews/{interview['id']}/answers",
                          json={"question_id": question["id"], "answer_text": "console.log(1)"}, headers=user["headers"])
        assert res.status_code == 409 and res.json()["detail"]["status"] == "CODE_SUBMISSION_REQUIRED"  # never a text answer
        problem_view = client.get(f"/api/interviews/{interview['id']}/questions/{question['id']}/problem", headers=user["headers"])
        assert problem_view.status_code == 200 and problem_view.json()["category"] == "frontend"
    finally:
        _end(user, interview)
        db = SessionLocal()
        db.query(InterviewQuestion).filter(InterviewQuestion.problem_id == pid).update({"problem_id": None})
        db.query(CodingProblem).filter(CodingProblem.id == pid).delete()
        db.commit()
        db.close()


# ---------------------------------------------------------------------------
# SQL execution through the coding pipeline (Judge0 mocked)
# ---------------------------------------------------------------------------


def test_sql_slot_runs_through_the_harness_and_rejects_dot_commands(user, model, judge):
    db = SessionLocal()
    problem = CodingProblem(
        slug=f"test-sql-{uuid.uuid4().hex[:6]}", title="Temp SQL", category="sql", difficulty="EASY", statement="s",
        input_format="", output_format="", constraints="", examples=[], starter_code={"SQLITE": "-- query"}, languages=["SQLITE"],
        # Verified (execution requires it) but mapped to no real role, so it can never be assigned to an interview.
        checker={"mode": "whitespace"}, roles=["test-fixture-only"], competencies=["sql-queries"], reference_solutions={"SQLITE": "SELECT 1;"},
        verified_at=svc.utcnow(),
    )
    db.add(problem)
    db.flush()
    db.add(CodingTestCase(problem_id=problem.id, ordinal=1, input="CREATE TABLE t(v INT);\nINSERT INTO t VALUES (1),(2);\n", expected_output="3", is_hidden=False))
    db.add(CodingTestCase(problem_id=problem.id, ordinal=2, input="CREATE TABLE t(v INT);\nINSERT INTO t VALUES (40),(2);\n", expected_output="42", is_hidden=True))
    db.commit()
    pid = problem.id
    db.close()
    res = client.post("/api/interviews", json={"target_role": "Data Analyst", "interview_type": "TECHNICAL", "question_count": 3}, headers=user["headers"])
    interview_id = res.json()["id"]
    db = SessionLocal()
    first = db.query(InterviewQuestion).filter(InterviewQuestion.session_id == interview_id).first()
    q = InterviewQuestion(session_id=interview_id, question_order=2, question_text="SQL assessment", category="TECHNICAL", kind="sql",
                          competency="SQL Queries", difficulty=first.difficulty, problem_id=pid,
                          practical={"type": "sql", "problem_id": pid, "problem_slug": "temp", "title": "Temp SQL",
                                     "difficulty": "EASY", "languages": ["SQLITE"]})
    db.add(q)
    db.commit()
    qid = q.id
    db.close()
    base = f"/api/interviews/{interview_id}/questions/{qid}"
    try:
        dot = client.post(f"{base}/run", json={"language": "SQLITE", "source_code": ".shell id"}, headers=user["headers"])
        assert dot.status_code == 422 and "dot-commands" in dot.text
        py = client.post(f"{base}/run", json={"language": "PYTHON", "source_code": "print(1)"}, headers=user["headers"])
        assert py.status_code == 422  # only the problem's language
        res = client.post(f"{base}/submit", json={"language": "SQLITE", "source_code": "SELECT SUM(v) FROM t; -- #fake:sum",
                                                   "idempotency_key": uuid.uuid4().hex}, headers=user["headers"])
        assert res.status_code == 200, res.text
        sent = judge.batches[-1]
        assert all(r.stdin == "" and r.source_code.startswith(harness.SQL_PRELUDE) for r in sent)
        assert "INSERT INTO t VALUES (40),(2);" in sent[1].source_code  # hidden data only ever goes to the sandbox
        assert "(40)" not in res.text
    finally:
        client.post(f"/api/interviews/{interview_id}/complete", headers=user["headers"])
        db = SessionLocal()
        from app.db.models import CodingSubmission
        db.query(CodingSubmission).filter(CodingSubmission.problem_id == pid).delete()
        db.query(InterviewQuestion).filter(InterviewQuestion.problem_id == pid).update({"problem_id": None})
        db.query(CodingProblem).filter(CodingProblem.id == pid).delete()
        db.commit()
        db.close()


def test_assigned_coding_problem_is_reported_as_awaiting_editor_not_unavailable():
    """A verified problem assigned to a coding slot is not 'no verified assessment'; it is unscored until the editor phase."""
    from app.services.interview_scoring import _practical_section

    blueprint = {"question_slots": [
        {"position": 2, "kind": "coding", "competency": "Scripting"},
        {"position": 3, "kind": "sql", "competency": "SQL"},
    ]}
    rows = [
        {"question_order": 2, "kind": "coding", "available": False, "problem_assigned": True, "answered": False, "score": None},
        {"question_order": 3, "kind": "sql", "available": False, "problem_assigned": False, "answered": False, "score": None},
    ]
    section = _practical_section(rows, blueprint, {"calculation", "scenario"})
    statuses = {i["position"]: i["status"] for i in section["items"]}
    assert statuses == {2: "awaiting_editor", 3: "not_available"}
    assert section["score"] is None and section["available"] is False
    assert all(i["score"] is None for i in section["items"])


# ---------------------------------------------------------------------------
# Difficulty fallback is recorded and disclosed
# ---------------------------------------------------------------------------


def _fake_problem(slug, difficulty):
    return SimpleNamespace(
        id=f"id-{slug}", slug=slug, title=slug, difficulty=difficulty, category="bash", languages=["BASH"],
        roles=["devops-engineer"], competencies=["scripting-automation"],
    )


def _devops_session(difficulty):
    role = roles.from_catalog(ROLE_BY_SLUG["devops-engineer"], "DevOps Engineer")
    bp = blueprints.build_blueprint(role, interview_type="TECHNICAL", difficulty=difficulty, total_questions=6,
                                    practical_supply={("coding", "scripting-automation"), ("scenario", "containers")})
    return SimpleNamespace(id=str(uuid.uuid4()), blueprint=bp, questions=[]), bp


def test_advanced_interview_without_hard_problem_records_the_fallback(monkeypatch):
    monkeypatch.setattr(practicals, "_verified_problems", lambda db: [_fake_problem("p-easy", "EASY"), _fake_problem("p-medium", "MEDIUM")])
    monkeypatch.setattr(practicals, "_history", lambda db, user_id, exclude: (Counter(), Counter()))
    session, bp = _devops_session("ADVANCED")
    slot = next(s for s in bp["question_slots"] if s["kind"] == "coding")
    spec = practicals.assign(None, "u", session, slot)
    assert spec["problem_slug"] == "p-medium"  # closest verified level, never a random one
    assert (spec["difficulty"], spec["planned_difficulty"], spec["difficulty_fallback"]) == ("MEDIUM", "HARD", True)
    view = practicals.public_view(SimpleNamespace(kind="coding", practical=spec, problem_id=spec["problem_id"], question_text="x"))
    assert view["difficulty"] == "MEDIUM" and view["planned_difficulty"] == "HARD" and view["difficulty_fallback"] is True


def test_matching_level_records_no_fallback(monkeypatch):
    monkeypatch.setattr(practicals, "_verified_problems", lambda db: [_fake_problem("p-easy", "EASY"), _fake_problem("p-medium", "MEDIUM")])
    monkeypatch.setattr(practicals, "_history", lambda db, user_id, exclude: (Counter(), Counter()))
    session, bp = _devops_session("INTERMEDIATE")
    slot = next(s for s in bp["question_slots"] if s["kind"] == "coding")
    spec = practicals.assign(None, "u", session, slot)
    assert (spec["problem_slug"], spec["difficulty_fallback"]) == ("p-medium", False)


def test_scenario_fallback_is_recorded(monkeypatch):
    only_easy = scenarios.Scenario(**{**scenarios.SCENARIO_BY_ID["devops-container-restart-loop"].__dict__, "difficulties": ("EASY",)})
    monkeypatch.setattr(practicals, "scenarios_for", lambda role_slug, competency_id: [only_easy])
    monkeypatch.setattr(practicals, "_history", lambda db, user_id, exclude: (Counter(), Counter()))
    session, bp = _devops_session("ADVANCED")
    slot = next(s for s in bp["question_slots"] if s["kind"] == "scenario")
    spec = practicals.assign(None, "u", session, slot)
    assert (spec["difficulty"], spec["planned_difficulty"], spec["difficulty_fallback"]) == ("EASY", "HARD", True)


def test_report_items_carry_the_difficulty_record():
    from app.services.interview_scoring import _practical_section

    blueprint = {"question_slots": [{"position": 2, "kind": "scenario", "competency": "Containers"}]}
    record = {"difficulty": "MEDIUM", "planned_difficulty": "HARD", "difficulty_fallback": True}
    rows = [{"question_order": 2, "kind": "scenario", "available": True, "answered": True, "score": 80, "method": "ai_rubric",
             "difficulty": record}]
    item = _practical_section(rows, blueprint, {"scenario"})["items"][0]
    assert item["status"] == "assessed" and item["difficulty"] == record
