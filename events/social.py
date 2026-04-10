from pydantic.v1 import ValidationError

from tools import auth, db
from pylon.core.tools import web, log

from ..models.users import User
from ..models.pd.users import UserModel


class Event:

    @web.event("auth_visitor")
    def add_social_user_data(self, context, event, payload):
        if payload.get('type', '') == 'token':
            return

        user_id = payload.get('id', '')
        if not isinstance(user_id, int):
            return

        try:
            auth_ctx = auth.get_referenced_auth_context(payload['reference'])
            avatar = auth_ctx['provider_attr']['attributes']['picture']
        except (AttributeError, KeyError):
            avatar = None

        # TODO: need to receive user title

        try:
            user_data = UserModel(user_id=user_id, avatar=avatar)
        except ValidationError as e:
            log.exception(e)
            return
        with db.get_session() as session:
            user = session.query(User).filter_by(user_id=user_id).first()
            if user:
                user.avatar = avatar
            else:
                user = User(**user_data.dict())
                session.add(user)
            session.commit()

            return user.to_json()
