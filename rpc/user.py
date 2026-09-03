from typing import List
from pylon.core.tools import web, log
from tools import auth, db

from ..constants import PROJECT_SCOPED_SETTINGS_FIELDS
from ..models.pd.users import UserModel
from ..models.module_settings import UserProjectModuleSettings
from ..models.users import User


class RPC:
    @web.rpc("social_get_user", "get_user")
    def get_user(self, user_id: int) -> dict:
        with db.get_session() as session:
            user = session.query(User).filter(User.user_id == user_id).first()
            if not user:
                return {}
            return UserModel.from_orm(user).dict()

    @web.rpc("social_get_users", "get_users")
    def get_users(self, user_ids: List[int]) -> List[dict]:
        with db.get_session() as session:
            users = session.query(User).where(User.user_id.in_(user_ids)).all()
            return [UserModel.from_orm(i).dict() for i in users]

    @web.rpc("social_get_authors", "get_authors")
    def get_authors(self, author_ids: List[int]) -> List[dict]:
        try:
            users_data: list = auth.list_users(user_ids=author_ids)
        except RuntimeError:
            return []
        try:
            social_data: list = self.get_users(author_ids)
        except KeyError:
            social_data = []

        avatar_map = {i['user_id']: i.get('avatar') for i in social_data}

        for user in users_data:
            avatar = avatar_map.pop(user['id'], None)
            user['avatar'] = avatar
        return users_data

    @web.rpc("social_get_project_module_settings", "get_project_module_settings")
    def get_project_module_settings(self, user_id: int, project_id: int) -> dict:
        # Per-project store first; falls back per-key to the legacy global personalization blob
        # (not just when the row is entirely absent) so a field added after a row already
        # existed - e.g. midturn_injection_enabled riding in on top of #6285's rows - still
        # inherits the user's prior global value instead of silently reading as False (#6303).
        with db.get_session(project_id) as session:
            row = session.query(UserProjectModuleSettings).filter(
                UserProjectModuleSettings.user_id == user_id
            ).first()
            stored = dict(row.module_settings) if row and row.module_settings is not None else {}

        missing_fields = [field for field in PROJECT_SCOPED_SETTINGS_FIELDS if field not in stored]
        legacy_personalization = {}
        if missing_fields:
            with db.get_session() as session:
                legacy_user = session.query(User).filter(User.user_id == user_id).first()
                legacy_personalization = (legacy_user.personalization or {}) if legacy_user else {}

        return {
            field: bool(stored[field]) if field in stored else bool(legacy_personalization.get(field, False))
            for field in PROJECT_SCOPED_SETTINGS_FIELDS
        }

    @web.rpc("social_set_project_module_settings", "set_project_module_settings")
    def set_project_module_settings(self, user_id: int, project_id: int, module_settings: dict) -> dict:
        # Merge onto whatever is already stored instead of replacing it wholesale, so a caller
        # that only sends a subset of fields (the API already allows this via
        # ModuleSettingsModel's all-Optional fields + exclude_none) doesn't reset every
        # unmentioned toggle back to False.
        incoming = {
            field: bool(module_settings[field])
            for field in PROJECT_SCOPED_SETTINGS_FIELDS
            if field in (module_settings or {})
        }
        with db.get_session(project_id) as session:
            row = session.query(UserProjectModuleSettings).filter(
                UserProjectModuleSettings.user_id == user_id
            ).first()
            if row:
                row.module_settings = {**(row.module_settings or {}), **incoming}
            else:
                row = UserProjectModuleSettings(user_id=user_id, module_settings=incoming)
                session.add(row)
            session.commit()
        return self.get_project_module_settings(user_id, project_id)
