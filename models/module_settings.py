from typing import Optional

from tools import db, config as c

from sqlalchemy import Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column


# Per-project module-toggle settings for a user (#6285). Lives in the tenant schema so the same
# user can have different default_*_enabled / default_agent_*_enabled toggles per project.
class UserProjectModuleSettings(db.Base):
    __tablename__ = 'social_user_module_settings'
    __table_args__ = (
        UniqueConstraint('user_id', name='uq_social_user_module_settings_user_id'),
        {"schema": c.POSTGRES_TENANT_SCHEMA},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    module_settings: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
