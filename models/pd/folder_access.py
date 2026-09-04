from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, ConfigDict, field_validator

from ..enums.folder_access import FolderAccessLevel


MAX_BULK_ACCESS_ENTRIES = 200


def _validate_level(value: str) -> str:
    try:
        return FolderAccessLevel(value).value
    except ValueError:
        valid = ', '.join(l.value for l in FolderAccessLevel)
        raise ValueError(
            f"Invalid access_level '{value}'. Must be one of: {valid}. "
            "Read/write is the default and is expressed by removing the exception."
        )


class FolderAccessEntry(BaseModel):
    """One user's exception on a folder."""
    user_id: int = Field(..., gt=0)
    access_level: str = Field(..., description="read_only | no_access")

    @field_validator('access_level')
    @classmethod
    def validate_access_level(cls, v):
        return _validate_level(v)


class FolderAccessBulkUpsert(BaseModel):
    """PUT payload: replace/insert the listed users' exceptions atomically."""
    entries: List[FolderAccessEntry] = Field(..., min_length=1, max_length=MAX_BULK_ACCESS_ENTRIES)


class FolderAccessBulkRemove(BaseModel):
    """DELETE payload: drop exceptions (back to RBAC default) for the listed users."""
    user_ids: List[int] = Field(..., min_length=1, max_length=MAX_BULK_ACCESS_ENTRIES)


class FolderAccessOverrideDetails(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    folder_id: int
    user_id: int
    access_level: str
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
