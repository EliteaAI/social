from typing import Optional
from pydantic.v1 import BaseModel

from ...models.enums.entity import EntityType


class PinModel(BaseModel):
    entity: EntityType
    user_id: int
    project_id: Optional[int]
    entity_id: int

