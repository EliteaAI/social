try:
    from enum import StrEnum
except ImportError:
    from enum import Enum

    class StrEnum(str, Enum):
        pass


class FolderAccessLevel(StrEnum):
    """Restrictive overlay levels persisted as folder exceptions.

    `read_write` is never stored: it is the RBAC default, so selecting it removes the row.
    """
    read_only = 'read_only'
    no_access = 'no_access'


# Effective access returned by the resolver (includes the un-persisted default)
class EffectiveFolderAccess(StrEnum):
    full = 'full'
    read_only = 'read_only'
    no_access = 'no_access'


PERSISTED_ACCESS_LEVELS = frozenset({
    FolderAccessLevel.read_only,
    FolderAccessLevel.no_access,
})
