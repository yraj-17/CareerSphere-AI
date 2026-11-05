"""
Coding assessment backend tests (Judge0 mocked at the network boundary).

FakeJudge0 replaces only Judge0Client.languages / submit_batch / fetch_batch.
Programs are identified by a marker in the source ("#fake:<behaviour>") and the
fake computes their output from the real stdin, so verdict mapping, checkers,
weighting, hidden-test filtering, persistence, rate limiting and idempotency all
run for real. Real execution is covered by the separate Judge0 integration run.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.models import CodingProblem, CodingSubmission, CodingTestCase, InterviewQuestion, User
from app.db.redis_client import redis_client
from app.db.session import SessionLocal
from app.main import app
from app.schemas.coding import SubmitSolutionRequest
from app.services import coding_checkers as checkers
from app.services import coding_service
from app.services import coding_verdicts as verdicts
from app.services import interview_service as isvc
from app.services import judge0_client as j0
from tests.test_interviews import _shift_deadline, model, other_user, user  # noqa: F401 — fixtures

client = TestClient(app)


# ---------------------------------------------------------------------------
# Fake Judge0
# ---------------------------------------------------------------------------

LANGS = [
    {"id": 54, "name": "C++ (GCC 9.2.0)"},
    {"id": 62, "name": "Java (OpenJDK 13.0.1)"},
    {"id": 71, "name": "Python (3.8.1)"},
    {"id": 63, "name": "JavaScript (Node.js 12.14.0)"},
]


def _ints(stdin: str) -> list[int]:
    return [int(x) for x in stdin.split() if x.lstrip("-").isdigit()]


class FakeJudge0:
    def __init__(self):
        self.store: dict[str, dict] = {}
        self.batches: list[list[j0.ExecutionRequest]] = []
        self.slow_polls = 0
        self.fail_submit: Exception | None = None
        self.fail_fetch: Exception | None = None

    def _run(self, req: j0.ExecutionRequest) -> dict:
        marker = req.source_code.split("#fake:")[-1].split()[0] if "#fake:" in req.source_code else "sum"
        nums = _ints(req.stdin)
        base = {"status_id": 3, "status_description": "Accepted", "time": 0.01, "memory": 3000}
        if marker == "sum":
            return {**base, "stdout": f"{sum(nums)}\n"}
        if marker == "wrong":
            return {**base, "stdout": "0\n"}
        if marker == "small-only":  # correct only when every number is small (fails the big hidden tests)
            return {**base, "stdout": f"{sum(nums) + (1 if any(n > 1000 for n in nums) else 0)}\n"}
        if marker == "echo":
            return {**base, "stdout": req.stdin, "stderr": "debug:" + req.stdin}
        if marker == "compile-error":
            return {"status_id": 6, "status_description": "Compilation Error", "compile_output": "main.cpp:1: error: 'x' was not declared"}
        if marker == "runtime":
            return {"status_id": 11, "status_description": "Runtime Error (NZEC)", "stderr": "IndexError: list index out of range", "memory": 3200, "time": 0.01}
        if marker == "tle":
            return {"status_id": 5, "status_description": "Time Limit Exceeded", "time": req.cpu_time_limit, "memory": 900}
        if marker == "mle":
            return {"status_id": 11, "status_description": "Runtime Error (NZEC)", "memory": req.memory_limit_kb, "time": 0.1}
        if marker == "oom-message":
            return {"status_id": 11, "status_description": "Runtime Error (NZEC)", "stderr": "MemoryError", "memory": 9000, "time": 0.1}
        if marker == "internal":
            return {"status_id": 13, "status_description": "Internal Error"}
        raise AssertionError(marker)

    async def languages(self_client):  # bound as Judge0Client method
        return LANGS

    def install(self, monkeypatch):
        fake = self

        async def languages(self_client):
            return LANGS

        async def submit_batch(self_client, requests):
            if fake.fail_submit:
                raise fake.fail_submit
            fake.batches.append(list(requests))
            tokens = []
            for req in requests:
                token = uuid.uuid4().hex
                fake.store[token] = {"req": req, "polls": 0, "result": fake._run(req)}
                tokens.append(token)
            return tokens

        async def fetch_batch(self_client, tokens):
            if fake.fail_fetch:
                raise fake.fail_fetch
            out = []
            for token in tokens:
                entry = fake.store[token]
                entry["polls"] += 1
                if entry["polls"] <= fake.slow_polls:
                    out.append(j0.ExecutionResult(token=token, status_id=2, status_description="Processing"))
                    continue
                r = entry["result"]
                out.append(
                    j0.ExecutionResult(
                        token=token,
                        status_id=r["status_id"],
                        status_description=r["status_description"],
                        stdout=r.get("stdout", ""),
                        stderr=r.get("stderr", ""),
                        compile_output=r.get("compile_output", ""),
                        time=r.get("time"),
                        memory=r.get("memory"),
                    )
                )
            return out

        monkeypatch.setattr(j0.Judge0Client, "languages", languages)
        monkeypatch.setattr(j0.Judge0Client, "submit_batch", submit_batch)
        monkeypatch.setattr(j0.Judge0Client, "fetch_batch", fetch_batch)
        return self


@pytest.fixture
def judge(monkeypatch):
    monkeypatch.setattr(settings, "JUDGE0_API_URL", "http://judge0.test:2358")
    monkeypatch.setattr(settings, "JUDGE0_AUTH_TOKEN", "test-token-not-real")
    monkeypatch.setattr(settings, "JUDGE0_POLL_INTERVAL_SECONDS", 0.01)
    monkeypatch.setattr(settings, "JUDGE0_INLINE_WAIT_SECONDS", 0.5)
    j0._language_cache.update(expires=0.0, value=None)
    async def _noop(session_id, user_id):
        return None
    monkeypatch.setattr(isvc, "prepare_remaining_questions", _noop)
    return FakeJudge0().install(monkeypatch)


# ---------------------------------------------------------------------------
# Problem + interview setup
# ---------------------------------------------------------------------------


def _make_problem(**overrides) -> str:
    overrides = {"verified_at": isvc.utcnow(), "reference_solutions": {"PYTHON": "#fake:sum"}, **overrides}
    db = SessionLocal()
    try:
        problem = CodingProblem(
            slug=f"sum-{uuid.uuid4().hex[:8]}",
            title="Sum of Numbers",
            difficulty="EASY",
            statement="Print the sum of the given integers.",
            input_format="Integers separated by spaces.",
            output_format="One integer.",
            constraints="Up to 10^5 integers.",
            examples=[{"input": "1 2", "output": "3", "explanation": "1 + 2 = 3"}],
            starter_code={"PYTHON": "# read input\n", "CPP": "int main(){}"},
            languages=["CPP", "JAVA", "PYTHON", "JAVASCRIPT"],
            checker={"mode": "whitespace"},
            time_limit_seconds=1.0,
            memory_limit_kb=128000,
            roles=["software-development-engineer"],
            competencies=["Data Structures"],
            estimated_minutes=10,
            **overrides,
        )
        db.add(problem)
        db.flush()
        tests = [
            ("1 2", "3", False, 1.0),
            ("10 20 30", "60", False, 1.0),
            ("SECRET-A 5 7", "12", True, 1.0),
            ("SECRET-B 4000 1", "4001", True, 2.0),
            ("SECRET-C 9000 9000", "18000", True, 2.0),
        ]
        for i, (inp, out, hidden, weight) in enumerate(tests, start=1):
            db.add(CodingTestCase(problem_id=problem.id, ordinal=i, input=inp, expected_output=out, is_hidden=hidden, weight=weight))
        db.commit()
        return problem.id
    finally:
        db.close()


def _delete_problem(problem_id: str) -> None:
    db = SessionLocal()
    try:
        db.query(CodingSubmission).filter(CodingSubmission.problem_id == problem_id).delete()
        db.query(InterviewQuestion).filter(InterviewQuestion.problem_id == problem_id).update({"problem_id": None})
        db.query(CodingProblem).filter(CodingProblem.id == problem_id).delete()
        db.commit()
    finally:
        db.close()


@pytest.fixture
def problem_id():
    pid = _make_problem()
    yield pid
    _delete_problem(pid)


def _coding_interview(user: dict, problem_id: str) -> tuple[str, str]:
    res = client.post("/api/interviews", json={"target_role": "Software Development Engineer", "interview_type": "TECHNICAL"}, headers=user["headers"])
    assert res.status_code == 201, res.text
    interview_id = res.json()["id"]
    db = SessionLocal()
    try:
        first = db.query(InterviewQuestion).filter(InterviewQuestion.session_id == interview_id).first()
        question = InterviewQuestion(
            session_id=interview_id, question_order=2, question_text="Coding assessment: Data Structures",
            category="TECHNICAL", kind="coding", competency="Data Structures", difficulty=first.difficulty, problem_id=problem_id,
        )
        db.add(question)
        db.commit()
        return interview_id, question.id
    finally:
        db.close()


@pytest.fixture
def coding(user, model, judge, problem_id):
    interview_id, question_id = _coding_interview(user, problem_id)
    return {"user": user, "interview": interview_id, "question": question_id, "problem": problem_id}


def _url(c: dict, action: str) -> str:
    return f"/api/interviews/{c['interview']}/questions/{c['question']}/{action}"


def _run(c, source, **extra):
    return client.post(_url(c, "run"), json={"language": "PYTHON", "source_code": source, **extra}, headers=c["user"]["headers"])


def _submit(c, source, key=None, language="PYTHON"):
    return client.post(
        _url(c, "submit"),
        json={"language": language, "source_code": source, "idempotency_key": key or uuid.uuid4().hex},
        headers=c["user"]["headers"],
    )


# ---------------------------------------------------------------------------
# Verdicts (1-6)
# ---------------------------------------------------------------------------


def test_run_accepted_on_samples_only(coding, judge):
    res = _run(coding, "#fake:sum")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["submission_type"] == "RUN" and body["status"] == "COMPLETED"
    assert body["verdict"] == "ACCEPTED" and body["verdict_label"] == "Accepted"
    assert body["tests_passed"] == 2 and body["tests_total"] == 2
    assert [r["kind"] for r in body["results"]] == ["sample", "sample"]
    assert body["results"][0] == {**body["results"][0], "input": "1 2", "expected_output": "3", "stdout": "3\n", "passed": True}
    assert body["language_label"] == "Python (3.8.1)"  # label as reported by the Judge0 server
    # Run never sends hidden inputs to Judge0.
    sent = [r.stdin for r in judge.batches[-1]]
    assert sent == ["1 2", "10 20 30"] and not any("SECRET" in s for s in sent)


def test_submit_accepted_with_weighted_correctness(coding):
    res = _submit(coding, "#fake:sum")
    body = res.json()
    assert body["verdict"] == "ACCEPTED" and body["tests_passed"] == 5 and body["tests_total"] == 5
    assert body["correctness_score"] == 100.0
    assert [r["kind"] for r in body["results"]] == ["sample", "sample", "hidden", "hidden", "hidden"]


def test_wrong_answer(coding):
    body = _submit(coding, "#fake:wrong").json()
    assert body["verdict"] == "WRONG_ANSWER" and body["tests_passed"] == 0 and body["correctness_score"] == 0.0


def test_partial_credit_uses_test_weights(coding):
    body = _submit(coding, "#fake:small-only").json()
    # passes samples (1+1) and hidden A (1); fails hidden B and C (2+2) -> 3/7
    assert body["verdict"] == "WRONG_ANSWER"
    assert body["tests_passed"] == 3
    assert body["correctness_score"] == round(100 * 3 / 7, 2)


def test_compilation_error(coding):
    body = _submit(coding, "#fake:compile-error").json()
    assert body["verdict"] == "COMPILATION_ERROR"
    assert "was not declared" in body["compile_output"]
    assert body["tests_passed"] == 0


def test_runtime_error_is_not_reported_as_memory(coding):
    body = _submit(coding, "#fake:runtime").json()
    assert body["verdict"] == "RUNTIME_ERROR"
    assert body["results"][0]["judge0_status"] == "Runtime Error (NZEC)"  # original Judge0 status preserved
    assert "IndexError" in body["results"][0]["stderr"]


def test_time_limit_exceeded(coding):
    body = _submit(coding, "#fake:tle").json()
    assert body["verdict"] == "TIME_LIMIT_EXCEEDED"


@pytest.mark.parametrize("marker", ["mle", "oom-message"])
def test_memory_limit_exceeded_requires_evidence(coding, marker):
    body = _submit(coding, f"#fake:{marker}").json()
    assert body["verdict"] == "MEMORY_LIMIT_EXCEEDED" and body["verdict_label"] == "Memory Limit Exceeded"
    assert body["results"][0]["judge0_status"] == "Runtime Error (NZEC)"


def test_judge_internal_error_is_not_blamed_on_the_candidate(coding):
    body = _submit(coding, "#fake:internal").json()
    assert body["verdict"] == "JUDGE_ERROR" and body["verdict_label"] == "Execution Service Error"


def test_classify_execution_mapping():
    def r(status_id, **kw):
        return j0.ExecutionResult(token="t", status_id=status_id, status_description="x", **kw)

    assert verdicts.classify_execution(r(6), 1000) == verdicts.COMPILATION_ERROR
    assert verdicts.classify_execution(r(5), 1000) == verdicts.TIME_LIMIT_EXCEEDED
    assert verdicts.classify_execution(r(11, memory=960), 1000) == verdicts.MEMORY_LIMIT_EXCEEDED
    assert verdicts.classify_execution(r(11, memory=500), 1000) == verdicts.RUNTIME_ERROR
    assert verdicts.classify_execution(r(7, memory=100, stderr="std::bad_alloc"), 1000) == verdicts.MEMORY_LIMIT_EXCEEDED
    assert verdicts.classify_execution(r(9, memory=100), 1000) == verdicts.RUNTIME_ERROR  # SIGFPE stays runtime
    assert verdicts.classify_execution(r(3), 1000) == verdicts.EXECUTED
    assert verdicts.classify_execution(r(13), 1000) == verdicts.JUDGE_ERROR


def test_optional_tests_do_not_block_acceptance():
    outcomes = [
        verdicts.TestOutcome(1, verdicts.ACCEPTED, 3, "", 0.1, 1, True, 1.0, True, False),
        verdicts.TestOutcome(2, verdicts.WRONG_ANSWER, 3, "", 0.1, 1, False, 1.0, False, True),
    ]
    summary = verdicts.summarise(outcomes)
    assert summary.verdict == verdicts.ACCEPTED and summary.correctness_score == 50.0


# ---------------------------------------------------------------------------
# Output checkers (7)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "config,expected,actual,ok",
    [
        ({"mode": "exact"}, "1 2\n", "1 2\r\n", True),
        ({"mode": "exact"}, "1 2\n", "1  2\n", False),
        ({"mode": "whitespace"}, "a\nb\n", "a  \nb\n\n\n", True),
        ({"mode": "whitespace"}, "a b", "a  b", False),
        ({"mode": "tokens"}, "a b\nc", "a\nb c", True),
        ({"mode": "float", "tolerance": 1e-6}, "0.333333", "0.3333331", True),
        ({"mode": "float", "tolerance": 1e-6}, "0.333333", "0.3334", False),
        ({"mode": "float", "tolerance": 1e-6}, "1e9 yes", "1000000000.0004 yes", True),  # relative tolerance
        ({"mode": "unordered_lines"}, "x 1\ny 2", "y 2\nx  1", True),
        ({"mode": "unordered_lines"}, "x\ny", "x\nx", False),
        ({"mode": "unordered_tokens"}, "3 1 2", "1\n2\n3", True),
    ],
)
def test_checker_modes(config, expected, actual, ok):
    assert checkers.run_checker(config, stdin="", expected=expected, actual=actual)[0] is ok


def test_custom_validator_accepts_any_valid_answer():
    cfg = {"mode": "custom", "validator": "two_sum_indices"}
    stdin = "4\n2 7 11 15\n9\n"
    assert checkers.run_checker(cfg, stdin=stdin, expected="0 1", actual="1 0")[0] is True
    assert checkers.run_checker(cfg, stdin=stdin, expected="0 1", actual="0 0")[0] is False
    assert checkers.run_checker(cfg, stdin=stdin, expected="0 1", actual="garbage")[0] is False


def test_invalid_checker_configs_are_rejected():
    for bad in ({"mode": "regex"}, {"mode": "float", "tolerance": 5}, {"mode": "custom", "validator": "nope"}):
        with pytest.raises(ValueError):
            checkers.validate_checker_config(bad)


# ---------------------------------------------------------------------------
# Hidden-test protection (8)
# ---------------------------------------------------------------------------


def test_hidden_tests_never_leave_the_backend(coding):
    body = _submit(coding, "#fake:echo").json()
    text = json.dumps(body)
    assert "SECRET" not in text  # neither inputs nor the program's echo of them
    hidden = [r for r in body["results"] if r["kind"] == "hidden"]
    assert len(hidden) == 3
    for r in hidden:
        assert set(r) == {"ordinal", "kind", "verdict", "verdict_label", "passed", "time", "memory", "judge0_status"}

    db = SessionLocal()
    try:
        row = db.get(CodingSubmission, body["id"])
        stored_hidden = [r for r in row.results if r["kind"] == "hidden"]
        assert all("stdout" not in r and "stderr" not in r for r in stored_hidden)  # not even stored
    finally:
        db.close()

    history = client.get(_url(coding, "submissions"), headers=coding["user"]["headers"]).text
    assert "SECRET" not in history


def test_problem_view_has_no_hidden_tests_or_reference_solutions(coding):
    res = client.get(_url(coding, "problem"), headers=coding["user"]["headers"])
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["sample_test_count"] == 2 and body["hidden_test_count"] == 3
    assert "SECRET" not in res.text and "#fake:sum" not in res.text and "reference" not in res.text
    assert {l["key"]: l["label"] for l in body["languages"]}["JAVA"] == "Java (OpenJDK 13.0.1)"


def test_client_cannot_override_limits_or_tests(coding, judge):
    res = client.post(
        _url(coding, "submit"),
        json={"language": "PYTHON", "source_code": "#fake:sum", "idempotency_key": uuid.uuid4().hex, "cpu_time_limit": 10, "tests": []},
        headers=coding["user"]["headers"],
    )
    assert res.status_code == 422
    _submit(coding, "#fake:sum")
    sent = judge.batches[-1]
    assert {r.cpu_time_limit for r in sent} == {3.0}  # 1.0 s problem limit × Python multiplier 3
    assert {r.memory_limit_kb for r in sent} == {128000}


# ---------------------------------------------------------------------------
# Auth, ownership, state (9, 15)
# ---------------------------------------------------------------------------


def test_authentication_required(coding):
    for action in ("run", "submit"):
        assert client.post(_url(coding, action), json={}).status_code == 401
    for action in ("problem", "submissions"):
        assert client.get(_url(coding, action)).status_code == 401
    assert client.get("/api/coding/languages").status_code == 401


def test_other_users_cannot_use_or_read_an_interview(coding, other_user):
    sub = _submit(coding, "#fake:sum").json()
    h = other_user["headers"]
    assert client.post(_url(coding, "run"), json={"language": "PYTHON", "source_code": "#fake:sum"}, headers=h).status_code == 404
    assert client.get(_url(coding, "problem"), headers=h).status_code == 404
    assert client.get(f"/api/interviews/{coding['interview']}/coding-submissions/{sub['id']}", headers=h).status_code == 404


def test_state_and_configuration_checks(coding, judge):
    db = SessionLocal()
    try:
        conceptual = db.query(InterviewQuestion).filter(InterviewQuestion.session_id == coding["interview"], InterviewQuestion.kind == "question").first()
        conceptual_id = conceptual.id
        db.get(CodingProblem, coding["problem"]).languages = ["PYTHON"]
        db.commit()
    finally:
        db.close()
    url = f"/api/interviews/{coding['interview']}/questions/{conceptual_id}/run"
    assert client.post(url, json={"language": "PYTHON", "source_code": "x"}, headers=coding["user"]["headers"]).json()["detail"]["status"] == "NOT_CODING"
    assert _submit(coding, "#fake:sum", language="JAVA").status_code == 422  # not enabled for this problem

    db = SessionLocal()
    try:
        db.get(CodingProblem, coding["problem"]).verified_at = None
        db.commit()
    finally:
        db.close()
    assert _submit(coding, "#fake:sum").json()["detail"]["status"] == "UNVERIFIED"

    db = SessionLocal()
    try:
        db.get(CodingProblem, coding["problem"]).verified_at = isvc.utcnow()
        db.commit()
    finally:
        db.close()
    _shift_deadline(coding["interview"], -timedelta(minutes=5))
    assert _submit(coding, "#fake:sum").json()["detail"]["status"] == "ENDED"


def test_unconfigured_judge0_reports_clearly(coding, monkeypatch):
    monkeypatch.setattr(settings, "JUDGE0_AUTH_TOKEN", "")
    res = _submit(coding, "#fake:sum")
    assert res.status_code == 503
    assert client.get("/api/coding/languages", headers=coding["user"]["headers"]).json()["execution_available"] is False


# ---------------------------------------------------------------------------
# Rate limiting (10)
# ---------------------------------------------------------------------------


def test_rate_limits(coding, monkeypatch):
    monkeypatch.setattr(settings, "CODING_RUN_RATE_LIMIT_PER_MINUTE", 2)
    assert _run(coding, "#fake:sum").status_code == 200
    assert _run(coding, "#fake:sum").status_code == 200
    third = _run(coding, "#fake:sum")
    assert third.status_code == 429 and third.json()["detail"]["status"] == "RATE_LIMITED"


def test_submission_cap_per_question(coding, monkeypatch):
    monkeypatch.setattr(settings, "CODING_MAX_SUBMISSIONS_PER_QUESTION", 1)
    assert _submit(coding, "#fake:sum").status_code == 200
    assert _submit(coding, "#fake:sum").json()["detail"]["status"] == "SUBMISSION_LIMIT"


# ---------------------------------------------------------------------------
# Duplicates and concurrency (11, 12)
# ---------------------------------------------------------------------------


def test_same_idempotency_key_returns_the_same_submission(coding, judge):
    key = uuid.uuid4().hex
    first = _submit(coding, "#fake:sum", key=key).json()
    second = _submit(coding, "#fake:sum", key=key).json()
    assert first["id"] == second["id"]
    assert len(judge.batches) == 1  # executed once
    conflict = _submit(coding, "#fake:wrong", key=key)
    assert conflict.status_code == 409 and conflict.json()["detail"]["status"] == "IDEMPOTENCY_CONFLICT"


def test_concurrent_duplicate_requests_create_one_submission(coding, judge):
    key = uuid.uuid4().hex

    async def both():
        dbs = [SessionLocal(), SessionLocal()]
        try:
            users = [d.get(User, coding["user"]["id"]) for d in dbs]
            payload = SubmitSolutionRequest(language="PYTHON", source_code="#fake:sum", idempotency_key=key)
            return await asyncio.gather(
                *[coding_service.submit_solution(d, u, coding["interview"], coding["question"], payload) for d, u in zip(dbs, users)],
                return_exceptions=True,
            )
        finally:
            for d in dbs:
                d.close()

    results = asyncio.run(both())
    ok = [r for r in results if not isinstance(r, Exception)]
    assert ok and len({r.id for r in ok}) == 1
    db = SessionLocal()
    try:
        assert db.query(CodingSubmission).filter(CodingSubmission.idempotency_key == key).count() == 1
    finally:
        db.close()


def test_one_execution_at_a_time_per_user(coding, judge):
    judge.slow_polls = 10_000  # stays running
    first = _submit(coding, "#fake:sum").json()
    assert first["status"] == "RUNNING"
    busy = _submit(coding, "#fake:sum")
    assert busy.status_code == 429 and busy.json()["detail"]["status"] == "IN_FLIGHT"
    redis_client.delete(coding_service._inflight_key(coding["user"]["id"]))


# ---------------------------------------------------------------------------
# Interrupted polling and service failures (13)
# ---------------------------------------------------------------------------


def test_running_submission_resumes_from_stored_tokens(coding, judge):
    judge.slow_polls = 1_000
    started = _submit(coding, "#fake:sum").json()
    assert started["status"] == "RUNNING" and started["verdict"] is None and started["results"] == []

    judge.fail_fetch = j0.Judge0Error("unavailable", "down")
    url = f"/api/interviews/{coding['interview']}/coding-submissions/{started['id']}"
    still = client.get(url, headers=coding["user"]["headers"]).json()
    assert still["status"] == "RUNNING"  # polling failure loses nothing

    judge.fail_fetch = None
    judge.slow_polls = 0
    done = client.get(url, headers=coding["user"]["headers"]).json()
    assert done["status"] == "COMPLETED" and done["verdict"] == "ACCEPTED"
    assert len(judge.batches) == 1  # resumed, not re-executed
    assert redis_client.get(coding_service._inflight_key(coding["user"]["id"])) is None  # lock released on completion


def test_judge0_unavailable_on_submit_can_be_retried_with_the_same_key(coding, judge):
    key = uuid.uuid4().hex
    judge.fail_submit = j0.Judge0Error("unavailable", "down")
    failed = _submit(coding, "#fake:sum", key=key)
    assert failed.status_code == 503 and failed.json()["detail"]["stage"] == "judge0_unavailable"
    judge.fail_submit = None
    retried = _submit(coding, "#fake:sum", key=key).json()
    assert retried["status"] == "COMPLETED" and retried["id"] == failed.json()["detail"]["submission_id"]


# ---------------------------------------------------------------------------
# Persistence (14)
# ---------------------------------------------------------------------------


def test_submission_is_persisted(coding):
    key = uuid.uuid4().hex
    body = _submit(coding, "#fake:small-only", key=key).json()
    db = SessionLocal()
    try:
        row = db.get(CodingSubmission, body["id"])
        assert (row.user_id, row.session_id, row.question_id, row.problem_id) == (
            coding["user"]["id"], coding["interview"], coding["question"], coding["problem"])
        assert row.submission_type == "SUBMIT" and row.language == "PYTHON" and row.language_label == "Python (3.8.1)"
        assert row.source_code == "#fake:small-only" and row.idempotency_key == key
        assert row.status == "COMPLETED" and row.verdict == "WRONG_ANSWER"
        assert (row.tests_passed, row.tests_total) == (3, 5)
        assert row.max_time_seconds == 0.01 and row.max_memory_kb == 3000
        assert row.created_at is not None and row.completed_at is not None
        assert len(row.judge_tokens) == 5
    finally:
        db.close()
    history = client.get(_url(coding, "submissions"), headers=coding["user"]["headers"]).json()["submissions"]
    assert history[0]["id"] == body["id"]


def test_custom_input_run(coding, judge):
    body = _run(coding, "#fake:sum", custom_input="40 2").json()
    custom = [r for r in body["results"] if r["kind"] == "custom"]
    assert custom and custom[0]["stdout"] == "42\n" and custom[0]["passed"] is None and custom[0]["expected_output"] is None
    assert body["verdict"] == "ACCEPTED"  # the verdict is from the samples; custom input has no expected output


# ---------------------------------------------------------------------------
# Problem verification (reference solutions)
# ---------------------------------------------------------------------------


def test_verify_problem_with_reference_solutions(judge):
    good = _make_problem(verified_at=None)
    bad = _make_problem(verified_at=None, reference_solutions={"PYTHON": "#fake:small-only"})
    db = SessionLocal()
    try:
        report = asyncio.run(coding_service.verify_problem(db, db.get(CodingProblem, good)))
        assert report["verified"] is True and db.get(CodingProblem, good).verified_at is not None
        report = asyncio.run(coding_service.verify_problem(db, db.get(CodingProblem, bad)))
        assert report["verified"] is False and report["languages"]["PYTHON"]["verdict"] == "WRONG_ANSWER"
        assert db.get(CodingProblem, bad).verified_at is None
    finally:
        db.close()
        _delete_problem(good)
        _delete_problem(bad)


# ---------------------------------------------------------------------------
# Judge0 client: auth header, retry policy, no secret logging
# ---------------------------------------------------------------------------


_REAL_ASYNC_CLIENT = httpx.AsyncClient


def _patched_client(monkeypatch, handler):
    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return _REAL_ASYNC_CLIENT(*args, **kwargs)

    monkeypatch.setattr(j0.httpx, "AsyncClient", factory)
    monkeypatch.setattr(settings, "JUDGE0_MAX_RETRIES", 2)
    return j0.Judge0Client("http://judge0.test:2358", "super-secret-token")


def test_client_sends_token_and_retries_get_on_503(monkeypatch, caplog):
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(503)
        return httpx.Response(200, json=LANGS)

    client_ = _patched_client(monkeypatch, handler)
    with caplog.at_level(logging.DEBUG):
        assert asyncio.run(client_.languages()) == LANGS
    assert len(calls) == 2 and calls[0].headers["X-Auth-Token"] == "super-secret-token"
    assert "super-secret-token" not in caplog.text


def test_client_never_resends_a_post_that_may_have_been_accepted(monkeypatch):
    calls = []

    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout("slow", request=request)

    client_ = _patched_client(monkeypatch, handler)
    with pytest.raises(j0.Judge0Error) as exc:
        asyncio.run(client_.submit_batch([j0.ExecutionRequest(language_id=71, source_code="print(1)")]))
    assert exc.value.kind == "unavailable" and len(calls) == 1


def test_client_retries_post_when_connection_failed(monkeypatch):
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            raise httpx.ConnectError("refused", request=request)
        return httpx.Response(201, json=[{"token": "abc"}])

    client_ = _patched_client(monkeypatch, handler)
    assert asyncio.run(client_.submit_batch([j0.ExecutionRequest(language_id=71, source_code="print(1)")])) == ["abc"]
    assert len(calls) == 2


def test_client_maps_401_and_422(monkeypatch):
    client_ = _patched_client(monkeypatch, lambda request: httpx.Response(401))
    with pytest.raises(j0.Judge0Error) as exc:
        asyncio.run(client_.languages())
    assert exc.value.kind == "auth" and "super-secret-token" not in str(exc.value)
    client_ = _patched_client(monkeypatch, lambda request: httpx.Response(422, json={"cpu_time_limit": ["too big"]}))
    with pytest.raises(j0.Judge0Error) as exc:
        asyncio.run(client_.submit_batch([j0.ExecutionRequest(language_id=71, source_code="x")]))
    assert exc.value.kind == "rejected"


def test_request_payload_never_enables_network():
    payload = j0.ExecutionRequest(language_id=54, source_code="int main(){}", compiler_options="-std=c++17").to_payload()
    assert payload["enable_network"] is False and payload["compiler_options"] == "-std=c++17"


# ---------------------------------------------------------------------------
# In-interview answers: a completed SUBMIT is the coding question's answer
# ---------------------------------------------------------------------------


@pytest.fixture
def assessed(coding):
    """The coding fixture's question, with the practical spec an assigned slot carries."""
    db = SessionLocal()
    try:
        q = db.get(InterviewQuestion, coding["question"])
        q.practical = {"type": "coding", "problem_id": coding["problem"], "problem_slug": "sum", "title": "Sum of Numbers",
                       "difficulty": "EASY", "planned_difficulty": "EASY", "difficulty_fallback": False, "languages": ["PYTHON", "CPP"]}
        db.commit()
    finally:
        db.close()
    return coding


def _question_state(c) -> dict:
    data = client.get(f"/api/interviews/{c['interview']}", headers=c["user"]["headers"]).json()
    return next(q for q in data["questions"] if q["id"] == c["question"])


def test_coding_question_is_answerable_only_by_submitting_code(assessed):
    q = _question_state(assessed)
    assert q["assessment_available"] is True and q["status"] in ("NOT_STARTED", "SKIPPED") and q["answer"] is None
    text = client.post(f"/api/interviews/{assessed['interview']}/answers",
                       json={"question_id": assessed["question"], "answer_text": "print(sum(...))"}, headers=assessed["user"]["headers"])
    assert text.status_code == 409 and text.json()["detail"]["status"] == "CODE_SUBMISSION_REQUIRED"
    assert _run(assessed, "#fake:sum").json()["verdict"] == "ACCEPTED"
    assert _question_state(assessed)["answer"] is None  # Run never counts as an answer


def test_completed_submit_is_recorded_as_the_scored_answer(assessed):
    body = _submit(assessed, "#fake:sum").json()
    assert body["status"] == "COMPLETED" and body["verdict"] == "ACCEPTED"
    q = _question_state(assessed)
    assert q["status"] == "ANSWERED" and q["answer"]["evaluation_status"] == "COMPLETED"
    ev = q["answer"]["evaluation"]
    assert ev["method"] == "judge0" and ev["verdict"] == "ACCEPTED" and ev["correctness_score"] == 100
    # The (mocked) AI review ran in the background: quality 75 -> combined 0.7*100 + 0.3*75 = 92.5
    assert ev["review_status"] == "COMPLETED" and ev["quality_score"] == 75.0 and ev["coding_score"] == 92.5
    assert q["answer"]["score"] == 93  # 92.5 rounded half-up, as displayed
    assert (ev["correct"], ev["total"], ev["language"], ev["submission_id"]) == (5, 5, "PYTHON", body["id"])
    assert q["answer"]["answer_text"] == "#fake:sum"  # the submitted source is the answer
    assert "SECRET" not in json.dumps(q)  # no hidden test data through the interview API either


def test_latest_submission_replaces_the_answer_and_older_ones_never_do(assessed):
    first = _submit(assessed, "#fake:sum").json()
    second = _submit(assessed, "#fake:small-only").json()
    q = _question_state(assessed)
    assert q["answer"]["evaluation"]["submission_id"] == second["id"] and q["answer"]["evaluation"]["verdict"] == "WRONG_ANSWER"
    # weighted correctness: tests weigh 1,1,1,2,2 and the 3 light ones pass -> 300/7
    assert round(q["answer"]["evaluation"]["correctness_score"], 2) == round(100 * 3 / 7, 2)
    assert q["answer"]["evaluation"]["coding_score"] == round(0.7 * (100 * 3 / 7) + 0.3 * 75.0, 1)  # with the AI quality score
    assert q["answer"]["score"] == int(0.7 * (100 * 3 / 7) + 0.3 * 75.0 + 0.5)
    db = SessionLocal()
    try:
        older = db.get(CodingSubmission, first["id"])
        assert coding_service.record_interview_answer(db, older) is False  # an older submission finishing late
    finally:
        db.close()
    assert _question_state(assessed)["answer"]["evaluation"]["submission_id"] == second["id"]


def test_code_drafts_survive_a_submission(assessed):
    _submit(assessed, "#fake:sum")
    url = f"/api/interviews/{assessed['interview']}/questions/{assessed['question']}/draft"
    meta = {"language": "CPP", "code": {"PYTHON": "#fake:sum", "CPP": "int main() { return 0; }"}, "edited": True}
    res = client.put(url, json={"text": "", "meta": meta, "revision": 10}, headers=assessed["user"]["headers"])
    assert res.status_code == 200 and res.json()["saved"] is True
    q = _question_state(assessed)
    assert q["draft_meta"] == meta and q["status"] == "ANSWERED"
    stale = client.put(url, json={"text": "", "meta": {"language": "PYTHON", "code": {}}, "revision": 5}, headers=assessed["user"]["headers"])
    assert stale.json()["saved"] is False and _question_state(assessed)["draft_meta"] == meta  # older autosave never wins


def test_report_settles_running_submission_and_scores_it_from_judge0(assessed, judge):
    first = client.get(f"/api/interviews/{assessed['interview']}", headers=assessed["user"]["headers"]).json()["current_question"]
    client.post(f"/api/interviews/{assessed['interview']}/answers",
                json={"question_id": first["id"], "answer_text": "Use a hash map for O(1) lookups."}, headers=assessed["user"]["headers"])
    judge.slow_polls = 1_000
    started = _submit(assessed, "#fake:sum").json()
    assert started["status"] == "RUNNING"
    client.post(f"/api/interviews/{assessed['interview']}/complete", headers=assessed["user"]["headers"])
    judge.slow_polls = 0
    report = client.post(f"/api/interviews/{assessed['interview']}/report/generate", headers=assessed["user"]["headers"]).json()
    db = SessionLocal()
    try:
        assert db.get(CodingSubmission, started["id"]).status == "COMPLETED"
    finally:
        db.close()
    q = _question_state(assessed)
    ev = q["answer"]["evaluation"]
    assert ev["submission_id"] == started["id"] and ev["correctness_score"] == 100
    assert ev["review_status"] == "COMPLETED" and q["answer"]["score"] == 93  # review settled before the report
    late = _submit(assessed, "#fake:wrong")
    assert late.status_code == 409  # interview ended: no more submissions
    assert report["status"] in ("COMPLETED", "FAILED")


def test_answers_are_frozen_once_the_report_is_completed(assessed):
    body = _submit(assessed, "#fake:sum").json()
    db = SessionLocal()
    try:
        from app.db.models import InterviewAIStatus, InterviewReport
        db.add(InterviewReport(session_id=assessed["interview"], status=InterviewAIStatus.COMPLETED))
        db.commit()
        row = db.get(CodingSubmission, body["id"])
        assert coding_service.record_interview_answer(db, row) is False
    finally:
        db.close()
