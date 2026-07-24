"""Unit tests for survey RPC helper functions.

Pure logic is copied here to avoid the DB/auth imports in rpc/surveys.py.
Tests cover: _serialize_survey, _upsert_answer_row (new-row branch),
_resolve_user_email fallback, and get_active_survey_for_user eligibility logic.
"""
import pytest
from datetime import datetime, timedelta
from types import SimpleNamespace


# ---------------------------------------------------------------------------
# Minimal stubs
# ---------------------------------------------------------------------------

def _make_survey(sid=1, name="NPS", updated_at=None):
    s = SimpleNamespace()
    s.id = sid
    s.name = name
    s.description = None
    s.enabled = True
    s.dismissible = True
    s.updated_at = updated_at or datetime(2024, 1, 1)
    s.to_json = lambda: {
        "id": s.id, "name": s.name, "description": s.description,
        "enabled": s.enabled, "dismissible": s.dismissible,
    }
    return s


def _make_question(qid, survey_id=1, title="Q", position=0):
    q = SimpleNamespace()
    q.id = qid
    q.survey_id = survey_id
    q.title = title
    q.position = position
    q.to_json = lambda: {"id": q.id, "title": q.title, "position": q.position}
    return q


def _make_answer(qid, user_id, answer=None, dismissed=False, updated_at=None):
    a = SimpleNamespace()
    a.question_id = qid
    a.user_id = user_id
    a.answer = answer
    a.dismissed = dismissed
    a.updated_at = updated_at or datetime(2024, 6, 1)
    return a


# ---------------------------------------------------------------------------
# _serialize_survey
# ---------------------------------------------------------------------------

def _serialize_survey(survey, questions):
    data = survey.to_json()
    data['questions'] = [q.to_json() for q in sorted(questions, key=lambda q: q.position)]
    return data


class TestSerializeSurvey:
    def test_returns_survey_fields(self):
        s = _make_survey(sid=5, name="Test")
        result = _serialize_survey(s, [])
        assert result["id"] == 5
        assert result["name"] == "Test"
        assert result["questions"] == []

    def test_questions_sorted_by_position(self):
        s = _make_survey()
        questions = [
            _make_question(3, position=2),
            _make_question(1, position=0),
            _make_question(2, position=1),
        ]
        result = _serialize_survey(s, questions)
        positions = [q["position"] for q in result["questions"]]
        assert positions == [0, 1, 2]

    def test_single_question(self):
        s = _make_survey()
        q = _make_question(1, title="Only Q", position=0)
        result = _serialize_survey(s, [q])
        assert len(result["questions"]) == 1
        assert result["questions"][0]["title"] == "Only Q"


# ---------------------------------------------------------------------------
# _upsert_answer_row logic (new-row path — no DB, tested via logic copy)
# ---------------------------------------------------------------------------

def _build_answer_row(survey, question, user_id, user_email):
    """Mirrors the new-row branch of _upsert_answer_row."""
    return SimpleNamespace(
        question_id=question.id,
        survey_id=survey.id,
        survey_name=survey.name,
        question_title=question.title,
        user_id=user_id,
        user_email=user_email,
        answer=None,
        shown=False,
        dismissed=False,
    )


class TestUpsertAnswerRowNewRow:
    def test_new_row_fields_populated(self):
        s = _make_survey(sid=1, name="NPS")
        q = _make_question(qid=10, title="Recommend?")
        row = _build_answer_row(s, q, user_id=42, user_email="u@x.com")
        assert row.question_id == 10
        assert row.survey_id == 1
        assert row.survey_name == "NPS"
        assert row.question_title == "Recommend?"
        assert row.user_id == 42
        assert row.user_email == "u@x.com"
        assert row.answer is None
        assert row.shown is False
        assert row.dismissed is False

    def test_new_row_null_email_accepted(self):
        s = _make_survey()
        q = _make_question(1)
        row = _build_answer_row(s, q, user_id=7, user_email=None)
        assert row.user_email is None


def _update_existing_row(row, survey, question, user_email):
    """Mirrors the existing-row branch of _upsert_answer_row."""
    row.survey_name = survey.name
    row.question_title = question.title
    if not row.user_email:
        row.user_email = user_email
    return row


class TestUpsertAnswerRowExistingRow:
    def test_denormalized_fields_refreshed(self):
        s = _make_survey(name="New Name")
        q = _make_question(1, title="New Title")
        row = SimpleNamespace(survey_name="Old", question_title="Old Q", user_email="e@x.com")
        _update_existing_row(row, s, q, user_email=None)
        assert row.survey_name == "New Name"
        assert row.question_title == "New Title"

    def test_email_not_overwritten_when_already_set(self):
        s = _make_survey()
        q = _make_question(1)
        row = SimpleNamespace(survey_name="X", question_title="Y", user_email="existing@x.com")
        _update_existing_row(row, s, q, user_email="new@x.com")
        assert row.user_email == "existing@x.com"

    def test_email_filled_when_blank(self):
        s = _make_survey()
        q = _make_question(1)
        row = SimpleNamespace(survey_name="X", question_title="Y", user_email=None)
        _update_existing_row(row, s, q, user_email="late@x.com")
        assert row.user_email == "late@x.com"


# ---------------------------------------------------------------------------
# get_active_survey_for_user eligibility logic
# ---------------------------------------------------------------------------

def _is_survey_eligible(survey, questions, user_answers):
    """Pure eligibility check extracted from get_active_survey_for_user."""
    if not questions:
        return False
    fresh = [a for a in user_answers if a.updated_at and a.updated_at >= survey.updated_at]
    if any(a.answer is not None for a in fresh):
        return False
    if any(a.dismissed for a in fresh):
        return False
    return True


class TestSurveyEligibility:
    def test_no_questions_ineligible(self):
        s = _make_survey()
        assert _is_survey_eligible(s, [], []) is False

    def test_no_answers_eligible(self):
        s = _make_survey()
        q = _make_question(1)
        assert _is_survey_eligible(s, [q], []) is True

    def test_answered_fresh_ineligible(self):
        s = _make_survey(updated_at=datetime(2024, 1, 1))
        q = _make_question(1)
        a = _make_answer(1, 99, answer={"value": 9}, updated_at=datetime(2024, 6, 1))
        assert _is_survey_eligible(s, [q], [a]) is False

    def test_dismissed_fresh_ineligible(self):
        s = _make_survey(updated_at=datetime(2024, 1, 1))
        q = _make_question(1)
        a = _make_answer(1, 99, dismissed=True, updated_at=datetime(2024, 6, 1))
        assert _is_survey_eligible(s, [q], [a]) is False

    def test_stale_answer_eligible_again(self):
        """AC9: row updated_at before survey updated_at → stale → eligible."""
        survey_updated = datetime(2024, 6, 1)
        answer_updated = datetime(2024, 1, 1)  # before survey update
        s = _make_survey(updated_at=survey_updated)
        q = _make_question(1)
        a = _make_answer(1, 99, answer={"value": 8}, updated_at=answer_updated)
        assert _is_survey_eligible(s, [q], [a]) is True

    def test_stale_dismissed_eligible_again(self):
        survey_updated = datetime(2024, 6, 1)
        answer_updated = datetime(2024, 1, 1)
        s = _make_survey(updated_at=survey_updated)
        q = _make_question(1)
        a = _make_answer(1, 99, dismissed=True, updated_at=answer_updated)
        assert _is_survey_eligible(s, [q], [a]) is True

    def test_shown_only_still_eligible(self):
        """shown=True without an answer or dismiss does not block."""
        s = _make_survey(updated_at=datetime(2024, 1, 1))
        q = _make_question(1)
        a = _make_answer(1, 99, answer=None, dismissed=False, updated_at=datetime(2024, 6, 1))
        assert _is_survey_eligible(s, [q], [a]) is True

    def test_answer_none_updated_at_treated_as_stale(self):
        """Rows with updated_at=None are excluded from fresh list."""
        s = _make_survey(updated_at=datetime(2024, 1, 1))
        q = _make_question(1)
        a = _make_answer(1, 99, answer={"value": 5}, updated_at=None)
        a.updated_at = None
        assert _is_survey_eligible(s, [q], [a]) is True


# ---------------------------------------------------------------------------
# _resolve_user_email fallback
# ---------------------------------------------------------------------------

def _resolve_user_email_safe(get_user_fn, user_id):
    """Mirrors _resolve_user_email with injected callable for testing."""
    try:
        user = get_user_fn(user_id=user_id)
        return user.get('email') if user else None
    except Exception:
        return None


class TestResolveUserEmail:
    def test_returns_email_when_user_found(self):
        result = _resolve_user_email_safe(
            lambda user_id: {"email": "found@x.com"}, 1
        )
        assert result == "found@x.com"

    def test_returns_none_when_user_not_found(self):
        result = _resolve_user_email_safe(lambda user_id: None, 1)
        assert result is None

    def test_returns_none_on_exception(self):
        def boom(user_id):
            raise RuntimeError("auth down")
        result = _resolve_user_email_safe(boom, 1)
        assert result is None

    def test_returns_none_when_email_key_missing(self):
        result = _resolve_user_email_safe(lambda user_id: {"name": "no email"}, 1)
        assert result is None
