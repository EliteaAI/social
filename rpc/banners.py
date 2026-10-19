from pydantic.v1 import ValidationError
from sqlalchemy import func

from tools import db
from pylon.core.tools import web

from ..models.banners import Banner
from ..models.pd.banners import BANNER_FIELDS, BannerModel, BannerUpdateModel, apply_banner_update


class RPC:
    @web.rpc("social_list_banners", "list_banners")
    def list_banners(self, only_enabled: bool = False) -> dict:
        with db.with_project_schema_session(None) as session:
            query = session.query(Banner)
            if only_enabled:
                query = query.filter(Banner.enabled.is_(True))
            banners = query.order_by(Banner.sort_order, Banner.id).all()
            return {"ok": True, "result": [banner.to_json() for banner in banners]}

    @web.rpc("social_get_banner", "get_banner")
    def get_banner(self, banner_id: int) -> dict:
        with db.with_project_schema_session(None) as session:
            banner = session.query(Banner).get(banner_id)
            if not banner:
                return {"ok": False, "error": f"Banner with id '{banner_id}' not found"}
            return {"ok": True, "result": banner.to_json()}

    @web.rpc("social_create_banner", "create_banner")
    def create_banner(self, data: dict) -> dict:
        try:
            payload = BannerModel.parse_obj(data)
        except ValidationError as e:
            return {"ok": False, "error": str(e)}

        with db.with_project_schema_session(None) as session:
            values = payload.dict()
            if values.get("sort_order") is None:
                # New banners go to the end of the queue
                max_order = session.query(func.max(Banner.sort_order)).scalar()
                values["sort_order"] = 0 if max_order is None else max_order + 1
            banner = Banner(**{field: values[field] for field in BANNER_FIELDS})
            session.add(banner)
            session.commit()
            return self.get_banner(banner.id)

    @web.rpc("social_update_banner", "update_banner")
    def update_banner(self, banner_id: int, payload: dict) -> dict:
        try:
            data = BannerUpdateModel.parse_obj(payload)
        except ValidationError as e:
            return {"ok": False, "error": str(e)}

        with db.with_project_schema_session(None) as session:
            banner = session.query(Banner).get(banner_id)
            if not banner:
                return {"ok": False, "error": f"Banner with id '{banner_id}' not found"}
            if apply_banner_update(banner, data):
                banner.updated_at = func.now()
            session.commit()
            return self.get_banner(banner.id)

    @web.rpc("social_delete_banner", "delete_banner")
    def delete_banner(self, banner_id: int) -> dict:
        with db.with_project_schema_session(None) as session:
            banner = session.query(Banner).get(banner_id)
            if not banner:
                return {"ok": False, "error": f"Banner with id '{banner_id}' not found"}
            session.delete(banner)
            session.commit()
            return {"ok": True, "result": "Successfully deleted"}
