"""
Phase 5: AI Code Review, combined coding score, follow-up questions, role-aware report.

The model is mocked (FakeModel) and Judge0 is mocked (FakeJudge0) — these are unit /
API tests, not live integration tests. Live runs are done separately against the real
Ollama/Qwen and Judge0 services.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import timedelta

import pytest

from app.core.config import settings
from app.db.models import CodingSubmission, InterviewAIStatus, InterviewQuestion, InterviewReport
from app.db.session import SessionLocal
from app.services import code_review
from app.services import coding_service
from app.services import interview_service as isvc
from app.services.ollama_service import AIServiceError
from tests.test_coding_assessment import (  # noqa: F401 — fixtures and helpers
    _question_state,
    _submit,
    assessed,
    client,
    coding,
    judge,
    problem_id,
)
from tests.test_interviews import _shift_deadline, model, other_user, user  # noqa: F401 — fixtures

REVIEW = "CodeReviewResult"
FOLLOW = "GeneratedFollowUp"


def _review(**overrides):
    base = {
        "criteria": {"problem_solving": 80, "code_quality": 70, "efficiency": 90, "time_complexity": 80,
                     "space_complexity": 60, "edge_cases": 50},
        "summary": "A clear single-pass approach with readable names.",
        "strengths": ["Single pass"], "weaknesses": ["No empty-input guard"], "improvements": ["Validate input"],
        "alternative_approaches": ["Two pointers after sorting"], "time_complexity": "O(n)", "space_complexity": "O(n)",
        "missing_edge_cases": ["Empty input"], "recommendations": ["Add boundary tests"],
    }
    base.update(overrides)
    return base


def _submission(c, sid):
    return client.get(f"/api/interviews/{c['interview']}/coding-submissions/{sid}", headers=c["user"]["headers"]).json()


def _interview(c):
    return client.get(f"/api/interviews/{c['interview']}", headers=c["user"]["headers"]).json()


def _hold_reviews(monkeypatch):
    """Keep reviews PENDING (as if the background review has not run yet)."""
    async def _noop(submission_id):
        return None
    monkeypatch.setattr(coding_service, "review_submission", _noop)


def _no_follow_ups(monkeypatch):
    async def _noop(*args):
        return None
    monkeypatch.setattr(isvc, "generate_follow_up_task", _noop)


# ---------------------------------------------------------------------------
# Deterministic scoring (7)
# ---------------------------------------------------------------------------


def test_quality_score_uses_the_fixed_weights():
    criteria = {"problem_solving": 80, "code_quality": 70, "efficiency": 90, "time_complexity": 80, "space_complexity": 60, "edge_cases": 50}
    assert code_review.quality_score(criteria) == 75.0  # 20 + 14 + 18 + 12 + 6 + 5
    assert code_review.quality_score({k: 100 for k in code_review.WEIGHTS}) == 100.0
    assert code_review.quality_score({k: 0 for k in code_review.WEIGHTS}) == 0.0
    assert sum(code_review.WEIGHTS.values()) == 100


def test_round_half_up_matches_the_ui():
    assert (code_review.round_half_up(92.5), code_review.round_half_up(92.4), code_review.round_half_up(0.5)) == (93, 92, 1)


def test_combined_score_is_70_30_and_never_manufactured():
    assert code_review.combined_score(100, 75) == 92.5
    assert code_review.combined_score(0, 100) == 30.0
    assert code_review.combined_score(42.857, 75) == round(0.7 * 42.857 + 0.3 * 75, 1)
    assert code_review.combined_score(None, 75) is None
    assert code_review.combined_score(100, None) is None


@pytest.mark.parametrize("bad", [{"problem_solving": 150}, {"code_quality": -1}, {"efficiency": 50.5}, {"edge_cases": True}])
def test_quality_score_rejects_out_of_range_or_non_integer(bad):
    criteria = {k: 50 for k in code_review.WEIGHTS} | bad
    with pytest.raises(ValueError):
        code_review.quality_score(criteria)


def test_quality_score_rejects_missing_criteria():
    with pytest.raises(ValueError):
        code_review.quality_score({"problem_solving": 80})


def test_execution_claims_are_detected_without_flagging_ordinary_review_text():
    for sentence in ["The code compiles successfully.", "It passes all hidden tests.", "I ran it and verified the fix.",
                     "The solution is accepted."]:
        assert code_review.execution_claims([sentence]), sentence
    assert code_review.execution_claims([
        "Empty input is accepted by the parser but not validated.", "Consider tests for duplicates.",
        "Judge0 reported a wrong answer on some tests; the loop bound looks off by one.",
    ]) == []


# ---------------------------------------------------------------------------
# Review lifecycle and integrity (1-6, 8-10, 19)
# ---------------------------------------------------------------------------


def test_verdict_is_returned_immediately_and_the_review_arrives_separately(assessed, model, monkeypatch):
    _hold_reviews(monkeypatch)
    body = _submit(assessed, "#fake:sum").json()
    assert body["verdict"] == "ACCEPTED" and body["ai_review"]["status"] == "PENDING" and body["coding_score"] is None
    q = _question_state(assessed)
    assert q["answer"]["score"] == 100 and q["answer"]["evaluation"]["review_status"] == "PENDING"  # correctness only
    assert q["answer"]["evaluation"]["coding_score"] is None  # no combined score until the review exists

    db = SessionLocal()
    try:
        assert asyncio.run(coding_service.run_review(db, body["id"])) is True
    finally:
        db.close()
    done = _submission(assessed, body["id"])
    assert done["verdict"] == "ACCEPTED"  # unchanged by the review
    review = done["ai_review"]
    assert review["status"] == "COMPLETED" and review["label"] == "AI Code Review" and review["quality_score"] == 75.0
    assert [c["id"] for c in review["criteria"]] == [k for k, _, _ in code_review.CRITERIA]
    assert done["coding_score"] == 92.5
    q = _question_state(assessed)
    assert (q["answer"]["evaluation"]["coding_score"], q["answer"]["score"]) == (92.5, 93)  # half-up, as displayed


def test_review_prompt_has_execution_facts_and_role_but_no_hidden_data(assessed, model):
    _submit(assessed, "#fake:sum")
    prompt = next(c for c in model.calls if c["kind"] == REVIEW)["messages"][1]["content"]
    assert "TARGET ROLE: Software Development Engineer" in prompt
    assert "Accepted; 5 of 5 tests passed" in prompt and "<candidate_code>" in prompt
    assert "SECRET" not in prompt  # hidden test inputs never reach the model
    assert "18000" not in prompt and "4001" not in prompt  # nor hidden expected outputs


def test_wrong_answer_remains_wrong_answer_after_review(assessed, model):
    body = _submit(assessed, "#fake:wrong").json()
    done = _submission(assessed, body["id"])
    assert done["verdict"] == "WRONG_ANSWER" and done["ai_review"]["status"] == "COMPLETED"
    assert done["coding_score"] == round(0.7 * done["correctness_score"] + 0.3 * 75.0, 1)
    ev = _question_state(assessed)["answer"]["evaluation"]
    assert ev["verdict"] == "WRONG_ANSWER" and ev["verdict_label"] == "Wrong Answer"


def test_compilation_error_is_never_treated_as_accepted(assessed, model):
    body = _submit(assessed, "#fake:compile-error").json()
    done = _submission(assessed, body["id"])
    assert done["verdict"] == "COMPILATION_ERROR"
    assert done["ai_review"]["compiled"] is False and "compilation error" in done["ai_review"]["note"].lower()
    prompt = next(c for c in model.calls if c["kind"] == REVIEW)["messages"][1]["content"]
    assert "did not compile, so no test was executed" in prompt
    assert _question_state(assessed)["answer"]["evaluation"]["verdict"] == "COMPILATION_ERROR"


@pytest.mark.parametrize(
    "responses",
    [
        ("not json", "```json\n{broken"),  # invalid JSON
        ({"criteria": _review()["criteria"]}, {"summary": "only a summary here"}),  # missing fields
        (_review(criteria=_review()["criteria"] | {"efficiency": 150}),) * 2,  # out-of-range score
        (_review(summary="The code compiles successfully and passes all tests."),) * 2,  # claims execution
    ],
    ids=["invalid-json", "missing-fields", "out-of-range", "execution-claim"],
)
def test_unusable_reviews_fail_cleanly_and_correctness_stands(assessed, model, responses):
    model.push(REVIEW, *responses)
    body = _submit(assessed, "#fake:sum").json()
    done = _submission(assessed, body["id"])
    assert done["verdict"] == "ACCEPTED" and done["ai_review"]["status"] == "FAILED" and done["ai_review"]["can_retry"]
    assert done["coding_score"] is None and done["ai_review"]["quality_score"] is None
    q = _question_state(assessed)
    assert q["answer"]["score"] == 100 and q["answer"]["evaluation"]["review_status"] == "FAILED"
    assert q["answer"]["evaluation"]["coding_score"] is None  # never manufactured


def test_failed_review_can_be_retried_safely(assessed, model):
    model.push(REVIEW, AIServiceError("ReadTimeout"))
    body = _submit(assessed, "#fake:sum").json()
    assert _submission(assessed, body["id"])["ai_review"]["status"] == "FAILED"
    url = f"/api/interviews/{assessed['interview']}/coding-submissions/{body['id']}/review"
    retried = client.post(url, headers=assessed["user"]["headers"]).json()
    assert retried["ai_review"]["status"] == "COMPLETED" and retried["coding_score"] == 92.5
    again = client.post(url, headers=assessed["user"]["headers"]).json()  # already completed: no new model call
    assert again["ai_review"]["status"] == "COMPLETED" and model.count(REVIEW) == 2
    assert _question_state(assessed)["answer"]["score"] == 93


def test_one_review_per_submission_despite_repeated_triggers(assessed, model):
    body = _submit(assessed, "#fake:sum").json()
    for _ in range(3):  # polling schedules the review again; the claim makes it a no-op
        _submission(assessed, body["id"])
    db = SessionLocal()
    try:
        assert asyncio.run(coding_service.run_review(db, body["id"])) is False
    finally:
        db.close()
    assert model.count(REVIEW) == 1


def test_concurrent_review_requests_produce_one_review(assessed, model, monkeypatch):
    _hold_reviews(monkeypatch)
    body = _submit(assessed, "#fake:sum").json()

    async def both():
        sessions = [SessionLocal(), SessionLocal()]
        try:
            return await asyncio.gather(*(coding_service.run_review(db, body["id"]) for db in sessions))
        finally:
            for db in sessions:
                db.close()

    assert sorted(asyncio.run(both())) == [False, True]
    assert model.count(REVIEW) == 1


def test_each_new_submission_gets_its_own_review(assessed, model):
    first = _submit(assessed, "#fake:sum").json()
    model.push(REVIEW, _review(summary="A weaker second attempt with nested loops.",
                               criteria={k: 40 for k in code_review.WEIGHTS}))
    second = _submit(assessed, "#fake:small-only").json()
    a, b = _submission(assessed, first["id"]), _submission(assessed, second["id"])
    assert a["ai_review"]["quality_score"] == 75.0 and b["ai_review"]["quality_score"] == 40.0
    assert a["ai_review"]["summary"] != b["ai_review"]["summary"]
    ev = _question_state(assessed)["answer"]["evaluation"]
    assert ev["submission_id"] == second["id"] and ev["quality_score"] == 40.0  # the newer code's review


def test_runs_are_never_reviewed(assessed, model):
    run = client.post(f"/api/interviews/{assessed['interview']}/questions/{assessed['question']}/run",
                      json={"language": "PYTHON", "source_code": "#fake:sum"}, headers=assessed["user"]["headers"]).json()
    assert run["ai_review"] is None and run["coding_score"] is None and model.count(REVIEW) == 0


# ---------------------------------------------------------------------------
# Report (16-18)
# ---------------------------------------------------------------------------


def _answer_first_conceptual(c):
    current = _interview(c)["current_question"]
    client.post(f"/api/interviews/{c['interview']}/answers", json={"question_id": current["id"], "answer_text": "Use a hash map."},
                headers=c["user"]["headers"])


def test_report_waits_for_a_pending_review_and_shows_coding_results(assessed, model, monkeypatch):
    _hold_reviews(monkeypatch)
    _no_follow_ups(monkeypatch)
    _answer_first_conceptual(assessed)
    body = _submit(assessed, "#fake:sum").json()
    _submit(assessed, "#fake:sum")  # second attempt (counts as an attempt, replaces the answer)
    client.post(f"/api/interviews/{assessed['interview']}/complete", headers=assessed["user"]["headers"])
    report = client.post(f"/api/interviews/{assessed['interview']}/report/generate", headers=assessed["user"]["headers"]).json()
    coding_section = report["aggregates"]["sections"]["coding"]
    item = coding_section["items"][0]
    assert item["title"] == "Sum of Numbers" and item["language_label"] == "Python (3.8.1)" and item["verdict"] == "ACCEPTED"
    assert (item["tests_passed"], item["tests_total"], item["submission_attempts"]) == (5, 5, 2)
    assert item["correctness_score"] == 100 and item["quality_score"] == 75.0 and item["coding_score"] == 92.5
    assert item["review_status"] == "COMPLETED" and item["review"]["time_complexity"] == "O(n)"
    assert item["max_time_seconds"] == 0.01 and item["max_memory_kb"] == 3000
    assert coding_section["reviews_pending"] == 0 and body["id"] != item.get("submission_id")
    dims = report["aggregates"]["dimensions"]
    assert dims["coding_correctness"] == 100 and dims["code_quality"] == 75
    assert dims["behavioral"] is None  # not assessed -> None, never 0


def test_review_unavailable_at_report_time_is_reported_with_its_status(assessed, model, monkeypatch):
    _no_follow_ups(monkeypatch)
    model.push(REVIEW, *[AIServiceError("down")] * 10)
    _answer_first_conceptual(assessed)
    _submit(assessed, "#fake:sum")
    client.post(f"/api/interviews/{assessed['interview']}/complete", headers=assessed["user"]["headers"])
    report = client.post(f"/api/interviews/{assessed['interview']}/report/generate", headers=assessed["user"]["headers"]).json()
    item = report["aggregates"]["sections"]["coding"]["items"][0]
    assert item["review_status"] == "FAILED" and item["quality_score"] is None and item["coding_score"] is None
    assert item["correctness_score"] == 100 and report["aggregates"]["sections"]["coding"]["coding_score"] is None
    assert report["aggregates"]["dimensions"]["code_quality"] is None


def test_review_finishing_after_report_finalisation_never_changes_it(assessed, model, monkeypatch):
    _hold_reviews(monkeypatch)
    body = _submit(assessed, "#fake:sum").json()
    db = SessionLocal()
    try:
        db.add(InterviewReport(session_id=assessed["interview"], status=InterviewAIStatus.COMPLETED))
        db.commit()
        assert asyncio.run(coding_service.run_review(db, body["id"])) is True
    finally:
        db.close()
    assert _submission(assessed, body["id"])["ai_review"]["status"] == "COMPLETED"  # stored on the submission
    q = _question_state(assessed)
    assert q["answer"]["score"] == 100 and q["answer"]["evaluation"]["coding_score"] is None  # finalised answer untouched


# ---------------------------------------------------------------------------
# Follow-ups (11-13, limits, timing)
# ---------------------------------------------------------------------------


def _follow_ups(c):
    return [q for q in _interview(c)["questions"] if q["parent_question_id"]]


def test_follow_up_is_generated_from_the_submitted_code(assessed, model):
    before = _interview(assessed)
    _submit(assessed, "#fake:sum")
    data = _interview(assessed)
    follow = [q for q in data["questions"] if q["parent_question_id"]]
    assert len(follow) == 1
    f = follow[0]
    assert f["parent_question_id"] == assessed["question"] and f["question_order"] == 102
    assert f["kind"] == "question" and f["competency"] == "Data Structures" and f["assessment_available"]
    parent = next(q for q in data["questions"] if q["id"] == assessed["question"])
    assert parent["follow_up_state"] == "CREATED"
    assert data["max_questions"] == before["max_questions"] and data["question_count"] == before["question_count"]
    assert data["follow_up_count"] == 1
    assert data["deadline_at"] == before["deadline_at"]  # the timer is never extended
    prompt = next(c for c in model.calls if c["kind"] == FOLLOW)["messages"][1]["content"]
    assert "#fake:sum" in prompt and "Accepted; 5 of 5 tests passed" in prompt and "SECRET" not in prompt
    assert "TARGET ROLE: Software Development Engineer" in prompt and "ASSESSED COMPETENCY: Data Structures" in prompt


def test_at_most_one_follow_up_per_question(assessed, model):
    _submit(assessed, "#fake:sum")
    _submit(assessed, "#fake:small-only")
    db = SessionLocal()
    try:
        assert asyncio.run(isvc.create_follow_up(db, assessed["interview"], assessed["user"]["id"], assessed["question"])) is None
    finally:
        db.close()
    assert len(_follow_ups(assessed)) == 1 and model.count(FOLLOW) == 1


def test_follow_up_can_be_opened_answered_and_is_scored_under_the_parent_competency(assessed, model):
    _submit(assessed, "#fake:sum")
    follow = _follow_ups(assessed)[0]
    nav = client.post(f"/api/interviews/{assessed['interview']}/navigate", json={"position": 102, "seq": 10**12},
                      headers=assessed["user"]["headers"])
    assert nav.status_code == 200 and nav.json()["current_position"] == 102
    res = client.post(f"/api/interviews/{assessed['interview']}/answers",
                      json={"question_id": follow["id"], "answer_text": "Use a streaming pass so memory stays O(1) per element."},
                      headers=assessed["user"]["headers"])
    assert res.status_code == 201 and res.json()["answer"]["evaluation_status"] == "COMPLETED"
    data = _interview(assessed)
    assert data["follow_up_answered_count"] == 1
    assert len([q for q in data["questions"] if q["parent_question_id"]]) == 1  # answering a follow-up never spawns another
    _answer_first_conceptual(assessed)
    client.post(f"/api/interviews/{assessed['interview']}/complete", headers=assessed["user"]["headers"])
    report = client.post(f"/api/interviews/{assessed['interview']}/report/generate", headers=assessed["user"]["headers"]).json()
    comp = {c["competency"]: c for c in report["aggregates"]["competency_scores"]}
    assert "Data Structures" in comp and comp["Data Structures"]["level"] is not None
    assert report["aggregates"]["follow_ups"] == {"asked": 1, "answered": 1}


def test_follow_up_limit_per_interview(assessed, model, monkeypatch):
    monkeypatch.setattr(settings, "INTERVIEW_MAX_FOLLOW_UPS", 1)
    _submit(assessed, "#fake:sum")
    db = SessionLocal()
    try:
        second = InterviewQuestion(
            session_id=assessed["interview"], question_order=3, question_text="Coding assessment: again", category="TECHNICAL",
            kind="coding", competency="Algorithms", difficulty=db.get(InterviewQuestion, assessed["question"]).difficulty,
            problem_id=assessed["problem"], practical=dict(db.get(InterviewQuestion, assessed["question"]).practical),
        )
        db.add(second)
        db.commit()
        second_id = second.id
    finally:
        db.close()
    client.post(f"/api/interviews/{assessed['interview']}/questions/{second_id}/submit",
                json={"language": "PYTHON", "source_code": "#fake:sum", "idempotency_key": uuid.uuid4().hex},
                headers=assessed["user"]["headers"])
    assert len(_follow_ups(assessed)) == 1 and model.count(FOLLOW) == 1  # limit reached: no second model call


def test_follow_ups_disabled_with_zero(assessed, model, monkeypatch):
    monkeypatch.setattr(settings, "INTERVIEW_MAX_FOLLOW_UPS", 0)
    _submit(assessed, "#fake:sum")
    assert _follow_ups(assessed) == [] and model.count(FOLLOW) == 0


def test_no_follow_up_when_too_little_time_is_left(assessed, model):
    _shift_deadline(assessed["interview"], timedelta(seconds=settings.INTERVIEW_FOLLOW_UP_MIN_REMAINING_SECONDS - 30))
    before = _interview(assessed)["deadline_at"]
    _submit(assessed, "#fake:sum")
    assert _follow_ups(assessed) == [] and model.count(FOLLOW) == 0
    assert _interview(assessed)["deadline_at"] == before


def test_no_follow_up_is_added_after_the_interview_ended(assessed, model, monkeypatch):
    _no_follow_ups(monkeypatch)
    _submit(assessed, "#fake:sum")
    client.post(f"/api/interviews/{assessed['interview']}/complete", headers=assessed["user"]["headers"])
    db = SessionLocal()
    try:
        made = asyncio.run(isvc.create_follow_up(db, assessed["interview"], assessed["user"]["id"], assessed["question"]))
    finally:
        db.close()
    assert made is None and model.count(FOLLOW) == 0


def test_failed_follow_up_generation_is_recorded_and_adds_nothing(assessed, model):
    model.push(FOLLOW, AIServiceError("ReadTimeout"))
    _submit(assessed, "#fake:sum")
    data = _interview(assessed)
    parent = next(q for q in data["questions"] if q["id"] == assessed["question"])
    assert parent["follow_up_state"] == "FAILED" and _follow_ups(assessed) == []


def test_unavailable_practical_slots_never_get_follow_ups(user, model):
    """Custom roles (no verified assessment) keep practical slots unavailable — no follow-up is possible."""
    res = client.post("/api/interviews", json={"target_role": f"Quantum Gardener {uuid.uuid4().hex[:4]}", "interview_type": "TECHNICAL"},
                      headers=user["headers"])
    interview = res.json()
    slot = next(s for s in interview["blueprint"]["question_slots"] if s["kind"] != "question")
    assert slot["assessment_available"] is False
    db = SessionLocal()
    try:
        reserved = (
            db.query(InterviewQuestion)
            .filter(InterviewQuestion.session_id == interview["id"], InterviewQuestion.question_order == slot["position"])
            .first()
        )
        if reserved is None:  # not prepared yet: record it as the preparer would
            first = db.query(InterviewQuestion).filter(InterviewQuestion.session_id == interview["id"]).first()
            reserved = InterviewQuestion(session_id=interview["id"], question_order=slot["position"], question_text="Practical slot",
                                         category="TECHNICAL", kind=slot["kind"], competency=slot["competency"],
                                         difficulty=first.difficulty, practical={"type": "unavailable", "reason": "No verified assessment"})
            db.add(reserved)
            db.commit()
        made = asyncio.run(isvc.create_follow_up(db, interview["id"], user["id"], reserved.id))
    finally:
        db.close()
    assert made is None and model.count(FOLLOW) == 0


def test_coding_follow_up_waits_for_an_accepted_submission(assessed, model):
    _submit(assessed, "#fake:wrong")
    assert _follow_ups(assessed) == [] and model.count(FOLLOW) == 0  # nothing deeper to ask about unsolved code
    parent = next(q for q in _interview(assessed)["questions"] if q["id"] == assessed["question"])
    assert parent["follow_up_state"] is None  # still open
    _submit(assessed, "#fake:sum")
    assert len(_follow_ups(assessed)) == 1 and model.count(FOLLOW) == 1
    prompt = next(c for c in model.calls if c["kind"] == FOLLOW)["messages"][1]["content"]
    assert "Accepted; 5 of 5 tests passed" in prompt  # grounded in the working solution


def test_follow_up_may_ask_about_technologies_the_candidate_used_but_not_unrelated_ones():
    from app.data.interview_roles import ROLE_BY_SLUG
    from app.services import interview_role_service as roles

    role = roles.from_catalog(ROLE_BY_SLUG["devops-engineer"], "DevOps Engineer")
    work = "The Node.js service loads its whole catalogue at boot; I would lazy-load it and pin node:20-slim."
    question = "How would you lazy-load the catalogue in the Node.js service without slowing the first request?"
    assert roles.off_role_terms(question, role, ["Containers"]) != []  # without the candidate's work: rejected
    assert roles.off_role_terms(question, role, ["Containers", work]) == []  # grounded in their own answer: allowed
    assert roles.off_role_terms("How would you design a React component tree here?", role, ["Containers", work]) != []
