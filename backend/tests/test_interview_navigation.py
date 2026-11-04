"""
Question navigation, background preparation and server-side drafts.

Unlike test_interviews.py, these tests run the real background preparer
(TestClient executes background tasks before returning), so the whole planned
interview exists right after creation — exactly what free navigation relies on.
"""

from __future__ import annotations

import asyncio
import time
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.db.models import InterviewQuestion
from app.db.session import SessionLocal
from app.main import app
from app.services import interview_service as svc
from app.services.ollama_service import AIServiceError
from tests.test_interviews import _shift_deadline, model, no_verified_bank, other_user, user  # noqa: F401 — fixtures/helpers (no_verified_bank is autouse)

client = TestClient(app)


def _create(user: dict, **overrides) -> dict:
    payload = {"target_role": "Software Development Engineer", "interview_type": "TECHNICAL"}
    payload.update(overrides)
    res = client.post("/api/interviews", json=payload, headers=user["headers"])
    assert res.status_code == 201, res.text
    return res.json()


def _detail(user: dict, interview_id: str) -> dict:
    res = client.get(f"/api/interviews/{interview_id}", headers=user["headers"])
    assert res.status_code == 200, res.text
    return res.json()


def _q(detail: dict, position: int) -> dict:
    return next(q for q in detail["questions"] if q["question_order"] == position)


_seq = [int(time.time() * 1000)]


def _next_seq() -> int:
    _seq[0] += 1
    return _seq[0]


def _navigate(user: dict, interview_id: str, position: int, seq: int | None = None):
    return client.post(
        f"/api/interviews/{interview_id}/navigate",
        json={"position": position, "seq": seq or _next_seq()},
        headers=user["headers"],
    )


def _draft(user: dict, interview_id: str, question_id: str, text: str, revision: int | None = None):
    return client.put(
        f"/api/interviews/{interview_id}/questions/{question_id}/draft",
        json={"text": text, "revision": revision or _next_seq()},
        headers=user["headers"],
    )


def _submit(user: dict, interview_id: str, question_id: str, text: str = "A considered answer."):
    return client.post(
        f"/api/interviews/{interview_id}/answers",
        json={"question_id": question_id, "answer_text": text},
        headers=user["headers"],
    )


def _evaluations(model) -> int:
    return model.count("TechnicalEvaluation") + model.count("BehavioralEvaluation")


# ---------------------------------------------------------------------------
# Background preparation
# ---------------------------------------------------------------------------


def test_whole_plan_is_prepared_once_after_creation(user, model):
    interview = _create(user)
    assert interview["preparing"] is True  # response returns as soon as question 1 is ready
    assert interview["question_count"] == 1

    detail = _detail(user, interview["id"])
    assert detail["preparing"] is False
    assert [q["question_order"] for q in detail["questions"]] == [1, 2, 3, 4, 5, 6]
    assert [q["kind"] for q in detail["questions"]] == ["question", "coding", "question", "question", "coding", "question"]
    assert [q["status"] for q in detail["questions"]] == ["NOT_STARTED", "UNAVAILABLE", "NOT_STARTED", "NOT_STARTED", "UNAVAILABLE", "NOT_STARTED"]
    assert model.count("GeneratedQuestion") == 4  # one call per conceptual slot, none for reserved slots
    assert len({q["id"] for q in detail["questions"]}) == 6
    # Each conceptual question was generated for its own blueprint competency.
    slots = {s["position"]: s["competency"] for s in detail["blueprint"]["question_slots"]}
    assert all(q["competency"] == slots[q["question_order"]] for q in detail["questions"])


def test_preparer_is_idempotent(user, model):
    interview = _create(user)
    calls = model.count("GeneratedQuestion")
    asyncio.run(svc.prepare_remaining_questions(interview["id"], user["id"]))
    asyncio.run(svc.prepare_remaining_questions(interview["id"], user["id"]))
    detail = _detail(user, interview["id"])
    assert len(detail["questions"]) == 6
    assert model.count("GeneratedQuestion") == calls


def test_failed_preparation_resumes_when_navigating_and_never_duplicates(user, model):
    model.push("GeneratedQuestion", {"question_text": "First question about arrays and strings, explained clearly?"}, AIServiceError("down"))
    interview = _create(user)
    detail = _detail(user, interview["id"])
    assert [q["question_order"] for q in detail["questions"]] == [1, 2]  # stopped at position 3; reserved slot 2 recorded
    assert detail["preparing"] is True

    res = _navigate(user, interview["id"], 4)  # an unprepared question: navigation restarts preparation
    assert res.status_code == 200
    detail = _detail(user, interview["id"])
    assert [q["question_order"] for q in detail["questions"]] == [1, 2, 3, 4, 5, 6]
    assert detail["preparing"] is False


def test_preparation_stops_when_the_interview_has_ended(user, model, monkeypatch):
    async def _noop(session_id, user_id):
        return None

    monkeypatch.setattr(svc, "prepare_remaining_questions", _noop)
    interview = _create(user)
    client.post(f"/api/interviews/{interview['id']}/complete", headers=user["headers"])
    monkeypatch.undo()
    asyncio.run(svc.prepare_remaining_questions(interview["id"], user["id"]))
    assert len(_detail(user, interview["id"])["questions"]) == 1


# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------


def test_navigation_never_submits_evaluates_or_generates(user, model):
    interview = _create(user)
    generated, evaluated = model.count("GeneratedQuestion"), _evaluations(model)
    for position in (2, 3, 1, 6, 5, 4, 1):
        assert _navigate(user, interview["id"], position).status_code == 200
    detail = _detail(user, interview["id"])
    assert model.count("GeneratedQuestion") == generated
    assert _evaluations(model) == evaluated
    assert detail["answered_count"] == 0
    assert all(q["answer"] is None for q in detail["questions"])
    assert detail["current_position"] == 1


def test_navigate_forward_back_and_preserve_draft(user, model):
    interview = _create(user)
    detail = _detail(user, interview["id"])
    q1, q3 = _q(detail, 1), _q(detail, 3)

    assert _draft(user, interview["id"], q1["id"], "Use a hash map.\nThen two pointers.").json()["saved"] is True
    _navigate(user, interview["id"], 3)
    _draft(user, interview["id"], q3["id"], "Draft for three")
    _navigate(user, interview["id"], 1)

    detail = _detail(user, interview["id"])
    assert _q(detail, 1)["draft_text"] == "Use a hash map.\nThen two pointers."  # multiline preserved
    assert _q(detail, 3)["draft_text"] == "Draft for three"  # drafts are independent per question
    assert _q(detail, 1)["status"] == "IN_PROGRESS" and _q(detail, 3)["status"] == "IN_PROGRESS"


def test_skip_a_question_and_return_later(user, model):
    interview = _create(user)
    _navigate(user, interview["id"], 1)
    _navigate(user, interview["id"], 3)  # leave question 1 untouched
    detail = _detail(user, interview["id"])
    assert _q(detail, 1)["status"] == "SKIPPED"
    assert _q(detail, 4)["status"] == "NOT_STARTED"

    _navigate(user, interview["id"], 1)
    assert _submit(user, interview["id"], _q(detail, 1)["id"]).status_code == 201
    assert _q(_detail(user, interview["id"]), 1)["status"] == "ANSWERED"


def test_jump_directly_and_answer_out_of_order(user, model):
    interview = _create(user)
    detail = _detail(user, interview["id"])
    assert _navigate(user, interview["id"], 6).json()["current_position"] == 6
    assert _submit(user, interview["id"], _q(detail, 6)["id"], "Answering the last one first").status_code == 201
    assert _submit(user, interview["id"], _q(detail, 3)["id"]).status_code == 201

    detail = _detail(user, interview["id"])
    assert [q["status"] for q in detail["questions"]] == ["NOT_STARTED", "UNAVAILABLE", "ANSWERED", "NOT_STARTED", "UNAVAILABLE", "ANSWERED"]
    assert detail["answered_count"] == 2
    assert detail["current_question"]["question_order"] == 1  # next to answer, independent of position


def test_submitted_answers_are_read_only_and_never_overwritten_by_drafts(user, model):
    interview = _create(user)
    q1 = _q(_detail(user, interview["id"]), 1)
    _draft(user, interview["id"], q1["id"], "my draft")
    assert _submit(user, interview["id"], q1["id"], "final answer").status_code == 201
    evaluations = _evaluations(model)

    res = _draft(user, interview["id"], q1["id"], "")  # e.g. an empty editor autosaving after submission
    assert res.status_code == 409 and res.json()["detail"]["status"] == "ALREADY_SUBMITTED"
    assert _submit(user, interview["id"], q1["id"], "again").status_code == 409  # no duplicate submission
    _navigate(user, interview["id"], 3)
    _navigate(user, interview["id"], 1)  # revisiting does not resubmit or re-evaluate

    q1 = _q(_detail(user, interview["id"]), 1)
    assert q1["answer"]["answer_text"] == "final answer"
    assert q1["draft_text"] is None
    assert _evaluations(model) == evaluations


def test_older_autosave_cannot_overwrite_newer_draft(user, model):
    interview = _create(user)
    q1 = _q(_detail(user, interview["id"]), 1)
    newer = _draft(user, interview["id"], q1["id"], "newer text", revision=2_000)
    older = _draft(user, interview["id"], q1["id"], "older text", revision=1_000)  # delivered late
    assert newer.json()["saved"] is True
    assert older.status_code == 200 and older.json() == {**older.json(), "saved": False, "revision": 2_000}
    assert _q(_detail(user, interview["id"]), 1)["draft_text"] == "newer text"


def test_rapid_navigation_resolves_to_the_latest_click(user, model):
    interview = _create(user)
    _navigate(user, interview["id"], 5, seq=5_000)
    _navigate(user, interview["id"], 2, seq=4_000)  # earlier click arriving late
    assert _detail(user, interview["id"])["current_position"] == 5


def test_timer_continues_across_navigation(user, model):
    interview = _create(user)
    deadline = _detail(user, interview["id"])["deadline_at"]
    remaining = []
    for position in (1, 2, 3, 1):
        body = _navigate(user, interview["id"], position).json()
        assert body["deadline_at"] == deadline
        remaining.append(body["remaining_seconds"])
    assert remaining == sorted(remaining, reverse=True)  # never increases


def test_refresh_and_resume_restore_position_and_drafts(user, model):
    interview = _create(user)
    detail = _detail(user, interview["id"])
    _navigate(user, interview["id"], 4)
    _draft(user, interview["id"], _q(detail, 4)["id"], "half-written answer")
    _submit(user, interview["id"], _q(detail, 1)["id"])

    restored = _detail(user, interview["id"])  # what a refresh or a resume on another device loads
    assert restored["current_position"] == 4
    assert _q(restored, 4)["draft_text"] == "half-written answer"
    assert _q(restored, 1)["answer"]["evaluation"]["feedback"]
    history = client.get("/api/interviews", headers=user["headers"]).json()["interviews"]
    assert history[0]["id"] == interview["id"] and history[0]["status"] == "IN_PROGRESS"


def test_navigation_and_draft_validation(user, other_user, model):
    interview = _create(user)
    detail = _detail(user, interview["id"])
    assert _navigate(user, interview["id"], 7).status_code == 422
    assert _navigate(user, interview["id"], 0).status_code == 422
    reserved = _q(detail, 2)
    res = _draft(user, interview["id"], reserved["id"], "def solve(): pass")
    assert res.status_code == 409 and res.json()["detail"]["status"] == "ASSESSMENT_UNAVAILABLE"
    too_long = _draft(user, interview["id"], _q(detail, 1)["id"], "x" * 5001)
    assert too_long.status_code == 422
    # Another user can neither navigate nor write drafts.
    assert _navigate(other_user, interview["id"], 1).status_code == 404
    assert _draft(other_user, interview["id"], _q(detail, 1)["id"], "hijack").status_code == 404


def test_drafts_and_navigation_stop_after_the_deadline(user, model):
    interview = _create(user)
    q1 = _q(_detail(user, interview["id"]), 1)
    _shift_deadline(interview["id"], -timedelta(minutes=5))
    assert _navigate(user, interview["id"], 1).status_code == 409
    assert _draft(user, interview["id"], q1["id"], "late").status_code == 409


def test_finishing_with_unanswered_questions_keeps_drafts_visible(user, model):
    interview = _create(user)
    detail = _detail(user, interview["id"])
    _submit(user, interview["id"], _q(detail, 1)["id"])
    _draft(user, interview["id"], _q(detail, 3)["id"], "unsubmitted thoughts")

    ended = client.post(f"/api/interviews/{interview['id']}/complete", headers=user["headers"]).json()
    assert ended["status"] == "COMPLETED"
    q3 = _q(ended, 3)
    assert q3["status"] == "IN_PROGRESS" and q3["draft_text"] == "unsubmitted thoughts"  # preserved, not discarded
    assert _navigate(user, interview["id"], 3).status_code == 409  # finalized: no further changes
    assert _draft(user, interview["id"], q3["id"], "edit").status_code == 409

    report = client.post(f"/api/interviews/{interview['id']}/report/generate", headers=user["headers"]).json()
    assert report["aggregates"]["answered_count"] == 1  # drafts are never scored as answers


def test_unique_question_order_prevents_duplicate_rows(user, model):
    interview = _create(user)
    db = SessionLocal()
    try:
        before = db.query(InterviewQuestion).filter(InterviewQuestion.session_id == interview["id"]).count()
        dup = InterviewQuestion(session_id=interview["id"], question_order=3, question_text="dup", category="TECHNICAL",
                                kind="question", competency="x", difficulty=_q(_detail(user, interview["id"]), 1)["difficulty"])
        assert svc._insert_question(db, interview["id"], dup) is False
        after = db.query(InterviewQuestion).filter(InterviewQuestion.session_id == interview["id"]).count()
        assert before == after == 6
    finally:
        db.close()
