from typing import Optional
from pydantic import ValidationError
from sqlalchemy import text

from tools import db, auth
from pylon.core.tools import web, log
from tools import serialize

from ..models.folders import EntityFolder
from ..models.pd.folders import EntityFolderCreate, EntityFolderUpdate, EntityFolderDetails
from ..constants import EntityType, ENTITY_TABLE_MAP


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
        """Create a folder for organizing entities."""
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
            query: str = None
    ) -> list[dict]:
        """List folders for an entity type."""
        if not user_id:
            user_id = auth.current_user().get("id")

        with db.get_session(project_id) as session:
            q = session.query(EntityFolder).filter(
                EntityFolder.owner_id == user_id,
                EntityFolder.entity_type == entity_type
            )
            if query:
                q = q.filter(EntityFolder.name.ilike(f'%{query}%'))

            folders = q.order_by(EntityFolder.name).all()
            return [serialize(EntityFolderDetails.model_validate(f)) for f in folders]

    @web.rpc('social_get_folder', 'get_folder')
    def get_folder(self, project_id: int, folder_id: int) -> Optional[dict]:
        """Get a single folder by ID."""
        with db.get_session(project_id) as session:
            folder = session.query(EntityFolder).filter(
                EntityFolder.id == folder_id
            ).first()
            if folder:
                return serialize(EntityFolderDetails.model_validate(folder))
            return None

    @web.rpc('social_update_folder', 'update_folder')
    def update_folder(
            self,
            project_id: int,
            folder_id: int,
            name: str = None,
            meta: dict = None
    ) -> dict:
        """Update folder name or metadata."""
        with db.get_session(project_id) as session:
            folder = session.query(EntityFolder).filter(
                EntityFolder.id == folder_id
            ).first()
            if not folder:
                return {'ok': False, 'error': 'Folder not found'}

            if name is not None:
                folder.name = name
            if meta is not None:
                folder.meta = meta

            session.commit()
            return {
                'ok': True,
                'folder': serialize(EntityFolderDetails.model_validate(folder))
            }

    @web.rpc('social_pin_folder', 'pin_folder')
    def pin_folder(self, project_id: int, folder_id: int, is_pinned: bool) -> dict:
        """Update folder pin status in meta field."""
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
    def delete_folder(self, project_id: int, folder_id: int) -> dict:
        """Delete a folder. Entities with this folder_id should be handled by caller."""
        with db.get_session(project_id) as session:
            folder = session.query(EntityFolder).filter(
                EntityFolder.id == folder_id
            ).first()
            if not folder:
                return {'ok': False, 'error': 'Folder not found'}

            session.delete(folder)
            session.commit()
            return {'ok': True}

    @web.rpc('social_get_folder_model', 'get_folder_model')
    def get_folder_model(self):
        """Return the EntityFolder model for advanced queries."""
        return EntityFolder

    @web.rpc('social_entity_exists', 'entity_exists')
    def entity_exists(self, project_id: int, entity_type: str, entity_id: int) -> bool:
        """Check if an entity exists in the database.

        Uses RPCs from respective plugins when available, falls back to direct SQL.
        """
        if not EntityType.is_valid(entity_type):
            return False

        # Try to use RPCs from respective plugins
        try:
            if entity_type in (EntityType.AGENT.value, EntityType.PIPELINE.value):
                app = self.context.rpc_manager.call.applications_get_by_id(
                    project_id=project_id, app_id=entity_id
                )
                return app is not None
            elif entity_type == EntityType.SKILL.value:
                skill = self.context.rpc_manager.call.skills_get(
                    project_id=project_id, id=entity_id
                )
                return skill is not None
            elif entity_type in (EntityType.TOOLKIT.value, EntityType.MCP.value):
                tool = self.context.rpc_manager.call.elitea_tools_get(
                    project_id=project_id, tool_id=entity_id
                )
                return tool is not None
            elif entity_type == EntityType.CONFIGURATION.value:
                config = self.context.rpc_manager.call.configuration_get(
                    project_id=project_id, configuration_id=entity_id
                )
                return config is not None
        except Exception as e:
            log.warning("RPC call failed for entity check, falling back to SQL: %s", e)

        # Fallback to direct SQL query
        table_name = ENTITY_TABLE_MAP.get(entity_type)
        if not table_name:
            return False

        schema = f"p_{project_id}"
        with db.get_session(project_id) as session:
            result = session.execute(
                text(f"SELECT id FROM {schema}.{table_name} WHERE id = :entity_id"),
                {"entity_id": entity_id}
            ).fetchone()
            return result is not None

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

        Validates:
        - Entity exists
        - Folder exists and belongs to user (if folder_id provided)
        - Folder entity_type matches
        """
        if not user_id:
            user_id = auth.current_user().get("id")

        if not EntityType.is_valid(entity_type):
            return {'ok': False, 'error': f"Invalid entity_type. Must be one of: {', '.join(EntityType.values())}"}

        # Check entity exists
        if not self.entity_exists(project_id, entity_type, entity_id):
            return {'ok': False, 'error': f'{entity_type.capitalize()} not found'}

        table_name = ENTITY_TABLE_MAP.get(entity_type)
        schema = f"p_{project_id}"

        with db.get_session(project_id) as session:
            # If folder_id is None, remove from folder
            if folder_id is None:
                session.execute(
                    text(f"UPDATE {schema}.{table_name} SET folder_id = NULL WHERE id = :entity_id"),
                    {"entity_id": entity_id}
                )
                session.commit()
                return {
                    'ok': True,
                    'message': f'{entity_type.capitalize()} removed from folder',
                    'entity_type': entity_type,
                    'entity_id': entity_id,
                    'folder_id': None
                }

            # Verify folder exists and belongs to user
            folder = session.query(EntityFolder).filter(
                EntityFolder.id == folder_id,
                EntityFolder.owner_id == user_id
            ).first()
            if not folder:
                return {'ok': False, 'error': 'Folder not found or you don\'t have permission'}

            # Verify folder entity_type matches
            if folder.entity_type != entity_type:
                return {
                    'ok': False,
                    'error': f"Folder type mismatch. Folder is for '{folder.entity_type}' but entity is '{entity_type}'"
                }

            # Move entity to folder
            session.execute(
                text(f"UPDATE {schema}.{table_name} SET folder_id = :folder_id WHERE id = :entity_id"),
                {"folder_id": folder_id, "entity_id": entity_id}
            )
            session.commit()

            log.info("Moved %s %s to folder %s", entity_type, entity_id, folder_id)
            return {
                'ok': True,
                'message': f'{entity_type.capitalize()} moved to folder',
                'entity_type': entity_type,
                'entity_id': entity_id,
                'folder_id': folder_id
            }
