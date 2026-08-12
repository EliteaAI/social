from typing import Dict, Optional
from pydantic.v1 import BaseModel

from pylon.core.tools import log


class PersonalizationModel(BaseModel):
    persona: Optional[str] = None
    # DEPRECATED server-owned mirror of personality_instructions[persona]; kept for back-compat
    # with consumers still reading the flat field. Removed once all readers use the dict.
    default_instructions: Optional[str] = None
    # Per-persona instructions keyed by persona value (generic/qa/nerdy/...). Left as None (not {})
    # so the API can detect "client did not send this key" via .dict(exclude_unset=True).
    personality_instructions: Optional[Dict[str, str]] = None
    default_internal_mcp_enabled: Optional[bool] = None
    midturn_injection_enabled: Optional[bool] = None
    default_ask_user_enabled: Optional[bool] = None

    class Config:
        orm_mode = True


class ContextManagementModel(BaseModel):
    enabled: Optional[bool] = None
    max_context_tokens: Optional[int] = None
    preserve_recent_messages: Optional[int] = None
    enable_context_editing: Optional[bool] = None

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
        schema_extra = {
            "examples": [
                {
                    "description": "Senior software engineer focused on backend systems",
                    "personalization": {
                        "persona": "Expert developer",
                        "default_instructions": "Always use Python 3.12+ syntax."
                    },
                    "default_context_management": {
                        "enabled": True,
                        "max_context_tokens": 8000,
                        "preserve_recent_messages": 5
                    },
                    "default_summarization": {
                        "enable_summarization": True,
                        "summary_model_name": "gpt-5-mini",
                        "summary_model_project_id": 1,
                        "summary_trigger_ratio": 0.8,
                        "min_messages_for_summary": 10,
                        "target_summary_tokens": 1000
                    }
                }
            ]
        }

