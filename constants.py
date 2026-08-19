from .models.enums.entity import EntityType, FOLDER_ENTITY_TYPES


PROMPT_LIB_MODE = 'prompt_lib'


# Mapping of folder entity types to their database table names (for validation/lookup)
ENTITY_TABLE_MAP = {
    EntityType.agent: "applications",
    EntityType.pipeline: "applications",
    EntityType.skill: "skills",
    EntityType.toolkit: "elitea_tools",
    EntityType.mcp: "elitea_tools",
    EntityType.configuration: "configuration",
}


def is_valid_folder_entity(entity_type: str) -> bool:
    """Check if entity_type is valid for folder organization."""
    try:
        return EntityType(entity_type) in FOLDER_ENTITY_TYPES
    except ValueError:
        return False
