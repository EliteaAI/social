"""Pytest configuration - auto-mark tests based on directory."""
import pathlib
import sys

import pytest

PLUGIN_ROOT = pathlib.Path(__file__).resolve().parent.parent
TESTS_DIR = pathlib.Path(__file__).resolve().parent

# `--import-mode=importlib` does not put the tests dir on sys.path, so `stubs.*` /
# `fixtures.*` would only import when run through run_tests.py.
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))


@pytest.fixture(scope="session")
def plugin_root() -> pathlib.Path:
    """Absolute path to the social plugin root."""
    return PLUGIN_ROOT


@pytest.fixture(scope="session")
def models_path(plugin_root: pathlib.Path) -> pathlib.Path:
    """Path to the models/ directory."""
    return plugin_root / "models"


@pytest.fixture(scope="session")
def utils_path(plugin_root: pathlib.Path) -> pathlib.Path:
    """Path to the utils/ directory."""
    return plugin_root / "utils"


def pytest_collection_modifyitems(items):
    for item in items:
        if '/unit/' in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        elif '/integration/' in str(item.fspath):
            item.add_marker(pytest.mark.integration)
