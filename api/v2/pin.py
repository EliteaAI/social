from tools import api_tools, register_openapi

from ...constants import PROMPT_LIB_MODE

_PATH_PARAMS = [
    {"name": "project_id", "in": "path", "schema": {"type": "integer"},
     "description": "Project identifier."},
    {"name": "entity", "in": "path", "schema": {"type": "string"},
     "description": "Entity type (e.g. prompt, application, datasource, toolkit, configuration, conversation)."},
    {"name": "entity_id", "in": "path", "schema": {"type": "integer"},
     "description": "Entity identifier."},
]


class PromptLibAPI(api_tools.APIModeHandler):
    @register_openapi(
        name="Pin Entity",
        description="Pin an entity to the user's pinned list.",
        parameters=_PATH_PARAMS,
        available_to_users=True,
    )
    @api_tools.endpoint_metrics
    def post(self, project_id: int, entity: str, entity_id: int):
        result = self.module.pin(
            project_id=project_id, entity=entity, entity_id=entity_id
        )
        if result.get('ok'):
            return result, 201
        return result, 400

    @register_openapi(
        name="Unpin Entity",
        description="Remove an entity from the user's pinned list.",
        parameters=_PATH_PARAMS,
        available_to_users=True,
    )
    @api_tools.endpoint_metrics
    def delete(self, project_id: int, entity: str, entity_id: int):
        result = self.module.unpin(
            project_id=project_id, entity=entity, entity_id=entity_id
        )
        return result, 204


class API(api_tools.APIBase):
    url_params = api_tools.with_modes(
        [
            "<int:project_id>/<string:entity>/<int:entity_id>",
        ]
    )

    mode_handlers = {
        PROMPT_LIB_MODE: PromptLibAPI,
    }
