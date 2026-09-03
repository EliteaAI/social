from queue import Empty
from typing import List, Optional, Union

import flask
from pydantic import ValidationError
from sqlalchemy import and_, exists

from tools import db, auth, serialize
from pylon.core.tools import web, log

from ..models.folders import EntityFolder
from ..models.folder_items import FolderItem
from ..models.folder_access import FolderAccessOverride
from ..models.enums.folder_access import (
    FolderAccessLevel,
    EffectiveFolderAccess,
)
from ..models.pd.folder_access import (
    FolderAccessBulkRemove,
    FolderAccessBulkUpsert,
    FolderAccessOverrideDetails,
)
from ..constants import (
    FOLDER_ACCESS_MEMO_ATTR,
    FOLDER_ACCESS_GRANTED_EVENT,
    FOLDER_ACCESS_REVOKED_EVENT,
)


def _current_user_id():
    """Caller's user id, or None when there is no user context.

    `auth.current_user()` reads `flask.g.auth` and raises outside a request, so
    background/runtime callers (indexer, celery, schedulers) must not blow up here:
    no user context means no per-user exception can apply.
    """
    try:
        return (auth.current_user() or {}).get('id')
    except Exception:  # pylint: disable=W0703
        return None


def _memo():
    """Per-request memo for restricted-folder lookups. Returns None outside a request."""
    try:
        if not flask.has_request_context():
            return None
    except Exception:  # pylint: disable=W0703
        return None
    memo = getattr(flask.g, FOLDER_ACCESS_MEMO_ATTR, None)
    if memo is None:
        memo = {}
        setattr(flask.g, FOLDER_ACCESS_MEMO_ATTR, memo)
    return memo


def _project_member_ids(module, project_id: int):
    """Set of member ids, or None when membership cannot be established (fail closed)."""
    try:
        members = module.context.rpc_manager.timeout(5).admin_get_users_ids_in_project(
            project_id=project_id
        )
    except Empty:
        log.error('admin_get_users_ids_in_project unavailable; refusing folder access write')
        return None
    except Exception:  # pylint: disable=W0703
        log.exception('Failed to list project members')
        return None
    return {int(i) for i in (members or [])}


def _audit(module, event: str, payload: dict) -> None:
    try:
        module.context.event_manager.fire_event(event, payload)
    except Exception:  # pylint: disable=W0703
        log.warning('Failed to fire %s audit event', event)


class RPC:
    # --- gating helpers -------------------------------------------------

    @web.rpc('social_folder_permissions_supported', 'folder_permissions_supported')
    def folder_permissions_supported(self, project_id: int) -> bool:
        """Folder exceptions only exist in Team projects.

        Fails closed on a missing `projects` RPC only for the *management* path;
        read paths treat a lookup failure as "no restrictions" via their own guards.
        """
        memo = _memo()
        key = ('kind', project_id)
        if memo is not None and key in memo:
            return memo[key]
        #
        try:
            supported = bool(
                self.context.rpc_manager.timeout(3).projects_is_team_project(project_id=project_id)
            )
        except Empty:
            log.debug('projects_is_team_project RPC unavailable, assuming Team project')
            supported = True
        #
        if memo is not None:
            memo[key] = supported
        return supported

    # --- resolution (read path) -----------------------------------------

    @web.rpc('social_resolve_folder_access', 'resolve_folder_access')
    def resolve_folder_access(
            self,
            project_id: int,
            folder_id: int,
            user_id: Optional[int] = None,
    ) -> str:
        """Effective access for one folder: 'full' | 'read_only' | 'no_access'.

        Restrictive overlay only: no row means the caller's RBAC default applies ('full'
        from this resolver's point of view — the caller's own permission decorator still runs).
        """
        if not folder_id:
            return EffectiveFolderAccess.full.value
        if not user_id:
            user_id = _current_user_id()
        if not user_id:
            return EffectiveFolderAccess.full.value
        #
        if not self.folder_permissions_supported(project_id):
            return EffectiveFolderAccess.full.value
        #
        memo = _memo()
        key = ('folder', project_id, folder_id, user_id)
        if memo is not None and key in memo:
            return memo[key]
        #
        with db.get_session(project_id) as session:
            level = session.query(FolderAccessOverride.access_level).filter(
                FolderAccessOverride.folder_id == folder_id,
                FolderAccessOverride.user_id == user_id,
            ).scalar()
        #
        result = level or EffectiveFolderAccess.full.value
        if memo is not None:
            memo[key] = result
        return result

    @web.rpc('social_assert_folder_access', 'assert_folder_access')
    def assert_folder_access(
            self,
            project_id: int,
            folder_id: int,
            write: bool = False,
            user_id: Optional[int] = None,
    ) -> bool:
        """True when the user may read (write=False) or modify (write=True) the folder."""
        level = self.resolve_folder_access(project_id, folder_id, user_id)
        if level == EffectiveFolderAccess.no_access.value:
            return False
        if write and level == EffectiveFolderAccess.read_only.value:
            return False
        return True

    @web.rpc('social_get_restricted_folder_ids', 'get_restricted_folder_ids')
    def get_restricted_folder_ids(
            self,
            project_id: int,
            entity_type: Union[str, List[str], None] = None,
            user_id: Optional[int] = None,
            levels: Optional[List[str]] = None,
    ) -> list:
        """Folder ids the user must not see entities from (default: no_access folders).

        Returns [] when nothing is restricted, which lets callers skip all extra work.
        """
        if not user_id:
            user_id = _current_user_id()
        if not user_id:
            return []
        #
        if not self.folder_permissions_supported(project_id):
            return []
        #
        if levels is None:
            levels = [FolderAccessLevel.no_access.value]
        #
        types = None
        if entity_type:
            types = [entity_type] if isinstance(entity_type, str) else list(entity_type)
        #
        memo = _memo()
        key = ('restricted', project_id, user_id, tuple(sorted(levels)),
               tuple(sorted(types)) if types else None)
        if memo is not None and key in memo:
            return memo[key]
        #
        with db.get_session(project_id) as session:
            q = session.query(FolderAccessOverride.folder_id).filter(
                FolderAccessOverride.user_id == user_id,
                FolderAccessOverride.access_level.in_(levels),
            )
            if types:
                q = q.join(
                    EntityFolder, EntityFolder.id == FolderAccessOverride.folder_id
                ).filter(EntityFolder.entity_type.in_(types))
            result = [row[0] for row in q.all()]
        #
        if memo is not None:
            memo[key] = result
        return result

    @web.rpc('social_folder_exclusion_clause', 'folder_exclusion_clause')
    def folder_exclusion_clause(
            self,
            project_id: int,
            entity_type: Union[str, List[str]],
            id_column,
            user_id: Optional[int] = None,
    ):
        """SQL predicate excluding entities inside the user's no-access folders.

        Returns None when nothing is restricted so callers can skip the clause entirely.
        `entity_type` may be a list for mixed listings (agent + pipeline).
        """
        restricted = self.get_restricted_folder_ids(project_id, entity_type, user_id)
        if not restricted:
            return None
        #
        types = [entity_type] if isinstance(entity_type, str) else list(entity_type)
        return ~exists().where(and_(
            FolderItem.entity.in_(types),
            FolderItem.entity_id == id_column,
            FolderItem.folder_id.in_(restricted),
        ))

    @web.rpc('social_filter_restricted_entity_ids', 'filter_restricted_entity_ids')
    def filter_restricted_entity_ids(
            self,
            project_id: int,
            entity_type: Union[str, List[str]],
            entity_ids: List[int],
            user_id: Optional[int] = None,
    ) -> list:
        """Subset of `entity_ids` the user may see. Used where a SQL clause cannot be injected."""
        if not entity_ids:
            return []
        restricted = self.get_restricted_folder_ids(project_id, entity_type, user_id)
        if not restricted:
            return list(entity_ids)
        #
        types = [entity_type] if isinstance(entity_type, str) else list(entity_type)
        with db.get_session(project_id) as session:
            hidden = {
                row[0] for row in session.query(FolderItem.entity_id).filter(
                    FolderItem.entity.in_(types),
                    FolderItem.entity_id.in_(entity_ids),
                    FolderItem.folder_id.in_(restricted),
                ).all()
            }
        return [i for i in entity_ids if i not in hidden]

    @web.rpc('social_resolve_entity_access', 'resolve_entity_access')
    def resolve_entity_access(
            self,
            project_id: int,
            entity_type: Union[str, List[str]],
            entity_id: int,
            user_id: Optional[int] = None,
    ) -> str:
        """Effective access for one entity via its containing folder.

        `entity_type` may be a list when the caller cannot cheaply tell the concrete
        type apart (agent vs pipeline, toolkit vs mcp) — ids are unique per table.

        'full' when the entity is in no folder, in a folder without an exception for
        this user, or when folder permissions do not apply to the project.
        """
        if not entity_id:
            return EffectiveFolderAccess.full.value
        if not user_id:
            user_id = _current_user_id()
        if not user_id:
            return EffectiveFolderAccess.full.value
        #
        if not self.folder_permissions_supported(project_id):
            return EffectiveFolderAccess.full.value
        #
        types = [entity_type] if isinstance(entity_type, str) else list(entity_type)
        #
        memo = _memo()
        key = ('entity', project_id, tuple(sorted(types)), entity_id, user_id)
        if memo is not None and key in memo:
            return memo[key]
        #
        with db.get_session(project_id) as session:
            level = session.query(FolderAccessOverride.access_level).join(
                FolderItem, FolderItem.folder_id == FolderAccessOverride.folder_id
            ).filter(
                FolderItem.entity.in_(types),
                FolderItem.entity_id == entity_id,
                FolderAccessOverride.user_id == user_id,
            ).scalar()
        #
        result = level or EffectiveFolderAccess.full.value
        if memo is not None:
            memo[key] = result
        return result

    @web.rpc('social_resolve_entities_access_bulk', 'resolve_entities_access_bulk')
    def resolve_entities_access_bulk(
            self,
            project_id: int,
            entity_type: Union[str, List[str]],
            entity_ids: List[int],
            user_id: Optional[int] = None,
    ) -> dict:
        """{entity_id: level} for the restricted ones only; absent means 'full'."""
        if not entity_ids:
            return {}
        if not user_id:
            user_id = _current_user_id()
        if not user_id:
            return {}
        #
        if not self.folder_permissions_supported(project_id):
            return {}
        #
        types = [entity_type] if isinstance(entity_type, str) else list(entity_type)
        with db.get_session(project_id) as session:
            rows = session.query(
                FolderItem.entity_id, FolderAccessOverride.access_level
            ).join(
                FolderAccessOverride,
                FolderAccessOverride.folder_id == FolderItem.folder_id,
            ).filter(
                FolderItem.entity.in_(types),
                FolderItem.entity_id.in_(entity_ids),
                FolderAccessOverride.user_id == user_id,
            ).all()
        return {row[0]: row[1] for row in rows}

    # --- management (write path) ----------------------------------------

    @web.rpc('social_list_folder_access', 'list_folder_access')
    def list_folder_access(self, project_id: int, folder_id: int) -> dict:
        """All exceptions stored for a folder."""
        with db.get_session(project_id) as session:
            folder = session.query(EntityFolder).filter(
                EntityFolder.id == folder_id
            ).first()
            if not folder:
                return {'ok': False, 'error': 'Folder not found'}
            #
            rows = session.query(FolderAccessOverride).filter(
                FolderAccessOverride.folder_id == folder_id
            ).order_by(FolderAccessOverride.user_id).all()
            #
            return {
                'ok': True,
                'folder_id': folder_id,
                'total': len(rows),
                'overrides': [
                    serialize(FolderAccessOverrideDetails.model_validate(r)) for r in rows
                ],
            }

    @web.rpc('social_set_folder_access', 'set_folder_access')
    def set_folder_access(
            self,
            project_id: int,
            folder_id: int,
            entries: List[dict],
            actor_id: Optional[int] = None,
    ) -> dict:
        """Insert/replace exceptions for the listed users. Atomic: all entries or none."""
        if not self.folder_permissions_supported(project_id):
            return {'ok': False, 'error': 'Folder permissions are available in Team projects only'}
        #
        if not actor_id:
            actor_id = _current_user_id()
        #
        try:
            payload = FolderAccessBulkUpsert(entries=entries)
        except ValidationError as e:
            return {'ok': False, 'error': str(e)}
        #
        members = _project_member_ids(self, project_id)
        if members is None:
            return {'ok': False, 'error': 'Cannot verify project membership right now'}
        #
        unknown = sorted({e.user_id for e in payload.entries} - members)
        if unknown:
            return {
                'ok': False,
                'error': f'Users are not members of this project: {unknown}',
            }
        #
        with db.get_session(project_id) as session:
            folder = session.query(EntityFolder).filter(
                EntityFolder.id == folder_id
            ).first()
            if not folder:
                return {'ok': False, 'error': 'Folder not found'}
            #
            existing = {
                row.user_id: row for row in session.query(FolderAccessOverride).filter(
                    FolderAccessOverride.folder_id == folder_id,
                    FolderAccessOverride.user_id.in_([e.user_id for e in payload.entries]),
                ).all()
            }
            #
            for entry in payload.entries:
                row = existing.get(entry.user_id)
                if row:
                    row.access_level = entry.access_level
                else:
                    session.add(FolderAccessOverride(
                        folder_id=folder_id,
                        user_id=entry.user_id,
                        access_level=entry.access_level,
                        project_id=project_id,
                        created_by=actor_id,
                    ))
            session.commit()
        #
        _audit(self, FOLDER_ACCESS_GRANTED_EVENT, {
            'project_id': project_id,
            'folder_id': folder_id,
            'actor_id': actor_id,
            'entries': [{'user_id': e.user_id, 'access_level': e.access_level}
                        for e in payload.entries],
        })
        return {'ok': True, 'folder_id': folder_id, 'updated': len(payload.entries)}

    @web.rpc('social_remove_folder_access', 'remove_folder_access')
    def remove_folder_access(
            self,
            project_id: int,
            folder_id: int,
            user_ids: List[int],
            actor_id: Optional[int] = None,
    ) -> dict:
        """Drop exceptions, returning the listed users to their RBAC default (read/write)."""
        if not actor_id:
            actor_id = _current_user_id()
        #
        try:
            payload = FolderAccessBulkRemove(user_ids=user_ids)
        except ValidationError as e:
            return {'ok': False, 'error': str(e)}
        #
        with db.get_session(project_id) as session:
            deleted = session.query(FolderAccessOverride).filter(
                FolderAccessOverride.folder_id == folder_id,
                FolderAccessOverride.user_id.in_(payload.user_ids),
            ).delete(synchronize_session=False)
            session.commit()
        #
        _audit(self, FOLDER_ACCESS_REVOKED_EVENT, {
            'project_id': project_id,
            'folder_id': folder_id,
            'actor_id': actor_id,
            'user_ids': payload.user_ids,
        })
        return {'ok': True, 'folder_id': folder_id, 'deleted': deleted}

    @web.rpc('social_purge_user_folder_access', 'purge_user_folder_access')
    def purge_user_folder_access(self, project_id: int, user_ids: List[int]) -> dict:
        """Drop every exception for users removed from the project."""
        if not user_ids:
            return {'ok': True, 'deleted': 0}
        with db.get_session(project_id) as session:
            deleted = session.query(FolderAccessOverride).filter(
                FolderAccessOverride.user_id.in_(list(user_ids))
            ).delete(synchronize_session=False)
            session.commit()
        return {'ok': True, 'deleted': deleted}
