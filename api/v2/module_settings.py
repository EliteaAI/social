from flask import g, request
from tools import api_tools, register_openapi

from ...models.pd.module_settings import ModuleSettingsModel


class ProjectApi(api_tools.APIModeHandler):
    @register_openapi(
        name="Get Project Module Settings",
        description="Get the current user's project-scoped settings (module toggles, mid-turn input) (#6285, #6303).",
        parameters=[
            {"name": "project_id", "in": "path", "required": True, "schema": {"type": "integer"}},
        ],
        available_to_users=True,
    )
    @api_tools.endpoint_metrics
    def get(self, project_id: int, **kwargs):
        user = self.module.context.rpc_manager.timeout(2).auth_main_current_user(g.auth)
        settings = self.module.context.rpc_manager.timeout(2).social_get_project_module_settings(
            user['id'], project_id,
        )
        return settings, 200

    @register_openapi(
        name="Update Project Module Settings",
        description="Update the current user's project-scoped settings (module toggles, mid-turn input) (#6285, #6303).",
        request_body=ModuleSettingsModel,
        parameters=[
            {"name": "project_id", "in": "path", "required": True, "schema": {"type": "integer"}},
        ],
        available_to_users=True,
    )
    @api_tools.endpoint_metrics
    def put(self, project_id: int, **kwargs):
        user = self.module.context.rpc_manager.timeout(2).auth_main_current_user(g.auth)
        try:
            update_data = ModuleSettingsModel(**(request.json or {}))
        except Exception as e:
            return {'error': f'Validation error: {str(e)}'}, 400

        settings = self.module.context.rpc_manager.timeout(2).social_set_project_module_settings(
            user['id'], project_id, update_data.dict(exclude_none=True),
        )
        return settings, 200


class API(api_tools.APIBase):
    url_params = api_tools.with_modes([
        "<int:project_id>",
    ])

    mode_handlers = {
        'default': ProjectApi,
    }
