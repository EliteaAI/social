import logging
from typing import Optional

from flask import request
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import text

from pylon.core.tools import web

from tools import api_tools, auth, config as c, db, register_openapi

from ...models.folders import EntityFolder

log = logging.getLogger(__name__)


ENTITY_TABLE_MAP = {
    "application": "applications",
    "skill": "skills",
    "toolkit": "elitea_tools",
    "configuration": "configuration",
}


class MoveToFolderRequest(BaseModel):
    entity_type: str = Field(..., description="Entity type: 'application', 'skill', 'toolkit', 'configuration'")
    entity_id: int = Field(..., description="Entity ID to move")
    folder_id: Optional[int] = Field(None, description="Target folder ID. Set to null to remove from folder.")
    sub_type: Optional[str] = Field(None, description="For applications: 'openai' or 'pipeline'. Required when moving to a folder.")


class PromptLibAPI(api_tools.APIModeHandler):

    @register_openapi(
        name="Move Entity to Folder",
        description="Move any entity (application, skill, toolkit, configuration) to a folder or remove from folder",
        mcp_description="""
        USE to move an entity into a folder, or remove it from a folder.

        Supported entity types: application, skill, toolkit, configuration

        Examples:
        1. Move agent to folder: { "entity_type": "application", "entity_id": 7, "folder_id": 5, "sub_type": "openai" }
        2. Move skill to folder: { "entity_type": "skill", "entity_id": 3, "folder_id": 2 }
        3. Remove from folder: { "entity_type": "toolkit", "entity_id": 10, "folder_id": null }

        Validation:
        - Folder must exist and belong to the current user
        - Folder's entity_type must match the entity being moved
        - For applications: sub_type must match folder's sub_type (openai vs pipeline)
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
        user_id = auth.current_user().get("id")

        try:
            parsed = MoveToFolderRequest.model_validate(raw)
        except ValidationError as e:
            return e.errors(), 400

        if parsed.entity_type not in ENTITY_TABLE_MAP:
            return {"error": f"Invalid entity_type. Must be one of: {list(ENTITY_TABLE_MAP.keys())}"}, 400

        table_name = ENTITY_TABLE_MAP[parsed.entity_type]
        schema = f"p_{project_id}"

        with db.get_session(project_id) as session:
            # Verify entity exists
            check_entity_sql = text(f"SELECT id FROM {schema}.{table_name} WHERE id = :entity_id")
            entity = session.execute(check_entity_sql, {"entity_id": parsed.entity_id}).fetchone()
            if not entity:
                return {"error": f"{parsed.entity_type.capitalize()} not found"}, 404

            # If folder_id is None, remove from folder
            if parsed.folder_id is None:
                update_sql = text(f"UPDATE {schema}.{table_name} SET folder_id = NULL WHERE id = :entity_id")
                session.execute(update_sql, {"entity_id": parsed.entity_id})
                session.commit()
                return {
                    "message": f"{parsed.entity_type.capitalize()} removed from folder",
                    "entity_type": parsed.entity_type,
                    "entity_id": parsed.entity_id,
                    "folder_id": None
                }, 200

            # Verify folder exists and belongs to user
            folder = session.query(EntityFolder).filter(
                EntityFolder.id == parsed.folder_id,
                EntityFolder.owner_id == user_id
            ).first()
            if not folder:
                return {"error": "Folder not found or you don't have permission"}, 404

            # Verify folder entity_type matches
            if folder.entity_type != parsed.entity_type:
                return {
                    "error": f"Folder type mismatch. Folder is for '{folder.entity_type}' but entity is '{parsed.entity_type}'"
                }, 400

            # For applications, verify sub_type match
            if parsed.entity_type == "application":
                if not parsed.sub_type:
                    return {"error": "sub_type is required for applications (openai or pipeline)"}, 400
                if folder.sub_type != parsed.sub_type:
                    return {
                        "error": f"Folder sub_type mismatch. Folder is '{folder.sub_type}' but application is '{parsed.sub_type}'"
                    }, 400

            # Move entity to folder
            update_sql = text(f"UPDATE {schema}.{table_name} SET folder_id = :folder_id WHERE id = :entity_id")
            session.execute(update_sql, {"folder_id": parsed.folder_id, "entity_id": parsed.entity_id})
            session.commit()

            log.info("Moved %s %s to folder %s", parsed.entity_type, parsed.entity_id, parsed.folder_id)
            return {
                "message": f"{parsed.entity_type.capitalize()} moved to folder",
                "entity_type": parsed.entity_type,
                "entity_id": parsed.entity_id,
                "folder_id": parsed.folder_id
            }, 200


class API(api_tools.APIBase):
    url_params = api_tools.with_modes([
        '<int:project_id>',
    ])

    mode_handlers = {
        c.DEFAULT_MODE: PromptLibAPI,
    }
