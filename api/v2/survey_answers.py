from flask import request
from tools import api_tools, config as c, auth, register_openapi

from pylon.core.tools import log


class AdminAPI(api_tools.APIModeHandler):
    """Survey responses report source — paginated answers filtered by exact date range."""

    @register_openapi(
        name="List Survey Answers",
        description="List captured survey answers for a survey, filtered by date range and paginated. "
                    "Used by the Reports menu to build the XLSX export.",
        parameters=[
            {"name": "survey_id", "in": "path", "schema": {"type": "integer"},
             "description": "Survey identifier."},
            {"name": "date_from", "in": "query", "schema": {"type": "string", "format": "date-time"},
             "description": "ISO 8601 lower bound (inclusive) on response date."},
            {"name": "date_to", "in": "query", "schema": {"type": "string", "format": "date-time"},
             "description": "ISO 8601 upper bound (inclusive) on response date."},
            {"name": "limit", "in": "query", "schema": {"type": "integer"},
             "description": "Max rows to return."},
            {"name": "offset", "in": "query", "schema": {"type": "integer"},
             "description": "Row offset for pagination."},
        ],
        available_to_users=True,
    )
    @auth.decorators.check_api({
        "permissions": ["models.admin.surveys.reports.view"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": False, "viewer": False},
        }})
    def get(self, survey_id: int, **kwargs):
        args = dict(request.args)
        if "limit" in args:
            try:
                args["limit"] = min(int(args["limit"]), 1000)
            except (TypeError, ValueError):
                args.pop("limit")
        if "offset" in args:
            try:
                args["offset"] = int(args["offset"])
            except (TypeError, ValueError):
                args.pop("offset")
        result = self.module.list_survey_answers(survey_id, args)
        return result, 200


class API(api_tools.APIBase):
    url_params = api_tools.with_modes([
        "<int:survey_id>",
    ])

    mode_handlers = {
        c.ADMINISTRATION_MODE: AdminAPI,
    }
