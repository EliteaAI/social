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

