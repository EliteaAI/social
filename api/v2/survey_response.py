from flask import request
from tools import api_tools, config as c, auth, register_openapi
from pydantic.v1 import ValidationError

from pylon.core.tools import log

from ...models.pd.surveys import SurveyResponseSubmitModel


class ProjectAPI(api_tools.APIModeHandler):
    """Submit a survey response for the current user."""

    @register_openapi(
        name="Submit Survey Response",
        description="Submit the current user's answers to a survey.",
        parameters=[
            {"name": "survey_id", "in": "path", "schema": {"type": "integer"},
             "description": "Survey identifier."},
        ],
        request_body=SurveyResponseSubmitModel,
        available_to_users=False,
    )
    @api_tools.endpoint_metrics
    def post(self, survey_id: int, **kwargs):
        try:
            data = SurveyResponseSubmitModel.parse_obj(request.get_json())
        except ValidationError as e:
            return {"ok": False, "errors": e.errors()}, 400
        user_id = auth.current_user().get("id")
        result = self.module.submit_survey_response(survey_id, data.dict(), user_id)
        return result, 201 if result.get("ok") else 400


class API(api_tools.APIBase):
    url_params = api_tools.with_modes([
        "<int:survey_id>",
    ])

    mode_handlers = {
        c.DEFAULT_MODE: ProjectAPI,
    }
