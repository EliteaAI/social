from datetime import datetime

from tools import db_tools, db

from .enums.entity import EntityType
from sqlalchemy import Integer, String, DateTime, func, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column


class Like(db_tools.AbstractBaseMixin, db.Base):
    __tablename__ = 'social_likes'
    __table_args__ = (
        UniqueConstraint('entity', 'user_id', 'project_id', 'entity_id',
                         name='_entity_id_uc'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity: Mapped[EntityType] = mapped_column(String, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    project_id: Mapped[int] = mapped_column(Integer, nullable=True, index=True)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    def to_json(self, exclude_fields: tuple = ()) -> dict:
        result = {
            "id": self.id,
            "entity": self.entity,
            "user_id": self.user_id,
            "project_id": self.project_id,
            "entity_id": self.entity_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        return {k: v for k, v in result.items() if k not in exclude_fields}
