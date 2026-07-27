from flask import request
from tools import api_tools, config as c, auth, register_openapi

from pylon.core.tools import log


class ProjectAPI(api_tools.APIModeHandler):
    """List the enabled surveys the current user has not yet been shown."""

    @register_openapi(
        name="List Current Surveys",
        description="List enabled surveys the current user has not yet been shown "
                    "(excluding surveys already answered or dismissed in the current version). "
                    "Filterable by name, sorted by newest first, paginated.",
        parameters=[
            {"name": "name", "in": "query", "schema": {"type": "string"},
             "description": "Case-insensitive substring filter on survey name."},
            {"name": "limit", "in": "query", "schema": {"type": "integer"},
             "description": "Max surveys to return (default 10)."},
            {"name": "offset", "in": "query", "schema": {"type": "integer"},
             "description": "Row offset for pagination."},
        ],
        available_to_users=True,
    )
    @api_tools.endpoint_metrics
    def get(self, **kwargs):
        user_id = auth.current_user().get("id")
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
        result = self.module.list_current_surveys_for_user(user_id, args)
        return result, 200


class API(api_tools.APIBase):
    url_params = api_tools.with_modes([
        "",
    ])

    mode_handlers = {
        c.DEFAULT_MODE: ProjectAPI,
    }
