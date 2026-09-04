import uuid
from datetime import datetime

from sqlalchemy import Integer, String, DateTime, func, Index
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from tools import db_tools, db, config as c


class EntityFolder(db_tools.AbstractBaseMixin, db.Base):
    """Generic folder for organizing entities (agents, pipelines, skills, toolkits, mcp, configurations)."""
    __tablename__ = 'entity_folders'
    __table_args__ = (
        Index('ix_entity_folders_type_name', 'entity_type', 'name'),
        {'schema': c.POSTGRES_TENANT_SCHEMA},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    uuid: Mapped[str] = mapped_column(UUID(as_uuid=True), unique=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    owner_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)  # 'agent', 'pipeline', 'skill', 'toolkit', 'mcp', 'configuration'
    meta: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)  # is_pinned, position, etc.
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=True, onupdate=func.now())
