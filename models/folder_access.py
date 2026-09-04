from datetime import datetime

from sqlalchemy import Integer, String, DateTime, ForeignKey, func, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column

from tools import db_tools, db, config as c


class FolderAccessOverride(db_tools.AbstractBaseMixin, db.Base):
    """Per-user restrictive exception on a folder.

    Absence of a row means "RBAC default applies". Only restrictions are stored,
    so effective access is always intersection(base RBAC, this row).
    """
    __tablename__ = 'folder_access_overrides'
    __table_args__ = (
        UniqueConstraint('folder_id', 'user_id', name='_folder_access_user_uc'),
        Index('ix_folder_access_user_level', 'user_id', 'access_level'),
        Index('ix_folder_access_folder', 'folder_id'),
        {'schema': c.POSTGRES_TENANT_SCHEMA},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    folder_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(f'{c.POSTGRES_TENANT_SCHEMA}.entity_folders.id', ondelete='CASCADE'),
        nullable=False,
    )
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    access_level: Mapped[str] = mapped_column(String(16), nullable=False)
    project_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    created_by: Mapped[int] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=True, onupdate=func.now())
