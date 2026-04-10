from datetime import datetime
from tools import db_tools, db
from sqlalchemy import Integer, String, DateTime, func, UniqueConstraint, Text
from sqlalchemy.orm import Mapped, mapped_column


class Feedback(db_tools.AbstractBaseMixin, db.Base):
    __tablename__ = 'social_feedbacks'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    referrer: Mapped[str] = mapped_column(String, nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    user_agent: Mapped[str] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
