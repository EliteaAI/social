import logging

from flask import request

from tools import api_tools, auth, config as c, register_openapi

from ...constants import PROMPT_LIB_MODE

log = logging.getLogger(__name__)


class PromptLibAPI(api_tools.APIModeHandler):
    """Get paginated list of entities in a folder."""

    @register_openapi(
        name="Get Folder Items",
        description="Get paginated list of entity IDs in a folder for efficient loading",
        mcp_description="""
        USE to get paginated entity IDs from a folder.

        Returns entity IDs that can be used with entity-specific list endpoints
        using ids= filter for fetching full entity data.

        Supports sorting by:
        - name: Sort by entity name (default)
        - created: Sort by when entity was added to folder
        - id: Sort by entity ID

        Examples:
        1. First page: GET .../folder-items/prompt_lib/42/5?limit=20
        2. With sorting: GET ...?sort_by=name&sort_order=desc&limit=50
        3. Pagination: GET ...?limit=20&offset=40
        """,
        tags=["social"],
        mcp_tool=True,
        parameters=[
            {"name": "sort_by", "in": "query", "required": False, "schema": {"type": "string", "enum": ["name", "created", "id"], "default": "name"}, "description": "Sort field"},
            {"name": "sort_order", "in": "query", "required": False, "schema": {"type": "string", "enum": ["asc", "desc"], "default": "asc"}, "description": "Sort direction"},
            {"name": "limit", "in": "query", "required": False, "schema": {"type": "integer", "default": 50, "maximum": 100}, "description": "Maximum items to return"},
            {"name": "offset", "in": "query", "required": False, "schema": {"type": "integer", "default": 0}, "description": "Number of items to skip"},
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
    def get(self, project_id: int, folder_id: int, **kwargs):
        sort_by = request.args.get('sort_by', 'name')
        sort_order = request.args.get('sort_order', 'asc')
        limit = min(int(request.args.get('limit', 50)), 100)
        offset = int(request.args.get('offset', 0))

        result = self.module.get_folder_items(
            project_id=project_id,
            folder_id=folder_id,
            sort_by=sort_by,
            sort_order=sort_order,
            limit=limit,
            offset=offset
        )

        if not result.get('ok'):
            error = result.get('error', 'Failed to get folder items')
            if 'not found' in error.lower():
                return {"error": error}, 404
            return {"error": error}, 400

        return {
            'folder_id': result['folder_id'],
            'entity_type': result['entity_type'],
            'total': result['total'],
            'limit': result['limit'],
            'offset': result['offset'],
            'items': result['items']
        }, 200


class API(api_tools.APIBase):
    url_params = api_tools.with_modes([
        '<int:project_id>/<int:folder_id>',
    ])

    mode_handlers = {
        PROMPT_LIB_MODE: PromptLibAPI
    }
