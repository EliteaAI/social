from flask import request
from tools import api_tools, config as c, auth, register_openapi

from ...models.pd.banners import BannerModel


PUBLIC_BANNER_FIELDS = (
    "id", "message", "dismissible", "persist_dismissal",
    "placement", "style", "icon", "sort_order", "updated_at",
)


class ProjectAPI(api_tools.APIModeHandler):
    """End-user facing banner endpoint (logged-in platform users).

    EliteaUI renders `rows` as a queue in the returned order and keys dismissals on `id` + `updated_at`,
    so keep the `{total, rows}` shape and these field names stable.
    """

    @register_openapi(
        name="List Current Banners",
        description="List enabled platform banners with a non-empty message, in display order.",
        available_to_users=True,
    )
    @api_tools.endpoint_metrics
    def get(self, **kwargs):
        result = self.module.list_banners(only_enabled=True)
        rows = [
            {field: banner.get(field) for field in PUBLIC_BANNER_FIELDS}
            for banner in result.get("result", [])
            if (banner.get("message") or "").strip()
        ]
        return {"total": len(rows), "rows": rows}, 200


class AdminAPI(api_tools.APIModeHandler):
    """Admin Platform banner configuration (list / create)."""

    @register_openapi(
        name="List Banners",
        description="List all configured platform banners in display order.",
        available_to_users=False,
    )
    @auth.decorators.check_api({
        "permissions": ["models.admin.banners.manage"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": False, "viewer": False},
        }})
    def get(self, **kwargs):
        result = self.module.list_banners()
        return result, 200

    @register_openapi(
        name="Create Banner",
        description="Create a new platform banner.",
        request_body=BannerModel,
        available_to_users=False,
    )
    @auth.decorators.check_api({
        "permissions": ["models.admin.banners.manage"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": False, "viewer": False},
        }})
    def post(self, **kwargs):
        result = self.module.create_banner(request.get_json())
        return result, 201 if result.get("ok") else 400


class API(api_tools.APIBase):
    url_params = api_tools.with_modes([
        "",
    ])

    mode_handlers = {
        c.DEFAULT_MODE: ProjectAPI,
        c.ADMINISTRATION_MODE: AdminAPI,
    }
