"""Unit tests for survey Pydantic models."""
import sys
import pytest
from pydantic.v1 import ValidationError


@pytest.fixture(scope='module')
def surveys_module(models_path):
    pd_path = models_path / "pd"
    sys.path.insert(0, str(pd_path))
    try:
        import surveys
        return surveys
    finally:
        sys.path.remove(str(pd_path))


class TestSurveyQuestionModel:
    def test_valid_slider_question(self, surveys_module):
        q = surveys_module.SurveyQuestionModel(
            title="How likely are you to recommend?",
            question_type="slider",
            options={"min": 0, "max": 10},
            position=0,
        )
        assert q.question_type == "slider"
        assert q.position == 0

    def test_valid_all_question_types(self, surveys_module):
        SurveyQuestionModel = surveys_module.SurveyQuestionModel
        for qt in ("open", "radio", "checkbox", "slider"):
            q = SurveyQuestionModel(title="Q", question_type=qt)
            assert q.question_type == qt

    def test_invalid_question_type_raises(self, surveys_module):
        with pytest.raises(ValidationError) as exc_info:
            surveys_module.SurveyQuestionModel(title="Q", question_type="matrix")
        assert "question_type must be one of" in str(exc_info.value)

    def test_default_question_type_is_open(self, surveys_module):
        q = surveys_module.SurveyQuestionModel(title="Anything")
        assert q.question_type == "open"

    def test_default_position_is_zero(self, surveys_module):
        q = surveys_module.SurveyQuestionModel(title="Q", question_type="open")
        assert q.position == 0

    def test_optional_id_defaults_none(self, surveys_module):
        q = surveys_module.SurveyQuestionModel(title="Q")
        assert q.id is None

    def test_options_can_be_none(self, surveys_module):
        q = surveys_module.SurveyQuestionModel(title="Q", question_type="open", options=None)
        assert q.options is None

    def test_options_accepts_dict(self, surveys_module):
        q = surveys_module.SurveyQuestionModel(
            title="Q",
            question_type="slider",
            options={"min": 0, "max": 10, "min_label": "Not likely", "max_label": "Very likely"},
        )
        assert q.options["max"] == 10

    def test_missing_title_raises(self, surveys_module):
        with pytest.raises(ValidationError):
            surveys_module.SurveyQuestionModel(question_type="open")


class TestSurveyModel:
    def test_valid_survey(self, surveys_module):
        s = surveys_module.SurveyModel(name="NPS Elitea")
        assert s.name == "NPS Elitea"
        assert s.enabled is False
        assert s.dismissible is False
        assert s.questions == []

    def test_survey_with_questions(self, surveys_module):
        s = surveys_module.SurveyModel(
            name="Test",
            enabled=True,
            questions=[
                {"title": "Q1", "question_type": "open"},
                {"title": "Q2", "question_type": "slider"},
            ],
        )
        assert len(s.questions) == 2
        assert s.questions[0].question_type == "open"

    def test_question_type_validated_inside_survey(self, surveys_module):
        with pytest.raises(ValidationError):
            surveys_module.SurveyModel(
                name="Bad",
                questions=[{"title": "Q", "question_type": "invalid"}],
            )

    def test_missing_name_raises(self, surveys_module):
        with pytest.raises(ValidationError):
            surveys_module.SurveyModel()

    def test_description_optional(self, surveys_module):
        s = surveys_module.SurveyModel(name="X", description=None)
        assert s.description is None


class TestSurveyUpdateModel:
    def test_empty_update_all_none(self, surveys_module):
        u = surveys_module.SurveyUpdateModel()
        assert u.name is None
        assert u.enabled is None
        assert u.questions is None

    def test_partial_update_name_only(self, surveys_module):
        u = surveys_module.SurveyUpdateModel(name="Renamed")
        assert u.name == "Renamed"
        assert u.enabled is None

    def test_update_with_questions(self, surveys_module):
        u = surveys_module.SurveyUpdateModel(
            questions=[{"title": "Q", "question_type": "radio"}]
        )
        assert len(u.questions) == 1
        assert u.questions[0].question_type == "radio"

    def test_invalid_question_type_in_update_raises(self, surveys_module):
        with pytest.raises(ValidationError):
            surveys_module.SurveyUpdateModel(
                questions=[{"title": "Q", "question_type": "bad"}]
            )


class TestSurveyResponseSubmitModel:
    def test_valid_response(self, surveys_module):
        r = surveys_module.SurveyResponseSubmitModel(
            answers=[{"question_id": 1, "answer": 9}]
        )
        assert len(r.answers) == 1
        assert r.answers[0].question_id == 1
        assert r.answers[0].answer == 9

    def test_multiple_answers(self, surveys_module):
        r = surveys_module.SurveyResponseSubmitModel(
            answers=[
                {"question_id": 1, "answer": 7},
                {"question_id": 2, "answer": "Very satisfied"},
            ]
        )
        assert len(r.answers) == 2

    def test_answer_accepts_any_type(self, surveys_module):
        SurveyResponseSubmitModel = surveys_module.SurveyResponseSubmitModel
        for val in (0, "text", ["a", "b"], {"key": "v"}, True):
            r = SurveyResponseSubmitModel(answers=[{"question_id": 1, "answer": val}])
            assert r.answers[0].answer == val

    def test_missing_answers_raises(self, surveys_module):
        with pytest.raises(ValidationError):
            surveys_module.SurveyResponseSubmitModel()

    def test_missing_question_id_raises(self, surveys_module):
        with pytest.raises(ValidationError):
            surveys_module.SurveyResponseSubmitModel(answers=[{"answer": 5}])


class TestSurveyReportQueryModel:
    def test_defaults(self, surveys_module):
        q = surveys_module.SurveyReportQueryModel()
        assert q.limit == 100
        assert q.offset == 0
        assert q.date_from is None
        assert q.date_to is None

    def test_custom_values(self, surveys_module):
        q = surveys_module.SurveyReportQueryModel(
            date_from="2024-01-01T00:00:00",
            date_to="2024-12-31T23:59:59",
            limit=50,
            offset=100,
        )
        assert q.limit == 50
        assert q.offset == 100
        assert q.date_from == "2024-01-01T00:00:00"
