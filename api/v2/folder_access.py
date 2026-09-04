import logging

from flask import request

from tools import api_tools, auth, config as c, register_openapi

from ...constants import PROMPT_LIB_MODE
from ...models.pd.folder_access import FolderAccessBulkRemove, FolderAccessBulkUpsert

log = logging.getLogger(__name__)

MANAGE_PERMISSION = {
    "permissions": ["social.folders.permissions.manage"],
    "recommended_roles": {
        c.ADMINISTRATION_MODE: {"admin": True, "editor": False, "viewer": False},
        c.DEFAULT_MODE: {"admin": True, "editor": False, "viewer": False},
    },
}

FOLDER_ID_PARAM = {
    "name": "folder_id", "in": "path", "required": True,
    "schema": {"type": "integer"}, "description": "Folder ID.",
}


def _enrich_with_user_info(overrides: list) -> list:
    """Attach name/email to each exception so the FE does not need a second round-trip."""
    user_ids = [o['user_id'] for o in overrides]
    if not user_ids:
        return overrides
    try:
        users = {u['id']: u for u in auth.list_users(user_ids=user_ids)}
    except Exception as e:  # pylint: disable=W0703
        log.warning("Cannot resolve users for folder access list: %s", e)
        return overrides
    for override in overrides:
        user = users.get(override['user_id']) or {}
        override['user_name'] = user.get('name')
        override['user_email'] = user.get('email')
    return overrides


class PromptLibAPI(api_tools.APIModeHandler):
    """Folder-level permission exceptions (#6524). Admin-only, Team projects only."""

    @register_openapi(
        name="List Folder Access Exceptions",
        description=(
            "List per-user access exceptions stored for a folder. "
            "Users absent from the list keep their role-based (read/write) access."
        ),
        tags=["social"],
        parameters=[FOLDER_ID_PARAM],
        mcp_tool=False,
        available_to_users=False,
    )
    @auth.decorators.check_api(MANAGE_PERMISSION)
    @api_tools.endpoint_metrics
    def get(self, project_id: int, folder_id: int, **kwargs):  # pylint: disable=unused-argument
        result = self.module.list_folder_access(
            project_id=project_id,
            folder_id=folder_id,
        )
        if not result.get('ok'):
            return {"error": result.get('error', 'Folder not found')}, 404

        result['overrides'] = _enrich_with_user_info(result['overrides'])
        return result, 200

    @register_openapi(
        name="Set Folder Access Exceptions",
        description=(
            "Insert or replace access exceptions for the listed users. "
            "Only restrictions are stored: 'read_only' and 'no_access'. "
            "Restoring read/write access is done by deleting the exception."
        ),
        tags=["social"],
        parameters=[FOLDER_ID_PARAM],
        request_body=FolderAccessBulkUpsert,
        mcp_tool=False,
        available_to_users=False,
    )
    @auth.decorators.check_api(MANAGE_PERMISSION)
    @api_tools.endpoint_metrics
    def put(self, project_id: int, folder_id: int, **kwargs):  # pylint: disable=unused-argument
        raw = request.json or {}
        entries = raw.get('entries')
        if not entries:
            return {"error": "entries is required"}, 400

        result = self.module.set_folder_access(
            project_id=project_id,
            folder_id=folder_id,
            entries=entries,
        )
        if not result.get('ok'):
            error = result.get('error', 'Failed to update folder access')
            return {"error": error}, 404 if error == 'Folder not found' else 400

        return result, 200

    @register_openapi(
        name="Remove Folder Access Exceptions",
        description=(
            "Delete access exceptions for the listed users, returning them to "
            "their role-based (read/write) access on the folder."
        ),
        tags=["social"],
        parameters=[FOLDER_ID_PARAM],
        request_body=FolderAccessBulkRemove,
        mcp_tool=False,
        available_to_users=False,
    )
    @auth.decorators.check_api(MANAGE_PERMISSION)
    @api_tools.endpoint_metrics
    def delete(self, project_id: int, folder_id: int, **kwargs):  # pylint: disable=unused-argument
        raw = request.json or {}
        user_ids = raw.get('user_ids')
        if not user_ids:
            return {"error": "user_ids is required"}, 400

        result = self.module.remove_folder_access(
            project_id=project_id,
            folder_id=folder_id,
            user_ids=user_ids,
        )
        if not result.get('ok'):
            return {"error": result.get('error', 'Failed to remove folder access')}, 400

        return result, 200


class API(api_tools.APIBase):
    """Folder permission management endpoints."""
    url_params = api_tools.with_modes([
        '<int:project_id>/<int:folder_id>',
    ])

    mode_handlers = {
        PROMPT_LIB_MODE: PromptLibAPI
    }
