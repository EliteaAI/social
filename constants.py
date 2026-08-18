from enum import Enum


PROMPT_LIB_MODE = 'prompt_lib'


class EntityType(str, Enum):
    """Supported entity types for folder organization."""
    APPLICATION = "application"
    SKILL = "skill"
    TOOLKIT = "toolkit"
    CONFIGURATION = "configuration"

    @classmethod
    def values(cls) -> list[str]:
        """Return list of all valid entity type values."""
        return [e.value for e in cls]

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """Check if a value is a valid entity type."""
        return value in cls.values()


# Mapping of entity types to their database table names
ENTITY_TABLE_MAP = {
    EntityType.APPLICATION.value: "applications",
    EntityType.SKILL.value: "skills",
    EntityType.TOOLKIT.value: "elitea_tools",
    EntityType.CONFIGURATION.value: "configuration",
}
