from typing import Optional
from pydantic import ValidationError

from tools import db, auth
from pylon.core.tools import web, log
from tools import serialize

from ..models.folders import EntityFolder
from ..models.pd.folders import EntityFolderCreate, EntityFolderUpdate, EntityFolderDetails


class RPC:
    @web.rpc('social_create_folder', 'create_folder')
    def create_folder(
            self,
            project_id: int,
            entity_type: str,
            name: str,
            sub_type: str = None,
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
                sub_type=sub_type,
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
            sub_type: str = None,
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
            if sub_type:
                q = q.filter(EntityFolder.sub_type == sub_type)
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
