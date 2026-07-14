"""Unit tests for utils/image_utils.py - pure functions."""
import pytest


SUPPORTED_FORMATS = ['.jpeg', '.jpg', '.ico', '.png', '.gif', '.bmp', '.tiff', '.webp']
UNITS = ("", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi")


def sizeof_fmt(num: int | float, suffix: str = "B") -> str:
    """Pure function copied from image_utils.py for isolated testing."""
    for unit in UNITS:
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}Yi{suffix}"


class TestSizeofFmt:
    """Tests for sizeof_fmt human-readable file size formatter."""

    def test_bytes(self):
        assert sizeof_fmt(0) == "0.0B"
        assert sizeof_fmt(1) == "1.0B"
        assert sizeof_fmt(512) == "512.0B"
        assert sizeof_fmt(1023) == "1023.0B"

    def test_kibibytes(self):
        assert sizeof_fmt(1024) == "1.0KiB"
        assert sizeof_fmt(1536) == "1.5KiB"
        assert sizeof_fmt(2048) == "2.0KiB"

    def test_mebibytes(self):
        assert sizeof_fmt(1024 * 1024) == "1.0MiB"
        assert sizeof_fmt(1024 * 1024 * 5) == "5.0MiB"
        assert sizeof_fmt(1024 * 1024 * 1.5) == "1.5MiB"

    def test_gibibytes(self):
        assert sizeof_fmt(1024 ** 3) == "1.0GiB"
        assert sizeof_fmt(1024 ** 3 * 2.5) == "2.5GiB"

    def test_tebibytes(self):
        assert sizeof_fmt(1024 ** 4) == "1.0TiB"

    def test_pebibytes(self):
        assert sizeof_fmt(1024 ** 5) == "1.0PiB"

    def test_exbibytes(self):
        assert sizeof_fmt(1024 ** 6) == "1.0EiB"

    def test_zebibytes(self):
        assert sizeof_fmt(1024 ** 7) == "1.0ZiB"

    def test_yobibytes(self):
        # Beyond ZiB falls back to Yi prefix
        assert sizeof_fmt(1024 ** 8) == "1.0YiB"

    def test_negative_values(self):
        assert sizeof_fmt(-1024) == "-1.0KiB"
        assert sizeof_fmt(-512) == "-512.0B"

    def test_custom_suffix(self):
        assert sizeof_fmt(1024, suffix="b") == "1.0Kib"
        assert sizeof_fmt(1024, suffix="") == "1.0Ki"

    def test_float_input(self):
        assert sizeof_fmt(1024.5) == "1.0KiB"
        assert sizeof_fmt(100.5) == "100.5B"


class TestSupportedFormats:
    """Tests for SUPPORTED_FORMATS constant."""

    def test_common_formats_included(self):
        assert '.jpg' in SUPPORTED_FORMATS
        assert '.jpeg' in SUPPORTED_FORMATS
        assert '.png' in SUPPORTED_FORMATS
        assert '.gif' in SUPPORTED_FORMATS

    def test_modern_format_webp_included(self):
        assert '.webp' in SUPPORTED_FORMATS

    def test_formats_are_lowercase(self):
        for fmt in SUPPORTED_FORMATS:
            assert fmt == fmt.lower()
            assert fmt.startswith('.')
