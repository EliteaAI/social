from datetime import datetime

from pydantic.v1 import ValidationError
from sqlalchemy import desc

from tools import auth, db
from pylon.core.tools import web, log

from ..models.surveys import Survey, SurveyQuestion, SurveyAnswer
from ..models.pd.surveys import SurveyModel, SurveyUpdateModel


def _serialize_survey(survey: Survey, questions: list) -> dict:
    data = survey.to_json()
    data['questions'] = [q.to_json() for q in sorted(questions, key=lambda q: q.position)]
    return data


def _resolve_user_email(user_id: int) -> str:
    try:
        user = auth.get_user(user_id=user_id)
        return user.get('email') if user else None
    except Exception:  # pylint: disable=W0703
        return None


def _upsert_answer_row(session, survey, question, user_id, user_email):
    row = session.query(SurveyAnswer).filter(
        SurveyAnswer.question_id == question.id,
        SurveyAnswer.user_id == user_id,
    ).first()
    if not row:
        row = SurveyAnswer(
            question_id=question.id,
            survey_id=survey.id,
            survey_name=survey.name,
            question_title=question.title,
            user_id=user_id,
            user_email=user_email,
        )
        session.add(row)
    else:
        # Refresh denormalized fields (survey/question may have changed)
        row.survey_name = survey.name
        row.question_title = question.title
        if user_email and not row.user_email:
            row.user_email = user_email
    return row


class RPC:
    @web.rpc("social_list_surveys", "list_surveys")
    def list_surveys(self, only_enabled: bool = False) -> dict:
        with db.with_project_schema_session(None) as session:
            query = session.query(Survey)
            if only_enabled:
                query = query.filter(Survey.enabled.is_(True))
            surveys = query.order_by(Survey.id).all()
            result = []
            for survey in surveys:
                questions = session.query(SurveyQuestion).filter(
                    SurveyQuestion.survey_id == survey.id).all()
                result.append(_serialize_survey(survey, questions))
            return {"ok": True, "result": result}

    @web.rpc("social_get_survey", "get_survey")
    def get_survey(self, survey_id: int) -> dict:
        with db.with_project_schema_session(None) as session:
            survey = session.query(Survey).get(survey_id)
            if not survey:
                return {"ok": False, "error": f"Survey with id '{survey_id}' not found"}
            questions = session.query(SurveyQuestion).filter(
                SurveyQuestion.survey_id == survey.id).all()
            return {"ok": True, "result": _serialize_survey(survey, questions)}

    @web.rpc("social_create_survey", "create_survey")
    def create_survey(self, data: dict) -> dict:
        try:
            payload = SurveyModel.parse_obj(data)
        except ValidationError as e:
            return {"ok": False, "error": str(e)}

        with db.with_project_schema_session(None) as session:
            survey = Survey(
                name=payload.name,
                description=payload.description,
                enabled=payload.enabled,
                dismissible=payload.dismissible,
            )
            session.add(survey)
            session.flush()
            for question in (payload.questions or []):
                session.add(SurveyQuestion(
                    survey_id=survey.id,
                    title=question.title,
                    question_type=question.question_type,
                    options=question.options,
                    position=question.position or 0,
                    created_by=auth.current_user().get("id"),
                ))
            session.commit()
            return self.get_survey(survey.id)

    @web.rpc("social_update_survey", "update_survey")
    def update_survey(self, survey_id: int, payload: dict) -> dict:
        try:
            data = SurveyUpdateModel.parse_obj(payload)
        except ValidationError as e:
            return {"ok": False, "error": str(e)}

        with db.with_project_schema_session(None) as session:
            survey = session.query(Survey).get(survey_id)
            if not survey:
                return {"ok": False, "error": f"Survey with id '{survey_id}' not found"}

            for field in ("name", "description", "enabled", "dismissible"):
                value = getattr(data, field)
                if value is not None:
                    setattr(survey, field, value)

            # Replace questions when provided
            if data.questions is not None:
                session.query(SurveyQuestion).filter(
                    SurveyQuestion.survey_id == survey.id).delete()
                for question in data.questions:
                    session.add(SurveyQuestion(
                        survey_id=survey.id,
                        title=question.title,
                        question_type=question.question_type,
                        options=question.options,
                        position=question.position or 0,
                        created_by=auth.current_user().get("id"),
                    ))
            session.commit()
            return self.get_survey(survey.id)

    @web.rpc("social_delete_survey", "delete_survey")
    def delete_survey(self, survey_id: int) -> dict:
        with db.with_project_schema_session(None) as session:
            survey = session.query(Survey).get(survey_id)
            if not survey:
                return {"ok": False, "error": f"Survey with id '{survey_id}' not found"}
            session.query(SurveyQuestion).filter(
                SurveyQuestion.survey_id == survey_id).delete()
            session.query(SurveyAnswer).filter(
                SurveyAnswer.survey_id == survey_id).delete()
            session.delete(survey)
            session.commit()
            return {"ok": True, "result": "Successfully deleted"}

    @web.rpc("social_get_active_survey_for_user", "get_active_survey_for_user")
    def get_active_survey_for_user(self, user_id: int) -> dict:
        with db.with_project_schema_session(None) as session:
            surveys = session.query(Survey).filter(
                Survey.enabled.is_(True)).order_by(Survey.id).all()
            for survey in surveys:
                questions = session.query(SurveyQuestion).filter(
                    SurveyQuestion.survey_id == survey.id).all()
                if not questions:
                    continue
                question_ids = [q.id for q in questions]
                answers = session.query(SurveyAnswer).filter(
                    SurveyAnswer.survey_id == survey.id,
                    SurveyAnswer.user_id == user_id,
                    SurveyAnswer.question_id.in_(question_ids),
                ).all()
                # AC9: a state row older than the survey's updated_at is stale -> eligible again
                fresh = [a for a in answers if a.updated_at and a.updated_at >= survey.updated_at]
                if any(a.answer is not None for a in fresh):
                    continue  # already answered current version
                if any(a.dismissed for a in fresh):
                    continue  # dismissed current version
                return {"ok": True, "result": _serialize_survey(survey, questions)}
            return {"ok": True, "result": None}

    @web.rpc("social_mark_survey_shown", "mark_survey_shown")
    def mark_survey_shown(self, survey_id: int, user_id: int) -> dict:
        with db.with_project_schema_session(None) as session:
            survey = session.query(Survey).get(survey_id)
            if not survey:
                return {"ok": False, "error": f"Survey with id '{survey_id}' not found"}
            questions = session.query(SurveyQuestion).filter(
                SurveyQuestion.survey_id == survey_id).all()
            user_email = _resolve_user_email(user_id)
            for question in questions:
                row = _upsert_answer_row(session, survey, question, user_id, user_email)
                row.shown = True
            session.commit()
            return {"ok": True, "result": "shown"}

    @web.rpc("social_dismiss_survey", "dismiss_survey")
    def dismiss_survey(self, survey_id: int, user_id: int) -> dict:
        with db.with_project_schema_session(None) as session:
            survey = session.query(Survey).get(survey_id)
            if not survey:
                return {"ok": False, "error": f"Survey with id '{survey_id}' not found"}
            questions = session.query(SurveyQuestion).filter(
                SurveyQuestion.survey_id == survey_id
            ).all()
            user_email = _resolve_user_email(user_id)
            for question in questions:
                row = _upsert_answer_row(session, survey, question, user_id, user_email)
                row.dismissed = True
            session.commit()
            return {"ok": True, "result": "dismissed"}

    @web.rpc("social_submit_survey_response", "submit_survey_response")
    def submit_survey_response(self, survey_id: int, data: dict, user_id: int = None) -> dict:
        if not user_id:
            user_id = auth.current_user().get("id")
        answers = data.get("answers") or []
        if not answers:
            return {"ok": False, "error": "No answers provided"}

        with db.with_project_schema_session(None) as session:
            survey = session.query(Survey).get(survey_id)
            if not survey:
                return {"ok": False, "error": f"Survey with id '{survey_id}' not found"}
            questions = {
                q.id: q for q in session.query(SurveyQuestion).filter(
                    SurveyQuestion.survey_id == survey_id).all()
            }
            user_email = _resolve_user_email(user_id)
            for item in answers:
                question = questions.get(item.get("question_id"))
                if not question:
                    continue
                row = _upsert_answer_row(session, survey, question, user_id, user_email)
                row.answer = {"value": item.get("answer")}
                row.shown = True
            session.commit()
            return {"ok": True, "result": "submitted"}

    @web.rpc("social_list_survey_answers", "list_survey_answers")
    def list_survey_answers(self, survey_id: int, args: dict) -> dict:
        date_from = args.get("date_from")
        date_to = args.get("date_to")
        limit = args.get("limit", 100)
        offset = args.get("offset", 0)

        with db.with_project_schema_session(None) as session:
            query = session.query(SurveyAnswer).filter(
                SurveyAnswer.survey_id == survey_id,
                SurveyAnswer.answer.isnot(None),
            )
            if date_from:
                try:
                    query = query.filter(SurveyAnswer.created_at >= datetime.fromisoformat(date_from))
                except ValueError:
                    pass
            if date_to:
                try:
                    query = query.filter(SurveyAnswer.created_at <= datetime.fromisoformat(date_to))
                except ValueError:
                    pass

            total = query.count()
            query = query.order_by(desc(SurveyAnswer.created_at))
            rows = query.limit(limit).offset(offset).all()
            return {
                "ok": True,
                "result": {"total": total, "rows": [r.to_json() for r in rows]},
            }
