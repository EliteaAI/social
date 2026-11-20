"""Issue #7383 - Elitea Builder module defaults.

The new defaults are the OR of the three old builder defaults, per column (Chats / Agents),
read from the stored per-project row first and the legacy global personalization second.
An explicitly stored new value always wins. Chats default to on when nothing was ever set (AC-5, shipped with S5);
Agents default to off (AC-6).
"""
import pathlib

import pytest

from fixtures.helpers import load_module_with_stubs

PLUGIN_ROOT = pathlib.Path(__file__).resolve().parents[2]

CHATS = 'default_elitea_builder_enabled'
AGENTS = 'default_agent_elitea_builder_enabled'


@pytest.fixture(scope='module')
def module_settings():
    return load_module_with_stubs(PLUGIN_ROOT / 'utils' / 'module_settings.py', 'social_module_settings_7383')


class TestResolveBuilderDefaults:

    def test_nothing_stored_is_chats_and_agents_on(self, module_settings):
        assert module_settings.resolve_builder_defaults({}, {}) == {CHATS: True, AGENTS: True}

    def test_old_chats_defaults_all_explicitly_off_stays_off(self, module_settings):
        stored = {'default_internal_mcp_enabled': False}
        assert module_settings.resolve_builder_defaults(stored, {})[CHATS] is False

    def test_user_turned_the_new_chats_default_off(self, module_settings):
        assert module_settings.resolve_builder_defaults({CHATS: False}, {})[CHATS] is False

    @pytest.mark.parametrize('old_key', [
        'default_internal_mcp_enabled',
        'default_skill_builder_enabled',
        'default_project_context_builder_enabled',
    ])
    def test_any_old_chats_default_turns_chats_on(self, module_settings, old_key):
        assert module_settings.resolve_builder_defaults({old_key: True}, {}) == {CHATS: True, AGENTS: True}

    @pytest.mark.parametrize('old_key', [
        'default_agent_internal_mcp_enabled',
        'default_agent_skill_builder_enabled',
        'default_agent_project_context_builder_enabled',
    ])
    def test_any_old_agents_default_turns_agents_on(self, module_settings, old_key):
        assert module_settings.resolve_builder_defaults({old_key: True}, {}) == {CHATS: True, AGENTS: True}

    def test_legacy_personalization_used_per_key(self, module_settings):
        stored = {'default_internal_mcp_enabled': False}
        legacy = {'default_project_context_builder_enabled': True}
        assert module_settings.resolve_builder_defaults(stored, legacy)[CHATS] is True

    def test_stored_old_false_beats_legacy_true(self, module_settings):
        stored = {'default_skill_builder_enabled': False}
        legacy = {'default_skill_builder_enabled': True}
        assert module_settings.resolve_builder_defaults(stored, legacy)[CHATS] is False

    def test_stored_new_value_wins(self, module_settings):
        stored = {CHATS: False, 'default_internal_mcp_enabled': True, AGENTS: True}
        assert module_settings.resolve_builder_defaults(stored, {}) == {CHATS: False, AGENTS: True}

    def test_legacy_new_value_used_when_not_stored(self, module_settings):
        assert module_settings.resolve_builder_defaults({}, {CHATS: True})[CHATS] is True


class TestMigrateModuleSettings:
    """Migration rewrite of one stored module_settings row."""

    def test_writes_new_keys_and_reports_change(self, module_settings):
        stored = {'default_agent_skill_builder_enabled': True, 'default_ask_user_enabled': True}
        new, changed = module_settings.migrate_module_settings(stored, {})
        assert changed is True
        assert new[CHATS] is True and new[AGENTS] is True
        assert new['default_ask_user_enabled'] is True
        assert new['default_agent_skill_builder_enabled'] is True  # old keys kept read-only for one release

    def test_already_migrated_is_unchanged(self, module_settings):
        stored = {CHATS: True, AGENTS: False, 'default_internal_mcp_enabled': False}
        new, changed = module_settings.migrate_module_settings(stored, {})
        assert changed is False
        assert new == stored


class TestResolveModuleDefaults:

    def test_ask_user_is_on_for_chats_when_never_set(self, module_settings):
        assert module_settings.resolve_module_defaults({}, {})['default_ask_user_enabled'] is True

    def test_ask_user_keeps_what_the_user_chose(self, module_settings):
        assert module_settings.resolve_module_defaults({'default_ask_user_enabled': False}, {})[
            'default_ask_user_enabled'] is False
        assert module_settings.resolve_module_defaults({}, {'default_ask_user_enabled': False})[
            'default_ask_user_enabled'] is False

    def test_agents_ask_user_is_on_when_never_set(self, module_settings):
        assert module_settings.resolve_module_defaults({}, {})['default_agent_ask_user_enabled'] is True

    def test_agents_keep_an_explicit_off(self, module_settings):
        stored = {AGENTS: False, 'default_agent_ask_user_enabled': False}
        resolved = module_settings.resolve_module_defaults(stored, {})
        assert resolved[AGENTS] is False and resolved['default_agent_ask_user_enabled'] is False

    def test_agents_keep_an_old_builder_off(self, module_settings):
        stored = {'default_agent_internal_mcp_enabled': False}
        assert module_settings.resolve_builder_defaults(stored, {})[AGENTS] is False
