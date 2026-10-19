from typing import Optional
from pydantic.v1 import BaseModel, validator


# EliteaUI renders exactly these values (and falls back for anything else): adding one needs a frontend change
BANNER_PLACEMENTS = ("top", "center", "bottom_right")
BANNER_STYLES = ("info", "warning")
BANNER_ICONS = ("info", "warning")

BANNER_FIELDS = (
    "name", "message", "enabled", "dismissible", "persist_dismissal",
    "placement", "style", "icon", "sort_order",
)
# Fields users see. EliteaUI keeps a dismissal while `updated_at` is unchanged, so changing one of these
# must bump it (the banner is shown again); name / enabled / sort_order changes must not
DISPLAY_FIELDS = ("message", "dismissible", "persist_dismissal", "placement", "style", "icon")


def apply_banner_update(banner, data) -> bool:
    """Copy the provided (non-None) fields that differ onto `banner`.

    Returns True when a displayed field changed, i.e. when `updated_at` must be bumped.
    """
    display_changed = False
    for field in BANNER_FIELDS:
        value = getattr(data, field)
        if value is not None and value != getattr(banner, field):
            setattr(banner, field, value)
            display_changed = display_changed or field in DISPLAY_FIELDS
    return display_changed


def _check_choice(value, choices, field):
    if value is not None and value not in choices:
        raise ValueError(f"{field} must be one of {list(choices)}, got '{value}'")
    return value


class BannerUpdateModel(BaseModel):
    name: Optional[str]
    message: Optional[str]
    enabled: Optional[bool]
    dismissible: Optional[bool]
    persist_dismissal: Optional[bool]
    placement: Optional[str]
    style: Optional[str]
    icon: Optional[str]
    sort_order: Optional[int]

    @validator("name", "message")
    def validate_not_blank(cls, v, field):
        # EliteaUI shows a banner only when it has a message, and the admin list needs a name
        if v is not None and not v.strip():
            raise ValueError(f"{field.name} must not be empty")
        return v

    @validator("placement")
    def validate_placement(cls, v):
        return _check_choice(v, BANNER_PLACEMENTS, "placement")

    @validator("style")
    def validate_style(cls, v):
        return _check_choice(v, BANNER_STYLES, "style")

    @validator("icon")
    def validate_icon(cls, v):
        return _check_choice(v, BANNER_ICONS, "icon")


class BannerModel(BannerUpdateModel):
    name: str
    message: str
    enabled: bool = False
    dismissible: bool = True
    persist_dismissal: bool = True
    placement: str = "top"
    style: str = "info"
    icon: str = "info"
    sort_order: Optional[int]

    class Config:
        schema_extra = {
            "examples": [
                {
                    "name": "AI disclosure",
                    "message": "This platform uses **AI systems**. Outputs may be inaccurate.",
                    "enabled": True,
                    "dismissible": True,
                    "persist_dismissal": False,
                    "placement": "center",
                    "style": "info",
                    "icon": "info",
                    "sort_order": 0,
                }
            ]
        }
