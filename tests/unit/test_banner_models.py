"""Unit tests for banner Pydantic models and the update contract EliteaUI relies on (#6971)."""
import sys
from types import SimpleNamespace

import pytest
from pydantic.v1 import ValidationError


@pytest.fixture(scope='module')
def banners_module(models_path):
    pd_path = models_path / "pd"
    sys.path.insert(0, str(pd_path))
    try:
        import banners
        return banners
    finally:
        sys.path.remove(str(pd_path))


class TestBannerModel:
    def test_defaults(self, banners_module):
        b = banners_module.BannerModel(name="Disclosure", message="AI is used here")
        assert b.enabled is False
        assert b.dismissible is True
        assert b.persist_dismissal is True
        assert b.placement == "top"
        assert b.style == "info"
        assert b.icon == "info"
        assert b.sort_order is None

    def test_name_required(self, banners_module):
        with pytest.raises(ValidationError):
            banners_module.BannerModel(message="Hi")

    def test_message_required(self, banners_module):
        with pytest.raises(ValidationError):
            banners_module.BannerModel(name="B")

    def test_blank_message_rejected(self, banners_module):
        with pytest.raises(ValidationError) as exc_info:
            banners_module.BannerModel(name="B", message="   ")
        assert "message must not be empty" in str(exc_info.value)

    def test_blank_name_rejected(self, banners_module):
        with pytest.raises(ValidationError):
            banners_module.BannerModel(name=" ", message="M")

    def test_all_placements_valid(self, banners_module):
        for placement in ("top", "center", "bottom_right"):
            b = banners_module.BannerModel(name="B", message="M", placement=placement)
            assert b.placement == placement

    def test_invalid_placement_raises(self, banners_module):
        with pytest.raises(ValidationError) as exc_info:
            banners_module.BannerModel(name="B", message="M", placement="left")
        assert "placement must be one of" in str(exc_info.value)

    def test_invalid_style_raises(self, banners_module):
        with pytest.raises(ValidationError) as exc_info:
            banners_module.BannerModel(name="B", message="M", style="error")
        assert "style must be one of" in str(exc_info.value)

    def test_invalid_icon_raises(self, banners_module):
        with pytest.raises(ValidationError) as exc_info:
            banners_module.BannerModel(name="B", message="M", icon="danger")
        assert "icon must be one of" in str(exc_info.value)


class TestBannerUpdateModel:
    def test_all_fields_optional(self, banners_module):
        u = banners_module.BannerUpdateModel()
        assert all(value is None for value in u.dict().values())

    def test_partial_update(self, banners_module):
        u = banners_module.BannerUpdateModel(persist_dismissal=False, sort_order=3)
        assert u.persist_dismissal is False
        assert u.sort_order == 3
        assert u.placement is None

    def test_invalid_placement_raises(self, banners_module):
        with pytest.raises(ValidationError):
            banners_module.BannerUpdateModel(placement="top_left")

    def test_blank_message_rejected(self, banners_module):
        with pytest.raises(ValidationError):
            banners_module.BannerUpdateModel(message="")


def _stored_banner(**overrides):
    values = dict(
        name="B", message="M", enabled=True, dismissible=True, persist_dismissal=True,
        placement="top", style="info", icon="info", sort_order=0,
    )
    values.update(overrides)
    return SimpleNamespace(**values)


class TestApplyBannerUpdate:
    """EliteaUI re-shows a closed banner only when `updated_at` changes (see apply_banner_update)."""

    @pytest.mark.parametrize("field, value", [
        ("message", "New text"),
        ("dismissible", False),
        ("persist_dismissal", False),
        ("placement", "center"),
        ("style", "warning"),
        ("icon", "warning"),
    ])
    def test_display_change_requires_version_bump(self, banners_module, field, value):
        banner = _stored_banner()
        update = banners_module.BannerUpdateModel(**{field: value})
        assert banners_module.apply_banner_update(banner, update) is True
        assert getattr(banner, field) == value

    @pytest.mark.parametrize("field, value", [
        ("name", "Renamed"),
        ("enabled", False),
        ("sort_order", 5),
    ])
    def test_non_display_change_keeps_version(self, banners_module, field, value):
        banner = _stored_banner()
        update = banners_module.BannerUpdateModel(**{field: value})
        assert banners_module.apply_banner_update(banner, update) is False
        assert getattr(banner, field) == value

    def test_resaving_same_values_keeps_version(self, banners_module):
        banner = _stored_banner()
        update = banners_module.BannerUpdateModel(message="M", placement="top", style="info")
        assert banners_module.apply_banner_update(banner, update) is False

    def test_omitted_fields_untouched(self, banners_module):
        banner = _stored_banner(message="Keep")
        banners_module.apply_banner_update(banner, banners_module.BannerUpdateModel(sort_order=2))
        assert banner.message == "Keep"
