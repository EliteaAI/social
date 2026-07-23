from datetime import datetime
from typing import Optional

from tools import db_tools, db, config as c
from sqlalchemy import (
    Integer, String, DateTime, Boolean, Text, ForeignKey, func,
    UniqueConstraint, Index,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column


class Survey(db_tools.AbstractBaseMixin, db.Base):
    __tablename__ = 'social_surveys'
    __table_args__ = (
        {"schema": c.POSTGRES_SCHEMA},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default='false')
    dismissible: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default='false')
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class SurveyQuestion(db_tools.AbstractBaseMixin, db.Base):
    __tablename__ = 'social_survey_questions'
    __table_args__ = (
        Index('ix_social_survey_questions_survey_id', 'survey_id'),
        {"schema": c.POSTGRES_SCHEMA},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    survey_id: Mapped[int] = mapped_column(
        ForeignKey(f'{c.POSTGRES_SCHEMA}.social_surveys.id', ondelete='CASCADE'), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    question_type: Mapped[str] = mapped_column(String, nullable=False)
    options: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, server_default='0')
    created_by: Mapped[int] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class SurveyAnswer(db_tools.AbstractBaseMixin, db.Base):
    __tablename__ = 'social_survey_answers'
    __table_args__ = (
        UniqueConstraint('question_id', 'user_id', name='_survey_answer_question_user_uc'),
        Index('ix_social_survey_answers_survey_id', 'survey_id'),
        Index('ix_social_survey_answers_user_id', 'user_id'),
        Index('ix_social_survey_answers_created_at', 'created_at'),
        {"schema": c.POSTGRES_SCHEMA},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question_id: Mapped[int] = mapped_column(
        ForeignKey(f'{c.POSTGRES_SCHEMA}.social_survey_questions.id', ondelete='CASCADE'), nullable=False)
    survey_id: Mapped[int] = mapped_column(Integer, nullable=False)
    survey_name: Mapped[str] = mapped_column(String, nullable=True)
    question_title: Mapped[str] = mapped_column(Text, nullable=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    user_email: Mapped[str] = mapped_column(String, nullable=True)
    answer: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    shown: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default='false')
    dismissed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default='false')
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
