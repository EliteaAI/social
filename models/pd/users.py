from typing import Optional
from pydantic.v1 import BaseModel

from pylon.core.tools import log


class PersonalizationModel(BaseModel):
    persona: Optional[str] = None
    default_instructions: Optional[str] = None

    class Config:
        orm_mode = True


class ContextManagementModel(BaseModel):
    enabled: Optional[bool] = None
    max_context_tokens: Optional[int] = None
    preserve_recent_messages: Optional[int] = None

    class Config:
        orm_mode = True


class SummarizationModel(BaseModel):
    enable_summarization: Optional[bool] = None
    summary_instructions: Optional[str] = None
    summary_model_name: Optional[str] = None
    summary_model_project_id: Optional[int] = None
    summary_trigger_ratio: Optional[float] = None
    min_messages_for_summary: Optional[int] = None
    target_summary_tokens: Optional[int] = None

    class Config:
        orm_mode = True


class UserModel(BaseModel):
    user_id: int
    avatar: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    personalization: Optional[PersonalizationModel] = None
    default_context_management: Optional[ContextManagementModel] = None
    default_summarization: Optional[SummarizationModel] = None

    class Config:
        orm_mode = True


class UserUpdateModel(BaseModel):
    description: Optional[str] = None
    personalization: Optional[PersonalizationModel] = None
    default_context_management: Optional[ContextManagementModel] = None
    default_summarization: Optional[SummarizationModel] = None

    class Config:
        orm_mode = True

