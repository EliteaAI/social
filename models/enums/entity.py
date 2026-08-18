try:
    from enum import StrEnum
except ImportError:
    from enum import Enum
    class StrEnum(str, Enum):
        pass


class EntityType(StrEnum):
    prompt = 'prompt'
    collection = 'collection'
    datasource = 'datasource'
    application = 'application'
    toolkit = 'toolkit'
    configuration = 'configuration'
    conversation = 'conversation'
    skill = 'skill'
    # Folder-specific entity types (more granular than application/toolkit)
    agent = 'agent'
    pipeline = 'pipeline'
    mcp = 'mcp'


# Entity types that support folder organization
FOLDER_ENTITY_TYPES = frozenset({
    EntityType.agent,
    EntityType.pipeline,
    EntityType.skill,
    EntityType.toolkit,
    EntityType.mcp,
    EntityType.configuration,
})

