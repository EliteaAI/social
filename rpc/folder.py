from typing import Optional, List, Union
from pydantic import ValidationError
from sqlalchemy import func

from tools import db, auth
from pylon.core.tools import web, log
from tools import serialize

from ..models.folders import EntityFolder
from ..models.folder_items import FolderItem
from ..models.folder_access import FolderAccessOverride
from ..models.pd.folders import EntityFolderCreate, EntityFolderDetails, FolderItemDetails
from ..models.enums.entity import EntityType, FOLDER_ENTITY_TYPES
from ..models.enums.folder_access import EffectiveFolderAccess
from ..constants import is_valid_folder_entity


NO_ACCESS_ERROR = 'Folder not found or you don\'t have permission'
READ_ONLY_ERROR = 'You have read-only access to this folder'


def _name_taken(session, entity_type: str, name: str, exclude_id: int = None) -> bool:
    """Case-insensitive folder-name collision inside one entity type."""
    q = session.query(EntityFolder.id).filter(
        EntityFolder.entity_type == entity_type,
        func.lower(EntityFolder.name) == (name or '').strip().lower()
    )
    if exclude_id:
        q = q.filter(EntityFolder.id != exclude_id)
    return session.query(q.exists()).scalar()


def _deny_write(module, project_id: int, folder_id: int, user_id: Optional[int]):
    """None when the write is allowed, else the error payload to return."""
    level = module.resolve_folder_access(project_id, folder_id, user_id)
    if level == EffectiveFolderAccess.no_access.value:
        return {'ok': False, 'error': NO_ACCESS_ERROR}
    if level == EffectiveFolderAccess.read_only.value:
        return {'ok': False, 'error': READ_ONLY_ERROR}
    return None


class RPC:
    @web.rpc('social_create_folder', 'create_folder')
    def create_folder(
            self,
            project_id: int,
            entity_type: str,
            name: str,
            user_id: int = None,
            meta: dict = None
    ) -> dict:
        """Create a folder for organizing entities. Folders are shared across the project."""
        if not user_id:
            user_id = auth.current_user().get("id")

        try:
            parsed = EntityFolderCreate(
                name=name,
                entity_type=entity_type,
                owner_id=user_id,
                meta=meta or {}
            )
        except ValidationError as e:
            return {'ok': False, 'error': str(e)}

        with db.get_session(project_id) as session:
            if _name_taken(session, entity_type, parsed.name):
                return {
                    'ok': False,
                    'error': f"A '{entity_type}' folder named '{parsed.name}' already exists"
                }
            folder = EntityFolder(**parsed.model_dump())
            session.add(folder)
            session.commit()
            return {
                'ok': True,
                'folder': serialize(EntityFolderDetails.model_validate(folder))
            }

    @web.rpc('social_get_folders', 'get_folders')
    def get_folders(
            self,
            project_id: int,
            entity_type: str,
            user_id: int = None,
            query: str = None,
            include_counts: bool = False
    ) -> list[dict]:
        """List project folders for an entity type, hiding the caller's no-access folders."""
        if not user_id:
            user_id = auth.current_user().get("id")

        restricted = set(self.get_restricted_folder_ids(project_id, entity_type, user_id))
        read_only = set(self.get_restricted_folder_ids(
            project_id, entity_type, user_id,
            levels=[EffectiveFolderAccess.read_only.value],
        ))

        with db.get_session(project_id) as session:
            q = session.query(EntityFolder).filter(
                EntityFolder.entity_type == entity_type
            )
            if query:
                q = q.filter(EntityFolder.name.ilike(f'%{query}%'))
            if restricted:
                q = q.filter(EntityFolder.id.notin_(restricted))

            folders = q.order_by(EntityFolder.name).all()
            if not folders:
                return []

            counts = {}
            if include_counts:
                rows = session.query(
                    FolderItem.folder_id, func.count(FolderItem.id)
                ).filter(
                    FolderItem.folder_id.in_([f.id for f in folders])
                ).group_by(FolderItem.folder_id).all()
                counts = dict(rows)

            result = []
            for f in folders:
                folder_data = serialize(EntityFolderDetails.model_validate(f))
                if include_counts:
                    folder_data['entities_count'] = counts.get(f.id, 0)
                folder_data['access_level'] = (
                    EffectiveFolderAccess.read_only.value if f.id in read_only
                    else EffectiveFolderAccess.full.value
                )
                result.append(folder_data)

            return result

    @web.rpc('social_get_folder', 'get_folder')
    def get_folder(
            self,
            project_id: int,
            folder_id: int,
            include_count: bool = False,
            user_id: Optional[int] = None
    ) -> Optional[dict]:
        """Get a single project folder by ID, subject to the caller's folder access."""
        if not self.assert_folder_access(project_id, folder_id, user_id=user_id):
            return None

        with db.get_session(project_id) as session:
            folder = session.query(EntityFolder).filter(
                EntityFolder.id == folder_id
            ).first()
            if folder:
                result = serialize(EntityFolderDetails.model_validate(folder))
                result['access_level'] = self.resolve_folder_access(
                    project_id, folder_id, user_id
                )
                if include_count:
                    count = session.query(func.count(FolderItem.id)).filter(
                        FolderItem.folder_id == folder_id
                    ).scalar()
                    result['entities_count'] = count
                return result
            return None

    @web.rpc('social_update_folder', 'update_folder')
    def update_folder(
            self,
            project_id: int,
            folder_id: int,
            name: str = None,
            meta: dict = None,
            user_id: Optional[int] = None
    ) -> dict:
        """Update folder name or metadata."""
        denied = _deny_write(self, project_id, folder_id, user_id)
        if denied:
            return denied

        with db.get_session(project_id) as session:
            folder = session.query(EntityFolder).filter(
                EntityFolder.id == folder_id
            ).first()
            if not folder:
                return {'ok': False, 'error': 'Folder not found'}

            if name is not None and name != folder.name:
                if _name_taken(session, folder.entity_type, name, exclude_id=folder_id):
                    return {
                        'ok': False,
                        'error': f"A '{folder.entity_type}' folder named '{name}' already exists"
                    }
                folder.name = name
            if meta is not None:
                folder.meta = meta

            session.commit()
            return {
                'ok': True,
                'folder': serialize(EntityFolderDetails.model_validate(folder))
            }

    @web.rpc('social_pin_folder', 'pin_folder')
    def pin_folder(
            self,
            project_id: int,
            folder_id: int,
            is_pinned: bool,
            user_id: Optional[int] = None
    ) -> dict:
        """Update folder pin status in meta field."""
        denied = _deny_write(self, project_id, folder_id, user_id)
        if denied:
            return denied

        with db.get_session(project_id) as session:
            folder = session.query(EntityFolder).filter(
                EntityFolder.id == folder_id
            ).first()
            if not folder:
                return {'ok': False, 'error': 'Folder not found'}

            meta = dict(folder.meta) if folder.meta else {}
            meta['is_pinned'] = is_pinned
            folder.meta = meta

            session.commit()
            return {
                'ok': True,
                'folder': serialize(EntityFolderDetails.model_validate(folder))
            }

    @web.rpc('social_delete_folder', 'delete_folder')
    def delete_folder(
            self,
            project_id: int,
            folder_id: int,
            user_id: Optional[int] = None
    ) -> dict:
        """Delete a folder, its folder items and its access exceptions."""
        denied = _deny_write(self, project_id, folder_id, user_id)
        if denied:
            return denied

        with db.get_session(project_id) as session:
            folder = session.query(EntityFolder).filter(
                EntityFolder.id == folder_id
            ).first()
            if not folder:
                return {'ok': False, 'error': 'Folder not found'}

            session.query(FolderItem).filter(
                FolderItem.folder_id == folder_id
            ).delete(synchronize_session=False)

            session.query(FolderAccessOverride).filter(
                FolderAccessOverride.folder_id == folder_id
            ).delete(synchronize_session=False)

            session.delete(folder)
            session.commit()
            return {'ok': True}

    @web.rpc('social_get_folder_model', 'get_folder_model')
    def get_folder_model(self):
        """Return the EntityFolder model for advanced queries."""
        return EntityFolder

    @web.rpc('social_get_folder_item_model', 'get_folder_item_model')
    def get_folder_item_model(self):
        """Return the FolderItem model for advanced queries."""
        return FolderItem

    @web.rpc('social_entity_exists', 'entity_exists')
    def entity_exists(self, project_id: int, entity_type: str, entity_id: int) -> dict:
        """Check if an entity of the specified type exists.

        Returns {'exists': bool, 'name': str or None}

        IMPORTANT: This validates that the entity's actual type matches the requested
        entity_type. For example, if you request entity_type='agent' but entity_id
        points to a pipeline, this returns exists=False.
        """
        if not is_valid_folder_entity(entity_type):
            return {'exists': False, 'name': None}

        try:
            et = EntityType(entity_type)

            if et == EntityType.agent:
                # Only match non-pipeline applications (agents)
                app = self.context.rpc_manager.timeout(5).applications_get_application_by_id(
                    project_id=project_id, application_id=entity_id
                )
                # agent_type is in version_details, not at top level
                version_details = app.get('version_details', {}) if app else {}
                actual_agent_type = version_details.get('agent_type')
                if app and actual_agent_type != 'pipeline':
                    return {'exists': True, 'name': app.get('name', '')}

            elif et == EntityType.pipeline:
                # Only match pipeline applications
                app = self.context.rpc_manager.timeout(5).applications_get_application_by_id(
                    project_id=project_id, application_id=entity_id
                )
                # agent_type is in version_details, not at top level
                version_details = app.get('version_details', {}) if app else {}
                actual_agent_type = version_details.get('agent_type')
                if app and actual_agent_type == 'pipeline':
                    return {'exists': True, 'name': app.get('name', '')}

            elif et == EntityType.skill:
                skill = self.context.rpc_manager.timeout(5).skills_get_skill_by_id(
                    project_id=project_id, skill_id=entity_id
                )
                if skill:
                    return {'exists': True, 'name': skill.get('name', '')}

            elif et == EntityType.toolkit:
                # Only match non-MCP toolkits (exclude type='mcp' and meta.mcp=True local MCPs)
                tool = self.context.rpc_manager.timeout(5).applications_get_toolkit_by_id(
                    project_id=project_id, toolkit_id=entity_id
                )
                if tool:
                    is_mcp = tool.get('type') == 'mcp' or (tool.get('meta') or {}).get('mcp') is True
                    if not is_mcp:
                        return {'exists': True, 'name': tool.get('name', '')}

            elif et == EntityType.mcp:
                # Only match MCP toolkits (either type='mcp' or meta.mcp=True for local MCPs)
                tool = self.context.rpc_manager.timeout(5).applications_get_toolkit_by_id(
                    project_id=project_id, toolkit_id=entity_id
                )
                if tool:
                    is_mcp = tool.get('type') == 'mcp' or (tool.get('meta') or {}).get('mcp') is True
                    if is_mcp:
                        return {'exists': True, 'name': tool.get('name', '')}

            elif et == EntityType.configuration:
                config = self.context.rpc_manager.timeout(5).configurations_get_by_id(
                    project_id=project_id, configuration_id=entity_id
                )
                if config:
                    return {'exists': True, 'name': config.get('name', '')}

        except Exception as e:
            log.warning("RPC call failed for entity check: %s", e)

        return {'exists': False, 'name': None}

    @web.rpc('social_move_entity_to_folder', 'move_entity_to_folder')
    def move_entity_to_folder(
            self,
            project_id: int,
            entity_type: str,
            entity_id: int,
            folder_id: Optional[int],
            user_id: Optional[int] = None
    ) -> dict:
        """Move an entity to a folder or remove from folder (folder_id=None).

        Uses FolderItem join table instead of updating entity tables directly.
        """
        if not user_id:
            user_id = auth.current_user().get("id")

        if not is_valid_folder_entity(entity_type):
            valid = ', '.join(e.value for e in FOLDER_ENTITY_TYPES)
            return {'ok': False, 'error': f"Invalid entity_type. Must be one of: {valid}"}

        # Check entity exists and get name for sorting
        entity_check = self.entity_exists(project_id, entity_type, entity_id)
        if not entity_check['exists']:
            return {'ok': False, 'error': f'{entity_type.capitalize()} not found'}

        # Leaving a folder requires write access on that folder too
        current = self.get_entity_folder(project_id, entity_type, entity_id, user_id)
        if current:
            denied = _deny_write(self, project_id, current['id'], user_id)
            if denied:
                return denied

        if folder_id is not None:
            denied = _deny_write(self, project_id, folder_id, user_id)
            if denied:
                return denied

        with db.get_session(project_id) as session:
            # Remove existing folder membership for this entity (project-wide)
            session.query(FolderItem).filter(
                FolderItem.entity == entity_type,
                FolderItem.entity_id == entity_id
            ).delete(synchronize_session=False)

            # If folder_id is None, just remove (already done above)
            if folder_id is None:
                session.commit()
                return {
                    'ok': True,
                    'message': f'{entity_type.capitalize()} removed from folder',
                    'entity_type': entity_type,
                    'entity_id': entity_id,
                    'folder_id': None
                }

            folder = session.query(EntityFolder).filter(
                EntityFolder.id == folder_id
            ).first()
            if not folder:
                session.rollback()
                return {'ok': False, 'error': NO_ACCESS_ERROR}

            # Verify folder entity_type matches
            if folder.entity_type != entity_type:
                session.rollback()
                return {
                    'ok': False,
                    'error': f"Folder type mismatch. Folder is for '{folder.entity_type}' but entity is '{entity_type}'"
                }

            # Create new folder item
            folder_item = FolderItem(
                folder_id=folder_id,
                entity=entity_type,
                entity_id=entity_id,
                project_id=project_id,
                owner_id=user_id,
                sort_name=(entity_check['name'] or '').lower()
            )
            session.add(folder_item)
            session.commit()

            log.info("Moved %s %s to folder %s", entity_type, entity_id, folder_id)
            return {
                'ok': True,
                'message': f'{entity_type.capitalize()} moved to folder',
                'entity_type': entity_type,
                'entity_id': entity_id,
                'folder_id': folder_id
            }

    @web.rpc('social_get_folder_items', 'get_folder_items')
    def get_folder_items(
            self,
            project_id: int,
            folder_id: int,
            user_id: Optional[int] = None,
            sort_by: str = 'name',
            sort_order: str = 'asc',
            limit: int = 50,
            offset: int = 0
    ) -> dict:
        """Get paginated list of entity IDs in a folder.

        Returns entity IDs that can be used with entity-specific list endpoints
        using ids= filter for fetching full entity data.
        """
        if not user_id:
            user_id = auth.current_user().get("id")

        if not self.assert_folder_access(project_id, folder_id, user_id=user_id):
            return {'ok': False, 'error': NO_ACCESS_ERROR}

        with db.get_session(project_id) as session:
            folder = session.query(EntityFolder).filter(
                EntityFolder.id == folder_id
            ).first()
            if not folder:
                return {'ok': False, 'error': NO_ACCESS_ERROR}

            # Build query
            q = session.query(FolderItem).filter(
                FolderItem.folder_id == folder_id
            )

            # Total count before pagination
            total = q.count()

            # Sort
            if sort_by == 'name':
                order_col = FolderItem.sort_name
            elif sort_by == 'created':
                order_col = FolderItem.created_at
            elif sort_by == 'id':
                order_col = FolderItem.entity_id
            else:
                order_col = FolderItem.sort_name

            if sort_order == 'desc':
                order_col = order_col.desc()

            # Apply pagination
            items = q.order_by(order_col).limit(limit).offset(offset).all()

            return {
                'ok': True,
                'folder_id': folder_id,
                'entity_type': folder.entity_type,
                'access_level': self.resolve_folder_access(project_id, folder_id, user_id),
                'total': total,
                'limit': limit,
                'offset': offset,
                'items': [
                    {
                        'entity_id': item.entity_id,
                        'entity_type': item.entity,
                        'sort_name': item.sort_name
                    }
                    for item in items
                ]
            }

    @web.rpc('social_get_entity_folder', 'get_entity_folder')
    def get_entity_folder(
            self,
            project_id: int,
            entity_type: str,
            entity_id: int,
            user_id: Optional[int] = None
    ) -> Optional[dict]:
        """Get the folder an entity belongs to (if any)."""
        with db.get_session(project_id) as session:
            item = session.query(FolderItem).filter(
                FolderItem.entity == entity_type,
                FolderItem.entity_id == entity_id
            ).first()

            if not item:
                return None

            folder = session.query(EntityFolder).filter(
                EntityFolder.id == item.folder_id
            ).first()

            if folder:
                return serialize(EntityFolderDetails.model_validate(folder))
            return None

    @web.rpc('social_get_entities_folder_info_bulk', 'get_entities_folder_info_bulk')
    def get_entities_folder_info_bulk(
            self,
            project_id: int,
            entity_type: Union[str, List[str]],
            entity_ids: List[int],
            user_id: Optional[int] = None
    ) -> dict:
        """Get folder info for multiple entities in bulk.

        `entity_type` accepts a list so mixed listings (agent + pipeline) need one call.

        Returns a dict mapping entity_id to folder info:
        {entity_id: {'folder_id': int, 'folder_name': str}, ...}

        Entities not in any folder are not included in the result.
        """
        if not entity_ids:
            return {}

        types = [entity_type] if isinstance(entity_type, str) else list(entity_type)

        with db.get_session(project_id) as session:
            results = session.query(
                FolderItem.entity_id,
                FolderItem.folder_id,
                EntityFolder.name.label('folder_name')
            ).join(
                EntityFolder, EntityFolder.id == FolderItem.folder_id
            ).filter(
                FolderItem.entity.in_(types),
                FolderItem.entity_id.in_(entity_ids)
            ).all()

            return {
                row.entity_id: {
                    'folder_id': row.folder_id,
                    'folder_name': row.folder_name
                }
                for row in results
            }

    @web.rpc('social_remove_entity_from_folders', 'remove_entity_from_folders')
    def remove_entity_from_folders(
            self,
            project_id: int,
            entity_type: Union[str, List[str]],
            entity_id: int
    ) -> dict:
        """Remove an entity from all folders. Called on entity deletion.

        `entity_type` accepts a list so a deletion handler that cannot cheaply tell the
        concrete type apart (agent vs pipeline, toolkit vs mcp) still clears the row:
        entity ids are unique inside the underlying table.
        """
        types = [entity_type] if isinstance(entity_type, str) else list(entity_type)
        with db.get_session(project_id) as session:
            deleted = session.query(FolderItem).filter(
                FolderItem.entity.in_(types),
                FolderItem.entity_id == entity_id,
                FolderItem.project_id == project_id
            ).delete(synchronize_session=False)
            session.commit()

            return {'ok': True, 'deleted': deleted}
