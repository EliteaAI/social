"""Reconcile indexes added to folder tables after their first release.

`shared.ready()` provisions tables via `create_all(checkfirst=True)`, which skips tables
that already exist — so indexes added to `social_folder_items` / `entity_folders` later
never land on schemas created before them. New tables (e.g. `folder_access_overrides`)
need nothing here: they are tenant-scoped and `shared.ready()` creates them with all
their indexes and constraints.

This runs as an on-demand admin task, not on boot: a per-project loop in `ready()`
blocks the pylon boot thread for as long as there are projects.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed

from sqlalchemy import text

from pylon.core.tools import log
from tools import db, rpc_tools

from ..models.folders import EntityFolder
from ..models.folder_items import FolderItem


LOCK_TIMEOUT = '5s'

MAX_WORKERS = 8

MIGRATED_TABLES = (FolderItem.__table__, EntityFolder.__table__)


def _existing_indexes(schema_names: list[str]) -> dict[str, set[str]]:
    """Map schema -> index names already present on the folder tables."""
    table_names = [table.name for table in MIGRATED_TABLES]
    #
    found: dict[str, set[str]] = {}
    with db.engine.connect() as connection:
        rows = connection.execute(
            text(
                'SELECT schemaname, indexname FROM pg_indexes '
                'WHERE schemaname = ANY(:schemas) AND tablename = ANY(:tables)'
            ),
            {'schemas': schema_names, 'tables': table_names},
        ).fetchall()
    #
    for schema_name, index_name in rows:
        found.setdefault(schema_name, set()).add(index_name)
    return found


def _create_indexes(project_id: int, indexes: list) -> None:
    with db.get_session(project_id) as session:
        connection = session.connection()
        connection.execute(text(f"SET LOCAL lock_timeout = '{LOCK_TIMEOUT}'"))
        #
        for index in indexes:
            index.create(bind=connection, checkfirst=True)
        #
        session.commit()


def migrate_folder_indexes(*args, workers: int = MAX_WORKERS, **kwargs) -> dict:
    """Create missing folder-table indexes in every project schema. Safe to re-run."""
    _ = args, kwargs
    #
    from tools import project_constants  # pylint: disable=E0401,C0415
    #
    results = {'projects_checked': 0, 'projects_updated': 0, 'indexes_created': 0, 'errors': []}
    #
    projects = rpc_tools.RpcMixin().rpc.call.project_list(filter_={'create_success': True})
    schema_template = project_constants['PROJECT_SCHEMA_TEMPLATE']
    schemas = {project['id']: schema_template.format(project['id']) for project in projects}
    results['projects_checked'] = len(schemas)
    #
    existing = _existing_indexes(list(schemas.values()))
    #
    pending = {}
    for project_id, schema_name in schemas.items():
        present = existing.get(schema_name, set())
        missing = [
            index
            for table in MIGRATED_TABLES
            for index in table.indexes
            if index.name not in present
        ]
        if missing:
            pending[project_id] = (schema_name, missing)
    #
    if pending:
        with ThreadPoolExecutor(max_workers=min(workers, len(pending))) as executor:
            futures = {
                executor.submit(_create_indexes, project_id, missing): project_id
                for project_id, (_schema_name, missing) in pending.items()
            }
            #
            for future in as_completed(futures):
                project_id = futures[future]
                schema_name, missing = pending[project_id]
                try:
                    future.result()
                except Exception as exc:  # pylint: disable=W0703
                    log.warning('Folder index migration failed for project %s: %s', project_id, exc)
                    results['errors'].append(f'project {project_id}: {exc}')
                    continue
                #
                results['projects_updated'] += 1
                results['indexes_created'] += len(missing)
                log.info(
                    'Created folder indexes in %s: %s',
                    schema_name, ', '.join(index.name for index in missing),
                )
    #
    log.info(
        'Folder index migration complete: %s projects checked, %s updated, %s indexes created',
        results['projects_checked'], results['projects_updated'], results['indexes_created'],
    )
    return results
