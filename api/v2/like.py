from queue import Empty

from sqlalchemy.exc import IntegrityError
from tools import api_tools, auth, register_openapi

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
        name="Like Entity",
        description="Like an entity (prompt, application, datasource, etc.).",
        parameters=_PATH_PARAMS,
        available_to_users=True,
    )
    @api_tools.endpoint_metrics
    def post(self, project_id: int, entity: str, entity_id: int):
        try:
            result = self.module.like(
                project_id=project_id, entity=entity, entity_id=entity_id
            )
        except IntegrityError:
            return {"ok": False, "error": "Already liked"}, 400
        return result, 201

    @register_openapi(
        name="Dislike Entity",
        description="Remove a like from an entity.",
        parameters=_PATH_PARAMS,
        available_to_users=True,
    )
    @api_tools.endpoint_metrics
    def delete(self, project_id: int, entity: str, entity_id: int):
        result = self.module.dislike(
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
