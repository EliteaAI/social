from flask import jsonify
from pylon.core.tools import log
from tools import api_tools, auth, config as c, register_openapi


class ProjectApi(api_tools.APIModeHandler):
    @register_openapi(
        name="List Authors",
        description="List all authors (users) for a project.",
        parameters=[
            {"name": "project_id", "in": "path", "schema": {"type": "integer"},
             "description": "Project identifier."},
        ],
        available_to_users=True,
    )
    @auth.decorators.check_api({
        "permissions": ["models.social.authors.get"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": True},
            c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": True},
        }})
    @api_tools.endpoint_metrics
    def get(self, project_id: int, **kwargs):
        user_ids = self.module.context.rpc_manager.timeout(5).admin_get_users_ids_in_project(
            project_id=project_id,
            filter_system_user=True
        )
        return jsonify(self.module.get_authors(user_ids))


class API(api_tools.APIBase):
    url_params = api_tools.with_modes([
        '<int:project_id>',
    ])

    mode_handlers = {c.DEFAULT_MODE: ProjectApi}
