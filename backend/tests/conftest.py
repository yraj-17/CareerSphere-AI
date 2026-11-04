"""
Shared test-session hygiene.

Some tests insert temporary coding problems (slug prefix "test-") into the dev
database. A run that is interrupted before a test's `finally` would leave such a
row behind, and a leftover *verified* row could then be assigned to a real
interview. Remove any leftovers before and after every test session.
"""
import pytest

FIXTURE_SLUG_PREFIXES = ("test-js-", "test-sql-", "test-temp-")


def _purge_fixture_problems() -> int:
    from sqlalchemy import or_

    from app.data.coding_bank import all_problems
    from app.db.models import CodingProblem, CodingSubmission, InterviewQuestion
    from app.db.session import SessionLocal

    bank = {spec.slug for spec in all_problems()}
    db = SessionLocal()
    try:
        ids = [
            pid for pid, slug in db.query(CodingProblem.id, CodingProblem.slug)
            .filter(or_(*[CodingProblem.slug.startswith(prefix) for prefix in FIXTURE_SLUG_PREFIXES]))
            .all()
            if slug not in bank  # never touch a curated bank problem
        ]
        if ids:
            db.query(CodingSubmission).filter(CodingSubmission.problem_id.in_(ids)).delete(synchronize_session=False)
            db.query(InterviewQuestion).filter(InterviewQuestion.problem_id.in_(ids)).update(
                {"problem_id": None}, synchronize_session=False
            )
            db.query(CodingProblem).filter(CodingProblem.id.in_(ids)).delete(synchronize_session=False)
            db.commit()
        return len(ids)
    except Exception:  # database unavailable: tests that need it will report that themselves
        db.rollback()
        return 0
    finally:
        db.close()


@pytest.fixture(scope="session", autouse=True)
def _no_leftover_fixture_problems():
    _purge_fixture_problems()
    yield
    _purge_fixture_problems()
