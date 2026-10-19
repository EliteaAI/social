from flask import request
from tools import api_tools, config as c, auth, register_openapi

from ...models.pd.banners import BannerUpdateModel


BANNER_ID_PARAM = {
    "name": "banner_id", "in": "path", "schema": {"type": "integer"},
    "description": "Banner identifier.",
}


class AdminAPI(api_tools.APIModeHandler):
    """Admin Platform single-banner configuration (get / update / delete)."""

    @register_openapi(
        name="Get Banner",
        description="Get a single platform banner by id.",
        parameters=[BANNER_ID_PARAM],
        available_to_users=False,
    )
    @auth.decorators.check_api({
        "permissions": ["models.admin.banners.manage"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": False, "viewer": False},
        }})
    def get(self, banner_id: int, **kwargs):
        result = self.module.get_banner(banner_id)
        return result, 200 if result.get("ok") else 404

    @register_openapi(
        name="Update Banner",
        description="Update a platform banner. Only provided fields are changed.",
        parameters=[BANNER_ID_PARAM],
        request_body=BannerUpdateModel,
        available_to_users=False,
    )
    @auth.decorators.check_api({
        "permissions": ["models.admin.banners.manage"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": False, "viewer": False},
        }})
    def put(self, banner_id: int, **kwargs):
        result = self.module.update_banner(banner_id, request.get_json())
        return result, 200 if result.get("ok") else 400

    @register_openapi(
        name="Delete Banner",
        description="Delete a platform banner.",
        parameters=[BANNER_ID_PARAM],
        available_to_users=False,
    )
    @auth.decorators.check_api({
        "permissions": ["models.admin.banners.manage"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": False, "viewer": False},
        }})
    def delete(self, banner_id: int, **kwargs):
        result = self.module.delete_banner(banner_id)
        return result, 200 if result.get("ok") else 404


class API(api_tools.APIBase):
    url_params = api_tools.with_modes([
        "<int:banner_id>",
    ])

    mode_handlers = {
        c.ADMINISTRATION_MODE: AdminAPI,
    }
