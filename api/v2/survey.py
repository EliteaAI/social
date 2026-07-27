from flask import request
from tools import api_tools, config as c, auth, register_openapi

from pylon.core.tools import log

from ...models.pd.surveys import SurveyUpdateModel


class AdminAPI(api_tools.APIModeHandler):
    """Admin Platform single-survey configuration (get / update / delete)."""

    @register_openapi(
        name="Get Survey",
        description="Get a single survey with its questions by id.",
        parameters=[
            {"name": "survey_id", "in": "path", "schema": {"type": "integer"},
             "description": "Survey identifier."},
        ],
        available_to_users=False,
    )
    @auth.decorators.check_api({
        "permissions": ["models.admin.surveys.manage"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": False, "viewer": False},
        }})
    def get(self, survey_id: int, **kwargs):
        result = self.module.get_survey(survey_id)
        return result, 200 if result.get("ok") else 404

    @register_openapi(
        name="Update Survey",
        description="Update a survey and (optionally) replace its questions.",
        parameters=[
            {"name": "survey_id", "in": "path", "schema": {"type": "integer"},
             "description": "Survey identifier."},
        ],
        request_body=SurveyUpdateModel,
        available_to_users=True,
    )
    @auth.decorators.check_api({
        "permissions": ["models.admin.surveys.manage"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": False, "viewer": False},
        }})
    def put(self, survey_id: int, **kwargs):
        result = self.module.update_survey(survey_id, request.get_json())
        return result, 200 if result.get("ok") else 400

    @register_openapi(
        name="Delete Survey",
        description="Delete a survey together with its questions and captured answers.",
        parameters=[
            {"name": "survey_id", "in": "path", "schema": {"type": "integer"},
             "description": "Survey identifier."},
        ],
        available_to_users=False,
    )
    @auth.decorators.check_api({
        "permissions": ["models.admin.surveys.manage"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": False, "viewer": False},
        }})
    def delete(self, survey_id: int, **kwargs):
        result = self.module.delete_survey(survey_id)
        return result, 200 if result.get("ok") else 404


class API(api_tools.APIBase):
    url_params = api_tools.with_modes([
        "<int:survey_id>",
    ])

    mode_handlers = {
        c.ADMINISTRATION_MODE: AdminAPI,
    }
