from flask import request
from tools import api_tools, config as c, auth, register_openapi
from pydantic.v1 import ValidationError

from pylon.core.tools import log

from ...models.pd.surveys import SurveyModel, SurveyUpdateModel, SurveyResponseSubmitModel


class ProjectAPI(api_tools.APIModeHandler):
    """End-user facing survey endpoints (logged-in platform users)."""

    @register_openapi(
        name="Get Active Survey",
        description="Get the enabled survey the current user should be shown, if any.",
        available_to_users=True,
    )
    @auth.decorators.check_api({
        "permissions": ["models.social.surveys.view"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": True},
            c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": True},
        }})
    def get(self, project_id: int | None = None, **kwargs):
        user_id = auth.current_user().get("id")
        result = self.module.get_active_survey_for_user(user_id)
        return result, 200


class AdminAPI(api_tools.APIModeHandler):
    """Admin Platform survey configuration (list all surveys)."""

    @register_openapi(
        name="List Surveys",
        description="List all configured surveys with their questions.",
        available_to_users=True,
    )
    @auth.decorators.check_api({
        "permissions": ["models.admin.surveys.manage"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": False, "viewer": False},
        }})
    def get(self, **kwargs):
        result = self.module.list_surveys()
        return result, 200

    @register_openapi(
        name="Create Survey",
        description="Create a new survey with questions.",
        request_body=SurveyModel,
        available_to_users=True,
    )
    @auth.decorators.check_api({
        "permissions": ["models.admin.surveys.manage"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": False, "viewer": False},
        }})
    def post(self, **kwargs):
        result = self.module.create_survey(request.get_json())
        return result, 201 if result.get("ok") else 400


class API(api_tools.APIBase):
    url_params = api_tools.with_modes([
        "",
        "<int:project_id>",
    ])

    mode_handlers = {
        c.DEFAULT_MODE: ProjectAPI,
        c.ADMINISTRATION_MODE: AdminAPI,
    }
