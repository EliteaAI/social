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

    def to_json(self, exclude_fields: tuple = ()) -> dict:
        result = {
            "id": self.id,
            "user_id": self.user_id,
            "referrer": self.referrer,
            "description": self.description,
            "rating": self.rating,
            "user_agent": self.user_agent,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        return {k: v for k, v in result.items() if k not in exclude_fields}
