"""Shared environment for the folder-permission suites (#6524)."""
import pytest

from stubs.folder_env import get_env


@pytest.fixture(scope='session')
def env():
    return get_env()


@pytest.fixture(autouse=True)
def _clean_env(env):
    """Every test starts from an empty tenant and a bare RPC bus."""
    env.truncate()
    env.context.rpc_manager.registry.clear()
    env.context.rpc_manager.calls.clear()
    env.context.event_manager.fired.clear()
    env.statements.clear()
    env.current_user_id = None
    env.team_project(True)
    yield
