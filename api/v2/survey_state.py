from tools import api_tools, config as c, auth, register_openapi

from pylon.core.tools import log


class ProjectAPI(api_tools.APIModeHandler):
    """Record that the survey widget was shown to / dismissed by the current user."""

    @register_openapi(
        name="Set Survey User State",
        description="Record widget display state for the current user. "
                    "action='shown' marks the survey as displayed; action='dismiss' marks it dismissed.",
        parameters=[
            {"name": "survey_id", "in": "path", "schema": {"type": "integer"},
             "description": "Survey identifier."},
            {"name": "action", "in": "path", "schema": {"type": "string", "enum": ["shown", "dismiss"]},
             "description": "State action to record."},
        ],
        available_to_users=True,
    )
    @api_tools.endpoint_metrics
    def post(self, survey_id: int, action: str, **kwargs):
        user_id = auth.current_user().get("id")
        if action == "shown":
            result = self.module.mark_survey_shown(survey_id, user_id)
        elif action == "dismiss":
            result = self.module.dismiss_survey(survey_id, user_id)
        else:
            return {"ok": False, "error": f"Unknown action '{action}'"}, 400
        return result, 200 if result.get("ok") else 404


class API(api_tools.APIBase):
    url_params = api_tools.with_modes([
        "<int:survey_id>/<string:action>",
    ])

    mode_handlers = {
        c.DEFAULT_MODE: ProjectAPI,
    }
