from datetime import datetime

from sqlalchemy import Integer, String, DateTime, func, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column

from tools import db_tools, db

from .enums.entity import EntityType


class FolderItem(db_tools.AbstractBaseMixin, db.Base):
    """Join table for folder membership.

    Links entities to folders without requiring folder_id columns on entity tables.
    Supports efficient sorting and pagination via denormalized sort_name.
    """
    __tablename__ = 'social_folder_items'
    __table_args__ = (
        UniqueConstraint('folder_id', 'entity', 'entity_id',
                         name='_folder_item_entity_uc'),
        Index('ix_folder_items_folder_sort', 'folder_id', 'sort_name'),
        Index('ix_folder_items_folder_entity', 'folder_id', 'entity', 'entity_id'),
        Index('ix_folder_items_owner', 'owner_id', 'entity'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    folder_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    entity: Mapped[EntityType] = mapped_column(String(32), nullable=False, index=True)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    project_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    owner_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    sort_name: Mapped[str] = mapped_column(String(256), nullable=False, default='')  # lowercased name for sorting
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
