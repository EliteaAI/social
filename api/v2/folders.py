import logging

from flask import request
from pydantic import ValidationError

from tools import api_tools, auth, config as c, register_openapi
from tools import serialize

from ...constants import PROMPT_LIB_MODE
from ...models.pd.folders import EntityFolderCreate, EntityFolderDetails

log = logging.getLogger(__name__)


class PromptLibAPI(api_tools.APIModeHandler):
    """Handles collection-level operations: list folders, create folder."""

    @register_openapi(
        name="List Entity Folders",
        description="List folders for organizing entities (applications, skills, toolkits, configurations)",
        mcp_description="""
        USE to get folder structure for any entity type.

        Mode selection guide:
        - Agent folders: GET .../folders/prompt_lib/42?entity_type=application&sub_type=openai
        - Pipeline folders: GET .../folders/prompt_lib/42?entity_type=application&sub_type=pipeline
        - Skill folders: GET .../folders/prompt_lib/42?entity_type=skill
        - Toolkit folders: GET .../folders/prompt_lib/42?entity_type=toolkit
        - MCP folders: GET .../folders/prompt_lib/42?entity_type=toolkit&sub_type=mcp
        - Config folders: GET .../folders/prompt_lib/42?entity_type=configuration

        Examples:
        1. List agent folders: GET .../folders/prompt_lib/42?entity_type=application&sub_type=openai
        2. Search folders: GET ...?entity_type=skill&query=review
        """,
        tags=["social"],
        mcp_tool=True,
        parameters=[
            {"name": "entity_type", "in": "query", "required": True, "schema": {"type": "string", "enum": ["application", "skill", "toolkit", "configuration"]}, "description": "Entity type to list folders for."},
            {"name": "sub_type", "in": "query", "required": False, "schema": {"type": "string"}, "description": "Sub-type filter ('openai', 'pipeline' for applications; 'mcp' for toolkits)."},
            {"name": "query", "in": "query", "required": False, "schema": {"type": "string"}, "description": "Search query for folder names."},
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
    def get(self, project_id: int, **kwargs):  # pylint: disable=unused-argument
        entity_type = request.args.get('entity_type')
        if not entity_type:
            return {"error": "entity_type is required"}, 400

        if entity_type not in ['application', 'skill', 'toolkit', 'configuration']:
            return {"error": "entity_type must be one of: application, skill, toolkit, configuration"}, 400

        sub_type = request.args.get('sub_type')
        query = request.args.get('query')

        folders = self.module.get_folders(
            project_id=project_id,
            entity_type=entity_type,
            sub_type=sub_type,
            query=query
        )

        return {
            'total': len(folders),
            'folders': folders,
        }, 200

    @register_openapi(
        name="Create Entity Folder",
        description="Create a new folder to organize entities",
        mcp_description="""
        USE to create a new folder for organizing entities.

        DO NOT USE to move an entity into a folder → entity-specific move endpoints handle that.
        DO NOT USE to rename an existing folder → use update endpoint.

        Examples:
        1. Create agent folder: { 'name': 'Code Review Agents', 'entity_type': 'application', 'sub_type': 'openai' }
        2. Create pipeline folder: { 'name': 'CI Pipelines', 'entity_type': 'application', 'sub_type': 'pipeline' }
        3. Create skill folder: { 'name': 'Documentation Skills', 'entity_type': 'skill' }
        4. Create toolkit folder: { 'name': 'VCS Toolkits', 'entity_type': 'toolkit' }
        """,
        tags=["social"],
        mcp_tool=True,
        request_body=EntityFolderCreate,
        available_to_users=True,
    )
    @auth.decorators.check_api({
        "permissions": ["social.folders.create"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
            c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
        },
    })
    @api_tools.endpoint_metrics
    def post(self, project_id: int, **kwargs):  # pylint: disable=unused-argument
        raw = dict(request.json)
        entity_type = raw.get('entity_type')

        if not entity_type:
            return {"error": "entity_type is required"}, 400

        if entity_type not in ['application', 'skill', 'toolkit', 'configuration']:
            return {"error": "entity_type must be one of: application, skill, toolkit, configuration"}, 400

        result = self.module.create_folder(
            project_id=project_id,
            entity_type=entity_type,
            name=raw.get('name'),
            sub_type=raw.get('sub_type'),
            meta=raw.get('meta')
        )

        if not result.get('ok'):
            return {"error": result.get('error', 'Failed to create folder')}, 400

        log.info(f"Created folder {result['folder']['id']} for entity_type={entity_type}")
        return result['folder'], 201


class API(api_tools.APIBase):
    """Collection endpoints: list, create (no folder_id in URL)."""
    url_params = api_tools.with_modes([
        '<int:project_id>',
    ])

    mode_handlers = {
        PROMPT_LIB_MODE: PromptLibAPI
    }
