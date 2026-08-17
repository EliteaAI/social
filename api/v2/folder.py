import logging

from flask import request

from tools import api_tools, auth, config as c, register_openapi

from ...constants import PROMPT_LIB_MODE
from ...models.pd.folders import EntityFolderUpdate

log = logging.getLogger(__name__)


class PromptLibAPI(api_tools.APIModeHandler):
    """Handles single-item operations: get, update, patch, delete folder."""

    @register_openapi(
        name="Get Entity Folder",
        description="Get details of a specific folder",
        tags=["social"],
        parameters=[
            {"name": "folder_id", "in": "path", "required": True, "schema": {"type": "integer"}, "description": "Folder ID."},
        ],
        available_to_users=True,
    )
    @auth.decorators.check_api({
        "permissions": ["social.folders.list"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
            c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": True},
        },
    })
    @api_tools.endpoint_metrics
    def get(self, project_id: int, folder_id: int, **kwargs):  # pylint: disable=unused-argument
        folder = self.module.get_folder(
            project_id=project_id,
            folder_id=folder_id
        )
        if not folder:
            return {"error": "Folder not found"}, 404

        return folder, 200

    @register_openapi(
        name="Update Entity Folder",
        description="Update a folder's name or metadata",
        mcp_description="""
        USE to rename a folder.

        DO NOT USE to delete a folder → use the folder DELETE endpoint.
        DO NOT USE to move entities between folders → use entity-specific move endpoints.

        Examples:
        1. Rename: { 'name': 'Q3 Review Agents' }
        """,
        tags=["social"],
        mcp_tool=True,
        parameters=[
            {"name": "folder_id", "in": "path", "required": True, "schema": {"type": "integer"}, "description": "Folder ID."},
        ],
        request_body=EntityFolderUpdate,
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
    def put(self, project_id: int, folder_id: int, **kwargs):  # pylint: disable=unused-argument
        raw = dict(request.json)

        result = self.module.update_folder(
            project_id=project_id,
            folder_id=folder_id,
            name=raw.get('name'),
            meta=raw.get('meta')
        )

        if not result.get('ok'):
            return {"error": result.get('error', 'Failed to update folder')}, 404

        return result['folder'], 200

    @register_openapi(
        name="Patch Entity Folder",
        description="Update folder pin status.",
        tags=["social"],
        parameters=[
            {"name": "folder_id", "in": "path", "required": True, "schema": {"type": "integer"}, "description": "Folder ID."},
        ],
        request_body={
            "required": True,
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "required": ["is_pinned"],
                        "properties": {
                            "is_pinned": {
                                "type": "boolean",
                                "description": "Set to true to pin the folder, false to unpin.",
                            }
                        },
                    }
                }
            },
        },
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
    def patch(self, project_id: int, folder_id: int, **kwargs):  # pylint: disable=unused-argument
        """Update folder pin status."""
        raw = dict(request.json)
        is_pinned_raw = raw.get('is_pinned')

        if is_pinned_raw is None:
            return {"error": "is_pinned is required"}, 400

        if isinstance(is_pinned_raw, int):
            is_pinned = is_pinned_raw != 0
        elif isinstance(is_pinned_raw, str):
            is_pinned = is_pinned_raw.lower() in ('true', '1')
        elif isinstance(is_pinned_raw, bool):
            is_pinned = is_pinned_raw
        else:
            return {"error": "is_pinned must be a boolean value"}, 400

        result = self.module.pin_folder(
            project_id=project_id,
            folder_id=folder_id,
            is_pinned=is_pinned
        )

        if not result.get('ok'):
            return {"error": result.get('error', 'Failed to update folder')}, 404

        return result['folder'], 200

    @register_openapi(
        name="Delete Entity Folder",
        description="Delete a folder. Entities in the folder are unassigned (not deleted).",
        tags=["social"],
        parameters=[
            {"name": "folder_id", "in": "path", "required": True, "schema": {"type": "integer"}, "description": "Folder ID."},
        ],
        available_to_users=True,
    )
    @auth.decorators.check_api({
        "permissions": ["social.folders.delete"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
            c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
        },
    })
    @api_tools.endpoint_metrics
    def delete(self, project_id: int, folder_id: int, **kwargs):  # pylint: disable=unused-argument
        result = self.module.delete_folder(
            project_id=project_id,
            folder_id=folder_id
        )

        if not result.get('ok'):
            return {"error": result.get('error', 'Folder not found')}, 404

        return {}, 204


class API(api_tools.APIBase):
    """Item endpoints: get, update, patch, delete (folder_id required)."""
    url_params = api_tools.with_modes([
        '<int:project_id>/<int:folder_id>',
    ])

    mode_handlers = {
        PROMPT_LIB_MODE: PromptLibAPI
    }
