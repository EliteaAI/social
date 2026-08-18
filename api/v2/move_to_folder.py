import logging

from flask import request
from pydantic import ValidationError

from tools import api_tools, auth, config as c, register_openapi

from ...constants import PROMPT_LIB_MODE, is_valid_folder_entity
from ...models.pd.folders import MoveToFolderRequest
from ...models.enums.entity import FOLDER_ENTITY_TYPES

log = logging.getLogger(__name__)


class PromptLibAPI(api_tools.APIModeHandler):

    @register_openapi(
        name="Move Entity to Folder",
        description="Move any entity (agent, pipeline, skill, toolkit, mcp, configuration) to a folder or remove from folder",
        mcp_description="""
        USE to move an entity into a folder, or remove it from a folder.

        Supported entity types: agent, pipeline, skill, toolkit, mcp, configuration

        Examples:
        1. Move agent to folder: { "entity_type": "agent", "entity_id": 7, "folder_id": 5 }
        2. Move pipeline to folder: { "entity_type": "pipeline", "entity_id": 3, "folder_id": 2 }
        3. Move skill to folder: { "entity_type": "skill", "entity_id": 3, "folder_id": 2 }
        4. Remove from folder: { "entity_type": "toolkit", "entity_id": 10, "folder_id": null }

        Validation:
        - Entity must exist
        - Folder must exist and belong to the current user
        - Folder's entity_type must match the entity being moved
        """,
        tags=["social"],
        mcp_tool=True,
        request_body=MoveToFolderRequest,
        available_to_users=True,
    )
    @auth.decorators.check_api({
        "permissions": ["social.folders.update"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
            c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
        },
    })
    @api_tools.endpoint_metrics
    def put(self, project_id: int, **kwargs):
        raw = dict(request.json)

        try:
            parsed = MoveToFolderRequest.model_validate(raw)
        except ValidationError as e:
            return e.errors(), 400

        if not is_valid_folder_entity(parsed.entity_type):
            valid = ', '.join(e.value for e in FOLDER_ENTITY_TYPES)
            return {"error": f"Invalid entity_type. Must be one of: {valid}"}, 400

        # Use RPC to move entity to folder
        result = self.module.move_entity_to_folder(
            project_id=project_id,
            entity_type=parsed.entity_type,
            entity_id=parsed.entity_id,
            folder_id=parsed.folder_id
        )

        if not result.get('ok'):
            error = result.get('error', 'Failed to move entity')
            # Determine appropriate status code
            if 'not found' in error.lower():
                return {"error": error}, 404
            return {"error": error}, 400

        return {
            "message": result.get('message'),
            "entity_type": result.get('entity_type'),
            "entity_id": result.get('entity_id'),
            "folder_id": result.get('folder_id')
        }, 200


class API(api_tools.APIBase):
    url_params = api_tools.with_modes([
        '<int:project_id>',
    ])

    mode_handlers = {
        PROMPT_LIB_MODE: PromptLibAPI,
    }
