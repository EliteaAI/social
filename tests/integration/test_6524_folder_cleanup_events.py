"""Issue #6524 - deletion and membership cleanup (plan phase 4).

Folder items and access exceptions outlive the entity or the membership that justified
them, so a re-created id or a re-invited user would silently inherit stale rows. These
handlers are also on the deletion path of other plugins: they must never turn a
successful delete into a failed one, so every one of them is fail-open.

Run via:
    python3 tests/run_tests.py integration/test_6524_folder_cleanup_events.py -v
"""

import pytest

from stubs.folder_env import seed_folder, seed_item, seed_override


READER = 7


def _items(env, project_id=1):
    with env.session(project_id) as session:
        return {
            (row.entity, row.entity_id)
            for row in session.query(env.models.FolderItem).all()
        }


def _overrides(env, project_id=1):
    with env.session(project_id) as session:
        return {
            (row.folder_id, row.user_id)
            for row in session.query(env.models.FolderAccessOverride).all()
        }


class TestApplicationDeleted:
    def test_clears_an_agent_item(self, env):
        folder_id = seed_folder(env, 1, 'Agents', 'agent')
        seed_item(env, 1, folder_id, 'agent', 10)
        env.module.on_application_deleted(
            env.context, 'application_deleted', {'project_id': 1, 'id': 10}
        )
        assert _items(env) == set()

    def test_clears_a_pipeline_without_version_details(self, env):
        """agent_type lives in version_details, which a version-less app does not have."""
        folder_id = seed_folder(env, 1, 'Pipelines', 'pipeline')
        seed_item(env, 1, folder_id, 'pipeline', 11)
        env.module.on_application_deleted(
            env.context, 'application_deleted', {'project_id': 1, 'id': 11}
        )
        assert _items(env) == set()

    def test_leaves_other_entity_types_alone(self, env):
        """Ids collide across tables, so only agent/pipeline rows may be cleared."""
        agents = seed_folder(env, 1, 'Agents', 'agent')
        toolkits = seed_folder(env, 1, 'Toolkits', 'toolkit')
        seed_item(env, 1, agents, 'agent', 10)
        seed_item(env, 1, toolkits, 'toolkit', 10)
        env.module.on_application_deleted(
            env.context, 'application_deleted', {'project_id': 1, 'id': 10}
        )
        assert _items(env) == {('toolkit', 10)}

    @pytest.mark.parametrize('payload', [
        {'id': 10},
        {'project_id': 1},
        {},
        {'project_id': 1, 'id': None},
    ])
    def test_incomplete_payload_is_a_no_op(self, env, payload):
        folder_id = seed_folder(env, 1, 'Agents', 'agent')
        seed_item(env, 1, folder_id, 'agent', 10)
        env.module.on_application_deleted(env.context, 'application_deleted', payload)
        assert _items(env) == {('agent', 10)}

    def test_failure_does_not_break_the_delete(self, env, monkeypatch):
        """The entity is already gone; raising here would only corrupt the caller."""
        def boom(**_kwargs):
            raise RuntimeError('db down')

        monkeypatch.setattr(env.module, 'remove_entity_from_folders', boom)
        env.module.on_application_deleted(
            env.context, 'application_deleted', {'project_id': 1, 'id': 10}
        )


class TestToolkitDeleted:
    def test_reads_project_id_from_owner_id(self, env):
        """The toolkit_deleted payload names the project 'owner_id', not 'project_id'."""
        folder_id = seed_folder(env, 1, 'Toolkits', 'toolkit')
        seed_item(env, 1, folder_id, 'toolkit', 20)
        env.module.on_toolkit_deleted(
            env.context, 'toolkit_deleted', {'owner_id': 1, 'id': 20}
        )
        assert _items(env) == set()

    def test_project_id_key_is_not_used(self, env):
        folder_id = seed_folder(env, 1, 'Toolkits', 'toolkit')
        seed_item(env, 1, folder_id, 'toolkit', 20)
        env.module.on_toolkit_deleted(
            env.context, 'toolkit_deleted', {'project_id': 1, 'id': 20}
        )
        assert _items(env) == {('toolkit', 20)}

    def test_clears_a_local_mcp_flagged_in_meta(self, env):
        """Local MCPs keep type='toolkit' and are flagged by meta.mcp, so both are cleared."""
        folder_id = seed_folder(env, 1, 'MCPs', 'mcp')
        seed_item(env, 1, folder_id, 'mcp', 21)
        env.module.on_toolkit_deleted(
            env.context, 'toolkit_deleted', {'owner_id': 1, 'id': 21}
        )
        assert _items(env) == set()

    def test_leaves_agents_alone(self, env):
        agents = seed_folder(env, 1, 'Agents', 'agent')
        toolkits = seed_folder(env, 1, 'Toolkits', 'toolkit')
        seed_item(env, 1, agents, 'agent', 20)
        seed_item(env, 1, toolkits, 'toolkit', 20)
        env.module.on_toolkit_deleted(
            env.context, 'toolkit_deleted', {'owner_id': 1, 'id': 20}
        )
        assert _items(env) == {('agent', 20)}

    def test_failure_does_not_break_the_delete(self, env, monkeypatch):
        def boom(**_kwargs):
            raise RuntimeError('db down')

        monkeypatch.setattr(env.module, 'remove_entity_from_folders', boom)
        env.module.on_toolkit_deleted(
            env.context, 'toolkit_deleted', {'owner_id': 1, 'id': 20}
        )


class TestSkillDeleted:
    def test_clears_the_skill_item(self, env):
        folder_id = seed_folder(env, 1, 'Skills', 'skill')
        seed_item(env, 1, folder_id, 'skill', 30)
        env.module.on_skill_deleted(
            env.context, 'skill_deleted', {'project_id': 1, 'id': 30, 'name': 'S'}
        )
        assert _items(env) == set()

    def test_does_not_touch_same_id_in_another_type(self, env):
        skills = seed_folder(env, 1, 'Skills', 'skill')
        agents = seed_folder(env, 1, 'Agents', 'agent')
        seed_item(env, 1, skills, 'skill', 30)
        seed_item(env, 1, agents, 'agent', 30)
        env.module.on_skill_deleted(
            env.context, 'skill_deleted', {'project_id': 1, 'id': 30}
        )
        assert _items(env) == {('agent', 30)}

    def test_failure_does_not_break_the_delete(self, env, monkeypatch):
        def boom(**_kwargs):
            raise RuntimeError('db down')

        monkeypatch.setattr(env.module, 'remove_entity_from_folders', boom)
        env.module.on_skill_deleted(
            env.context, 'skill_deleted', {'project_id': 1, 'id': 30}
        )


class TestConfigurationDeleted:
    @pytest.mark.parametrize('id_key', ['id', 'configuration_id'])
    def test_accepts_either_id_key(self, env, id_key):
        folder_id = seed_folder(env, 1, 'Configs', 'configuration')
        seed_item(env, 1, folder_id, 'configuration', 40)
        env.module.on_configuration_deleted(
            env.context, 'configuration_deleted', {'project_id': 1, id_key: 40}
        )
        assert _items(env) == set()

    def test_no_id_is_a_no_op(self, env):
        folder_id = seed_folder(env, 1, 'Configs', 'configuration')
        seed_item(env, 1, folder_id, 'configuration', 40)
        env.module.on_configuration_deleted(
            env.context, 'configuration_deleted', {'project_id': 1, 'name': 'c'}
        )
        assert _items(env) == {('configuration', 40)}

    def test_failure_does_not_break_the_delete(self, env, monkeypatch):
        def boom(**_kwargs):
            raise RuntimeError('db down')

        monkeypatch.setattr(env.module, 'remove_entity_from_folders', boom)
        env.module.on_configuration_deleted(
            env.context, 'configuration_deleted', {'project_id': 1, 'id': 40}
        )


class TestUserRemovedFromProject:
    def test_purges_every_exception_of_the_leaver(self, env):
        first = seed_folder(env, 1, 'Alpha', 'agent')
        second = seed_folder(env, 1, 'Beta', 'toolkit')
        seed_override(env, 1, first, READER, 'no_access')
        seed_override(env, 1, second, READER, 'read_only')
        seed_override(env, 1, first, 8, 'no_access')

        env.module.on_user_removed_from_project(
            env.context, 'user_removed_from_project',
            {'project_id': 1, 'user_ids': [READER]},
        )
        assert _overrides(env) == {(first, 8)}

    def test_reader_regains_access_after_the_purge(self, env):
        """The row must be gone, not merely hidden: a re-invite would re-apply it."""
        folder_id = seed_folder(env, 1, 'Alpha', 'agent')
        seed_override(env, 1, folder_id, READER, 'no_access')
        with env.request(READER):
            assert env.module.resolve_folder_access(1, folder_id) == 'no_access'

        env.module.on_user_removed_from_project(
            env.context, 'user_removed_from_project',
            {'project_id': 1, 'user_ids': [READER]},
        )
        with env.request(READER):
            assert env.module.resolve_folder_access(1, folder_id) == 'full'

    def test_string_user_ids_are_coerced(self, env):
        """Membership payloads carry ids as strings in some callers."""
        folder_id = seed_folder(env, 1, 'Alpha', 'agent')
        seed_override(env, 1, folder_id, READER, 'no_access')
        env.module.on_user_removed_from_project(
            env.context, 'user_removed_from_project',
            {'project_id': 1, 'user_ids': [str(READER)]},
        )
        assert _overrides(env) == set()

    @pytest.mark.parametrize('payload', [
        {'project_id': 1, 'user_ids': []},
        {'project_id': 1},
        {'user_ids': [READER]},
        {},
    ])
    def test_incomplete_payload_is_a_no_op(self, env, payload):
        folder_id = seed_folder(env, 1, 'Alpha', 'agent')
        seed_override(env, 1, folder_id, READER, 'no_access')
        env.module.on_user_removed_from_project(
            env.context, 'user_removed_from_project', payload
        )
        assert _overrides(env) == {(folder_id, READER)}

    def test_other_tenants_are_untouched(self, env):
        first = seed_folder(env, 1, 'Alpha', 'agent')
        second = seed_folder(env, 2, 'Alpha', 'agent')
        seed_override(env, 1, first, READER, 'no_access')
        seed_override(env, 2, second, READER, 'no_access')

        env.module.on_user_removed_from_project(
            env.context, 'user_removed_from_project',
            {'project_id': 1, 'user_ids': [READER]},
        )
        assert _overrides(env, 1) == set()
        assert _overrides(env, 2) == {(second, READER)}

    def test_failure_does_not_break_the_removal(self, env, monkeypatch):
        """The user is already out of the project; the stale rows can wait."""
        def boom(**_kwargs):
            raise RuntimeError('db down')

        monkeypatch.setattr(env.module, 'purge_user_folder_access', boom)
        env.module.on_user_removed_from_project(
            env.context, 'user_removed_from_project',
            {'project_id': 1, 'user_ids': [READER]},
        )
