from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, List
from datetime import datetime
from uuid import UUID


class EntityFolderBase(BaseModel):
    name: str = Field(..., max_length=128)
    entity_type: str = Field(..., description="'agent', 'pipeline', 'skill', 'toolkit', 'mcp', 'configuration'")
    meta: Optional[Dict] = Field(default_factory=dict)


class EntityFolderCreate(EntityFolderBase):
    """Request model for creating a folder. owner_id is set automatically from authenticated user."""
    owner_id: Optional[int] = Field(None, json_schema_extra={"hidden": True})


class EntityFolderUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=128)
    meta: Optional[Dict] = Field(default_factory=dict)


class EntityFolderDetails(EntityFolderBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    uuid: UUID
    owner_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None


class EntityFolderList(EntityFolderDetails):
    """Folder with entity count for list views."""
    entities_count: Optional[int] = 0


class EntityFolderWithEntities(EntityFolderDetails):
    """Folder with nested entities for grouped views."""
    entities: List[dict] = Field(default_factory=list)
    total: int = 0


class MoveToFolderRequest(BaseModel):
    folder_id: Optional[int] = Field(None, description="Target folder ID. Set to null to remove from folder.")
