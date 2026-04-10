from pathlib import Path

from flask import url_for
from tools import rpc_tools, db, auth
from pylon.core.tools import web, log

from ...elitea_core.utils.constants import ICON_PATH_DELIMITER


class RPC:
    @web.rpc(f'social_get_icons_list', "get_icons_list")
    def get_icons_list(
        self, project_id: int, flask_route_url: str,
        folder_path: Path, skip: int = 0, limit: int = None
    ) -> dict:
        results = list()
        for icon in folder_path.iterdir():
            icon_name: str = icon.name
            results.append({
                'name': icon_name,
                'url': url_for(
                    flask_route_url,
                    sub_path=f'{project_id}/{icon_name}' if project_id else str(icon_name),
                    _external=True
                )
            })

        results = sorted(results, key=lambda x: x['name'])

        if not limit:
            limit = len(results)

        to_show = results[skip:skip + limit]

        return {'total': len(results), 'rows': to_show}

    @web.rpc(f'social_update_icon_with_entity', "update_icon_with_entity")
    def update_icon_with_entity(
            self, project_id: int, entity_id: int, icon_path: Path,
            new_meta: dict, EntityModel
    ) -> dict:
        with db.get_session(project_id) as session:
            entity = session.query(EntityModel).filter(
                EntityModel.id == entity_id
            ).first()
            if not entity:
                return {'ok': False, 'msg': f'There is no such id {entity_id}'}

            if entity.meta:
                entity.meta['icon_meta'] = new_meta
            else:
                entity.meta = {'icon_meta': new_meta}
            session.commit()
            return {'data': new_meta, 'ok': True}

    @web.rpc(f'social_delete_icon_from_entity', "delete_icon_from_entity")
    def delete_icon_from_entity(self, project_id: int, icon_name: str, icons_path: Path, Entity):
        with db.get_session(project_id) as session:
            entities = session.query(Entity).all()

            for entity in entities:
                if entity.meta:
                    icon_meta = entity.meta.get('icon_meta', {})
                    version_icon_name = icon_meta.get('name')
                    if version_icon_name == icon_name:
                        entity.meta['icon_meta'] = {}

            session.commit()

            result = rpc_tools.RpcMixin().rpc.call.social_remove_image(
                icons_path.joinpath(
                    icon_name
                )
            )

        return result
