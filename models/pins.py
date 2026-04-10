from datetime import datetime

from tools import db_tools, db

from .enums.entity import EntityType
from sqlalchemy import Integer, String, DateTime, func, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column


class Pin(db_tools.AbstractBaseMixin, db.Base):
    __tablename__ = 'social_pins'
    __table_args__ = (
        UniqueConstraint('entity', 'project_id', 'entity_id',
                         name='_pin_entity_id_uc'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity: Mapped[EntityType] = mapped_column(String, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)  # Last user who pinned
    project_id: Mapped[int] = mapped_column(Integer, nullable=True, index=True)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

