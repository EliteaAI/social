from datetime import datetime

from tools import db_tools, db, config as c
from sqlalchemy import Integer, String, DateTime, Boolean, Text, func
from sqlalchemy.orm import Mapped, mapped_column


class Banner(db_tools.AbstractBaseMixin, db.Base):
    __tablename__ = 'social_banners'
    __table_args__ = (
        {"schema": c.POSTGRES_SCHEMA},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False, server_default='')
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default='false')
    dismissible: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default='true')
    # When false the "closed" state is kept in memory only, so the banner reappears on every page load
    persist_dismissal: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default='true')
    placement: Mapped[str] = mapped_column(String, nullable=False, server_default='top')
    style: Mapped[str] = mapped_column(String, nullable=False, server_default='info')
    icon: Mapped[str] = mapped_column(String, nullable=False, server_default='info')
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default='0')
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    # Version of what users see: bumped only when displayed content changes (not on reorder / enable),
    # so a changed banner is shown again to users who closed the previous version
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
