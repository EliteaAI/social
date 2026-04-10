from flask import jsonify, request
from queue import Empty
from pylon.core.tools import log
from tools import api_tools, auth, config as c


class ProjectApi(api_tools.APIModeHandler):
    @auth.decorators.check_api({
        "permissions": ["models.social.authors.get"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": True},
            c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": True},
        }})
    def get(self, project_id: int, **kwargs):
        # Optional query params for optimization
        limit = request.args.get('limit', type=int)
        sort_by = request.args.get('sort_by', type=str)  # 'application', 'toolkit', 'collection'

        # If sort_by is specified, get top contributors by entity count
        if sort_by and limit:
            try:
                user_ids = self.module.context.rpc_manager.timeout(5).elitea_core_get_top_contributors(
                    project_id=project_id,
                    entity_type=sort_by,
                    limit=limit
                )
            except Empty:
                log.warning(f"elitea_core_get_top_contributors RPC not available, falling back to all users")
                user_ids = self._get_all_user_ids(project_id, limit)
        else:
            user_ids = self._get_all_user_ids(project_id, limit)

        return jsonify(self.module.get_authors(user_ids))

    def _get_all_user_ids(self, project_id: int, limit: int = None):
        """Get all user IDs in project, optionally limited."""
        user_ids = self.module.context.rpc_manager.timeout(5).admin_get_users_ids_in_project(
            project_id=project_id,
            filter_system_user=True
        )
        if limit and len(user_ids) > limit:
            user_ids = user_ids[:limit]
        return user_ids


class API(api_tools.APIBase):
    url_params = api_tools.with_modes([
        '<int:project_id>',
    ])

    mode_handlers = {c.DEFAULT_MODE: ProjectApi}
