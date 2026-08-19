from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Optional, Dict, List
from datetime import datetime
from uuid import UUID

from ..enums.entity import EntityType, FOLDER_ENTITY_TYPES


class EntityFolderBase(BaseModel):
    name: str = Field(..., max_length=128)
    entity_type: str = Field(..., description="Entity type: agent, pipeline, skill, toolkit, mcp, configuration")
    meta: Optional[Dict] = Field(default_factory=dict)

    @field_validator('entity_type')
    @classmethod
    def validate_entity_type(cls, v):
        try:
            if EntityType(v) not in FOLDER_ENTITY_TYPES:
                raise ValueError(f"Entity type '{v}' does not support folders")
        except ValueError:
            valid = ', '.join(e.value for e in FOLDER_ENTITY_TYPES)
            raise ValueError(f"Invalid entity_type. Must be one of: {valid}")
        return v


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


# FolderItem models

class FolderItemBase(BaseModel):
    entity_type: str = Field(..., description="Entity type: agent, pipeline, skill, toolkit, mcp, configuration")
    entity_id: int = Field(..., description="ID of the entity")

    @field_validator('entity_type')
    @classmethod
    def validate_entity_type(cls, v):
        try:
            if EntityType(v) not in FOLDER_ENTITY_TYPES:
                raise ValueError(f"Entity type '{v}' does not support folders")
        except ValueError:
            valid = ', '.join(e.value for e in FOLDER_ENTITY_TYPES)
            raise ValueError(f"Invalid entity_type. Must be one of: {valid}")
        return v


class FolderItemCreate(FolderItemBase):
    """Request model for adding an entity to a folder."""
    folder_id: int = Field(..., description="Target folder ID")
    sort_name: Optional[str] = Field(None, description="Name for sorting (auto-populated if not provided)")


class FolderItemDetails(FolderItemBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    folder_id: int
    project_id: int
    owner_id: int
    sort_name: str
    created_at: datetime


class MoveToFolderRequest(BaseModel):
    """Request to move an entity to a folder or remove from folder."""
    entity_type: str = Field(..., description="Entity type: agent, pipeline, skill, toolkit, mcp, configuration")
    entity_id: int = Field(..., description="Entity ID to move")
    folder_id: Optional[int] = Field(None, description="Target folder ID. Set to null to remove from folder.")

    @field_validator('entity_type')
    @classmethod
    def validate_entity_type(cls, v):
        try:
            if EntityType(v) not in FOLDER_ENTITY_TYPES:
                raise ValueError(f"Entity type '{v}' does not support folders")
        except ValueError:
            valid = ', '.join(e.value for e in FOLDER_ENTITY_TYPES)
            raise ValueError(f"Invalid entity_type. Must be one of: {valid}")
        return v
