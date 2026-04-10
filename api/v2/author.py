from queue import Empty

from flask import request, g, jsonify
from pylon.core.tools import log
from tools import api_tools, auth, constants as c

from ...models.users import User
from ...models.pd.users import UserUpdateModel


class ProjectApi(api_tools.APIModeHandler):
    @api_tools.endpoint_metrics
    def get(self, **kwargs):
        user = self.module.context.rpc_manager.timeout(2).auth_main_current_user(g.auth)
        try:
            personal_project_id = self.module.context.rpc_manager.timeout(2).projects_get_personal_project_id(
                user['id'])
            user['personal_project_id'] = personal_project_id
        except Empty:
            ...

        social_user: User = User.query.filter(User.user_id == user['id']).first()
        if social_user:
            user['description'] = social_user.description
            user['avatar'] = social_user.avatar
            user['title'] = social_user.title
            user['personalization'] = social_user.personalization
            user['default_context_management'] = social_user.default_context_management
            user['default_summarization'] = social_user.default_summarization
        else:
            try:
                auth_ctx = auth.get_referenced_auth_context(g.auth.reference)
                avatar = auth_ctx['provider_attr']['attributes']['picture']
            except (AttributeError, KeyError):
                avatar = None
            user['avatar'] = avatar

        user['api_url'] = c.APP_HOST

        return jsonify(user)


class API(api_tools.APIBase):
    url_params = api_tools.with_modes([
        "",
        # "<int:user_id>",
    ])

    mode_handlers = {
        'default': ProjectApi,
    }

    @api_tools.endpoint_metrics
    def put(self, **kwargs):
        u = self.module.context.rpc_manager.timeout(2).auth_main_current_user(g.auth)
        user_id = u['id']
        user = User.query.filter(User.user_id == user_id).first()

        if not user:
            return {'error': 'User not found'}, 400

        # Validate request data
        try:
            update_data = UserUpdateModel(**request.json)
        except Exception as e:
            return {'error': f'Validation error: {str(e)}'}, 400

        # Update fields if provided
        data = request.json
        if 'description' in data:
            user.description = data['description']
        if 'personalization' in data:
            user.personalization = data['personalization']
        if 'default_context_management' in data:
            user.default_context_management = data['default_context_management']
        if 'default_summarization' in data:
            user.default_summarization = data['default_summarization']

        user.insert()

        return {
            'id': user.id,
            'user_id': user.user_id,
            'avatar': user.avatar,
            'title': user.title,
            'description': user.description,
            'personalization': user.personalization,
            'default_context_management': user.default_context_management,
            'default_summarization': user.default_summarization,
        }, 200
