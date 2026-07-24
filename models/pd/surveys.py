from typing import Optional, List, Any
from pydantic.v1 import BaseModel, validator


QUESTION_TYPES = ("open", "radio", "checkbox", "slider")


class SurveyQuestionModel(BaseModel):
    id: Optional[int]
    title: str
    question_type: str = "open"
    options: Optional[dict]
    position: Optional[int] = 0

    @validator("question_type")
    def validate_question_type(cls, v):
        if v not in QUESTION_TYPES:
            raise ValueError(f"question_type must be one of {list(QUESTION_TYPES)}, got '{v}'")
        return v

    class Config:
        schema_extra = {
            "examples": [
                {
                    "title": "How likely are you to recommend Elitea to a friend or colleague?",
                    "question_type": "slider",
                    "options": {"min": 0, "max": 10, "min_label": "Not likely", "max_label": "Very likely"},
                    "position": 0,
                }
            ]
        }


class SurveyModel(BaseModel):
    name: str
    description: Optional[str]
    enabled: bool = False
    dismissible: bool = False
    questions: Optional[List[SurveyQuestionModel]] = []

    class Config:
        schema_extra = {
            "examples": [
                {
                    "name": "NPS Elitea",
                    "description": "Net Promoter Score survey (internal note).",
                    "enabled": True,
                    "dismissible": True,
                    "questions": [
                        {
                            "title": "How likely are you to recommend Elitea to a friend or colleague?",
                            "question_type": "slider",
                            "options": {"min": 0, "max": 10, "min_label": "Not likely", "max_label": "Very likely"},
                            "position": 0,
                        }
                    ],
                }
            ]
        }


class SurveyUpdateModel(BaseModel):
    name: Optional[str]
    description: Optional[str]
    enabled: Optional[bool]
    dismissible: Optional[bool]
    questions: Optional[List[SurveyQuestionModel]]


class SurveyAnswerItem(BaseModel):
    question_id: int
    answer: Any


class SurveyResponseSubmitModel(BaseModel):
    answers: List[SurveyAnswerItem]

    class Config:
        schema_extra = {
            "examples": [
                {"answers": [{"question_id": 1, "answer": 9}]}
            ]
        }


class SurveyReportQueryModel(BaseModel):
    date_from: Optional[str]
    date_to: Optional[str]
    limit: Optional[int] = 100
    offset: Optional[int] = 0
