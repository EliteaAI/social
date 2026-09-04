"""Idempotent schema/data fixes for folder tables.

`shared.ready()` provisions *new* tables via `create_all(checkfirst=True)`, which silently
skips tables that already exist — so indexes and constraints added to `social_folder_items`
and `entity_folders` after their first release never land. This module applies them
explicitly, and cleans the data that would otherwise violate them.
"""
from sqlalchemy import func, inspect
from sqlalchemy.schema import AddConstraint

from pylon.core.tools import log
from tools import db

from ..models.folders import EntityFolder
from ..models.folder_items import FolderItem
from ..models.folder_access import FolderAccessOverride


UNIQUE_ENTITY_CONSTRAINT = '_folder_item_unique_entity_uc'


def _dedupe_folder_items(session) -> int:
    """Keep the earliest membership per entity (tie-break: lowest id), drop the rest."""
    ranked = session.query(
        FolderItem.id.label('id'),
        func.row_number().over(
            partition_by=(FolderItem.entity, FolderItem.entity_id),
            order_by=(FolderItem.created_at.asc(), FolderItem.id.asc()),
        ).label('rn'),
    ).subquery()
    #
    dupe_ids = [row[0] for row in session.query(ranked.c.id).filter(ranked.c.rn > 1).all()]
    if not dupe_ids:
        return 0
    #
    session.query(FolderItem).filter(
        FolderItem.id.in_(dupe_ids)
    ).delete(synchronize_session=False)
    return len(dupe_ids)


def _drop_orphan_folder_items(session) -> int:
    """Remove memberships pointing at folders that no longer exist."""
    orphan_ids = [
        row[0] for row in session.query(FolderItem.id).outerjoin(
            EntityFolder, EntityFolder.id == FolderItem.folder_id
        ).filter(EntityFolder.id.is_(None)).all()
    ]
    if not orphan_ids:
        return 0
    #
    session.query(FolderItem).filter(
        FolderItem.id.in_(orphan_ids)
    ).delete(synchronize_session=False)
    return len(orphan_ids)


def _ensure_indexes(connection, table) -> None:
    for index in table.indexes:
        try:
            index.create(bind=connection, checkfirst=True)
        except Exception:  # pylint: disable=W0703
            log.debug('Index %s already present or could not be created', index.name)


def _ensure_unique_entity_constraint(session, schema_name: str) -> None:
    """Add the one-folder-per-entity constraint if the DB does not have it yet."""
    try:
        existing = {
            c['name'] for c in inspect(session.connection()).get_unique_constraints(
                FolderItem.__tablename__, schema=schema_name
            )
        }
    except Exception:  # pylint: disable=W0703
        log.debug('Cannot inspect unique constraints on %s', FolderItem.__tablename__)
        return
    #
    if UNIQUE_ENTITY_CONSTRAINT in existing:
        return
    #
    constraint = next(
        (c for c in FolderItem.__table__.constraints if c.name == UNIQUE_ENTITY_CONSTRAINT),
        None,
    )
    if constraint is None:
        return
    #
    try:
        with session.begin_nested():
            session.execute(AddConstraint(constraint))
        log.info('Added %s on %s', UNIQUE_ENTITY_CONSTRAINT, schema_name)
    except Exception as exc:  # pylint: disable=W0703
        log.warning('Could not add %s on %s: %s', UNIQUE_ENTITY_CONSTRAINT, schema_name, exc)


def apply_folder_migrations(project_id: int, schema_name: str) -> dict:
    """Bring one project schema up to date. Safe to run repeatedly."""
    stats = {'deduped': 0, 'orphans': 0}
    #
    with db.get_session(project_id) as session:
        connection = session.connection()
        #
        # New table: needed here too because plugin ready() order is not guaranteed
        FolderAccessOverride.__table__.create(bind=connection, checkfirst=True)
        #
        stats['orphans'] = _drop_orphan_folder_items(session)
        stats['deduped'] = _dedupe_folder_items(session)
        session.flush()
        #
        _ensure_unique_entity_constraint(session, schema_name)
        _ensure_indexes(connection, FolderItem.__table__)
        _ensure_indexes(connection, EntityFolder.__table__)
        _ensure_indexes(connection, FolderAccessOverride.__table__)
        #
        session.commit()
    #
    return stats
