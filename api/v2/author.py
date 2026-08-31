from queue import Empty

from flask import request, g, jsonify
from pylon.core.tools import log
from tools import api_tools, auth, constants as c, register_openapi

from ...constants import MODULE_TOGGLE_FIELDS
from ...models.users import User
from ...models.pd.users import UserUpdateModel


def _hydrate_personalization(personalization):
    """Ensure the returned personalization always exposes a personality_instructions dict (#5392).

    Self-heals legacy/unmigrated rows: if the dict is absent but a flat default_instructions
    exists, seed it under the row's current persona so the UI (and any dict-aware reader) sees
    the user's existing instructions without depending on the manual DB migration having run.
    """
    if not personalization:
        return personalization
    result = dict(personalization)
    persona = result.get('persona') or 'generic'
    instructions_map = result.get('personality_instructions')
    if not isinstance(instructions_map, dict):
        instructions_map = {}
        if result.get('default_instructions'):
            instructions_map[persona] = result['default_instructions']
    result['personality_instructions'] = instructions_map
    # Module toggles are served exclusively via /social/module_settings/<project_id> now (#6285);
    # strip any stale values so this endpoint can't surface or accept them anymore.
    for field in MODULE_TOGGLE_FIELDS:
        result.pop(field, None)
    return result


class ProjectApi(api_tools.APIModeHandler):
    @register_openapi(
        name="Get Current Author",
        description="Get current authenticated user profile, including social data (avatar, description, personalization).",
        available_to_users=True,
    )
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
            # In terms of https://github.com/EliteaAI/elitea_issues/issues/5394, description is set to None
            user['description'] = None
            user['avatar'] = social_user.avatar
            user['title'] = social_user.title
            user['personalization'] = _hydrate_personalization(social_user.personalization)
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

    @register_openapi(
        name="Update Current Author",
        description="Update current authenticated user profile fields (description, personalization, context management, summarization).",
        request_body=UserUpdateModel,
        available_to_users=True,
    )
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
            # Strip module-toggle keys (#6285): this endpoint no longer accepts them, even from
            # a stale client build; they must go through /social/module_settings/<project_id>.
            incoming_personalization = {
                k: v for k, v in (data['personalization'] or {}).items()
                if k not in MODULE_TOGGLE_FIELDS
            }
            user.personalization = self._merge_personalization(
                user.personalization, incoming_personalization,
            )
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
            'personalization': _hydrate_personalization(user.personalization),
            'default_context_management': user.default_context_management,
            'default_summarization': user.default_summarization,
        }, 200

    @staticmethod
    def _merge_personalization(existing, incoming):
        """Merge an incoming personalization payload over the stored one (#5392).

        personality_instructions is merged key-by-key so a partial or stale client payload can
        never wipe personas it didn't send. The flat default_instructions field is server-owned:
        it is always recomputed as personality_instructions[persona], ignoring the client value.

        A legacy client (pre-#5392 bundle) that omits personality_instructions but sends a flat
        default_instructions edit is treated as an edit to the CURRENTLY SELECTED persona's slot,
        so its edit is preserved rather than dropped during the rollout window.
        """
        existing = dict(existing or {})
        merged = dict(incoming)

        persona = merged.get('persona') or existing.get('persona') or 'generic'
        existing_map = existing.get('personality_instructions')
        existing_map = dict(existing_map) if isinstance(existing_map, dict) else {}

        # 'personality_instructions' absent from the raw payload => legacy client shape.
        if 'personality_instructions' in incoming and isinstance(incoming.get('personality_instructions'), dict):
            merged_map = {**existing_map, **incoming['personality_instructions']}
        else:
            merged_map = existing_map
            if 'default_instructions' in incoming:
                merged_map[persona] = incoming.get('default_instructions') or ''

        merged['personality_instructions'] = merged_map
        merged['default_instructions'] = merged_map.get(persona, '')
        return merged
