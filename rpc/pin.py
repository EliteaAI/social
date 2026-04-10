from pydantic.v1 import ValidationError

from tools import db, auth
from pylon.core.tools import web

from ..models.pins import Pin
from ..models.pd.pins import PinModel


class RPC:
    @web.rpc(f'social_pin', "pin")
    def pin(
            self, project_id: int | None, entity: str, entity_id: int, user_id: int = None
    ) -> dict:
        if not user_id:
            user_id = auth.current_user().get("id")
        try:
            pin_data = PinModel(
                entity=entity,
                entity_id=entity_id,
                user_id=user_id,
                project_id=project_id
            )
        except ValidationError as e:
            return {'ok': False, 'error': str(e)}

        with db.with_project_schema_session(None) as session:
            # Check if pin already exists for this project/entity
            existing_pin = session.query(Pin).where(
                Pin.project_id == project_id,
                Pin.entity == entity,
                Pin.entity_id == entity_id
            ).first()

            if existing_pin:
                # Update existing pin with new user_id and timestamp
                existing_pin.user_id = user_id
                session.commit()
                return {'ok': True, 'pin_id': existing_pin.id, 'updated': True}
            else:
                # Create new pin
                pin = Pin(**pin_data.dict())
                session.add(pin)
                session.commit()
                return {'ok': True, 'pin_id': pin.id, 'updated': False}

    @web.rpc("social_unpin", "unpin")
    def unpin(
            self, project_id: int | None, entity: str, entity_id: int, user_id: int = None
    ) -> dict:
        # user_id is kept for consistency but not used in the query
        with db.with_project_schema_session(None) as session:
            pin = session.query(Pin).where(
                Pin.project_id == project_id,
                Pin.entity == entity,
                Pin.entity_id == entity_id
            ).first()
            if pin:
                session.delete(pin)
                session.commit()
                return {'ok': True}
        return {'ok': False}

    @web.rpc("social_is_pinned", "is_pinned")
    def is_pinned(
            self, project_id: int | None, entity: str, entity_id: int, user_id: int = None
    ) -> bool:
        # user_id is kept for consistency but not used in the query
        with db.with_project_schema_session(None) as session:
            pin = session.query(Pin).where(
                Pin.project_id == project_id,
                Pin.entity == entity,
                Pin.entity_id == entity_id
            ).first()
        return pin is not None

    @web.rpc("social_get_pin_model", "get_pin_model")
    def get_pin_model(self):
        return Pin

    @web.rpc("social_add_pins_with_priority", "add_pins_with_priority")
    def add_pins_with_priority(self):
        from ..utils.pin_utils import add_pins_with_priority
        return add_pins_with_priority

