from typing import Optional
from pydantic.v1 import BaseModel, conint


class FeedbackModel(BaseModel):
    rating: conint(ge=0, le=5)
    user_id: int
    referrer: Optional[str]
    description: str
    user_agent: Optional[str]

    class Config:
        schema_extra = {
            "examples": [
                {
                    "rating": 4,
                    "description": "Great platform, very intuitive and powerful."
                }
            ]
        }


class FeedbackUpdateModel(BaseModel):
    rating: Optional[conint(ge=0, le=5)]
    user_id: Optional[int]
    referrer: Optional[str]
    description: Optional[str]

    class Config:
        schema_extra = {
            "examples": [
                {
                    "rating": 5,
                    "description": "Updated: outstanding platform after the latest improvements."
                }
            ]
        }

