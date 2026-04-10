from typing import List
from pylon.core.tools import web, log
from tools import auth, db

from ..models.pd.users import UserModel
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
