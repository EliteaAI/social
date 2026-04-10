from pydantic.v1 import ValidationError, parse_obj_as
from sqlalchemy import func
from traceback import format_exc
from typing import Optional, List

from tools import rpc_tools, db, auth
from pylon.core.tools import web, log

from ..models.likes import Like
from ..models.pd.likes import LikeModel


class RPC:
    @web.rpc(f'social_like', "like")
    def like(
            self, project_id: int | None, entity: str, entity_id: int, user_id: int = None
    ) -> dict:
        if not user_id:
            user_id = auth.current_user().get("id")
        try:
            like_data = LikeModel(
                entity=entity,
                entity_id=entity_id,
                user_id=user_id,
                project_id=project_id
            )
        except ValidationError as e:
            return {'ok': False, 'error': str(e)}
        with db.with_project_schema_session(None) as session:
            like = Like(**like_data.dict())
            session.add(like)
            session.commit()
            return {'ok': True, 'like_id': like.id}

    @web.rpc("social_dislike", "dislike")
    def dislike(
            self, project_id: int | None, entity: str, entity_id: int, user_id: int = None
    ) -> dict:
        if not user_id:
            user_id = auth.current_user().get("id")
        with db.with_project_schema_session(None) as session:
            like = session.query(Like).where(
                Like.project_id == project_id,
                Like.user_id == user_id,
                Like.entity == entity,
                Like.entity_id == entity_id
            ).first()
            if like:
                session.delete(like)
                session.commit()
                return {'ok': True}
        return {'ok': False}

    @web.rpc("social_is_liked", "is_liked")
    def is_liked(
            self, project_id: int | None, entity: str, entity_id: int, user_id: int = None
    ) -> bool:
        if not user_id:
            user_id = auth.current_user().get("id")
        with db.with_project_schema_session(None) as session:
            like = session.query(Like).where(
                Like.project_id == project_id,
                Like.user_id == user_id,
                Like.entity == entity,
                Like.entity_id == entity_id
            ).first()
        return like is not None

    @web.rpc("social_get_likes", "get_likes")
    def get_likes(
            self, project_id: int | None, entity: str, entity_id: int
    ) -> dict:
        with db.with_project_schema_session(None) as session:
            likes = session.query(Like).where(
                Like.project_id == project_id,
                Like.entity == entity,
                Like.entity_id == entity_id
            ).all()
            return {'total': len(likes), 'rows': [like.to_json() for like in likes]}

    @web.rpc("social_get_top_likes", "get_top_likes")
    def get_top_likes(
            self, project_id: int | None, entity: str, top_n: int = 10
    ) -> list[dict]:
        with db.with_project_schema_session(None) as session:
            likes = (
                session.query(
                    Like.project_id, Like.entity_id, func.count(Like.id).label('likes')
                ).where(Like.project_id == project_id, Like.entity == entity)
                .group_by(Like.project_id, Like.entity_id)
                .order_by(func.count(Like.id).desc())
                .limit(top_n)
            ).all()

            return [like.to_json() for like in likes]

    @web.rpc("social_get_like_model", "get_like_model")
    def get_like_model(self):
        return Like
