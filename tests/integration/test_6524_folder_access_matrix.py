"""Issue #6524 - folder-level permission matrix, against real SQL.

Every assertion here is a security boundary: a wrong answer either hides an entity a
member is entitled to or hands out one they are not. The suite runs the real models and
the real RPC bodies (see stubs/folder_env.py) because the enforcement lives in the SQL
those bodies emit, not in logic that could be restated in a test.

Run via:
    python3 tests/run_tests.py integration/test_6524_folder_access_matrix.py -v
"""

import pytest

from stubs.folder_env import seed_entity, seed_folder, seed_item, seed_override


READER = 7
OTHER = 8
ADMIN = 1


# --- resolve_folder_access -------------------------------------------------

class TestResolveFolderAccess:
    def test_no_override_is_full(self, env):
        folder_id = seed_folder(env, 1, 'Alpha', 'agent')
        with env.request(READER):
            assert env.module.resolve_folder_access(1, folder_id) == 'full'

    def test_read_only_override(self, env):
        folder_id = seed_folder(env, 1, 'Alpha', 'agent')
        seed_override(env, 1, folder_id, READER, 'read_only')
        with env.request(READER):
            assert env.module.resolve_folder_access(1, folder_id) == 'read_only'

    def test_no_access_override(self, env):
        folder_id = seed_folder(env, 1, 'Alpha', 'agent')
        seed_override(env, 1, folder_id, READER, 'no_access')
        with env.request(READER):
            assert env.module.resolve_folder_access(1, folder_id) == 'no_access'

    def test_override_is_per_user(self, env):
        folder_id = seed_folder(env, 1, 'Alpha', 'agent')
        seed_override(env, 1, folder_id, READER, 'no_access')
        with env.request(OTHER):
            assert env.module.resolve_folder_access(1, folder_id) == 'full'

    def test_no_user_context_is_full(self, env):
        """Background callers (indexer, celery, schedulers) have no flask.g.auth."""
        folder_id = seed_folder(env, 1, 'Alpha', 'agent')
        seed_override(env, 1, folder_id, READER, 'no_access')
        assert env.module.resolve_folder_access(1, folder_id) == 'full'

    def test_explicit_user_id_works_without_request(self, env):
        folder_id = seed_folder(env, 1, 'Alpha', 'agent')
        seed_override(env, 1, folder_id, READER, 'no_access')
        assert env.module.resolve_folder_access(1, folder_id, user_id=READER) == 'no_access'

    def test_non_team_project_is_full(self, env):
        folder_id = seed_folder(env, 1, 'Alpha', 'agent')
        seed_override(env, 1, folder_id, READER, 'no_access')
        env.team_project(False)
        with env.request(READER):
            assert env.module.resolve_folder_access(1, folder_id) == 'full'

    def test_absent_projects_plugin_assumes_team(self, env):
        """queue.Empty means the plugin is not installed; the exception must still apply."""
        folder_id = seed_folder(env, 1, 'Alpha', 'agent')
        seed_override(env, 1, folder_id, READER, 'no_access')
        env.unregister_rpc('projects_is_team_project')
        with env.request(READER):
            assert env.module.resolve_folder_access(1, folder_id) == 'no_access'

    def test_falsy_folder_id_is_full(self, env):
        with env.request(READER):
            assert env.module.resolve_folder_access(1, None) == 'full'


# --- assert_folder_access -------------------------------------------------

class TestAssertFolderAccess:
    @pytest.mark.parametrize('level,read,write', [
        (None, True, True),
        ('read_only', True, False),
        ('no_access', False, False),
    ])
    def test_matrix(self, env, level, read, write):
        folder_id = seed_folder(env, 1, 'Alpha', 'agent')
        if level:
            seed_override(env, 1, folder_id, READER, level)
        with env.request(READER):
            assert env.module.assert_folder_access(1, folder_id) is read
            assert env.module.assert_folder_access(1, folder_id, write=True) is write


# --- get_restricted_folder_ids -------------------------------------------

class TestRestrictedFolderIds:
    def test_defaults_to_no_access_only(self, env):
        hidden = seed_folder(env, 1, 'Hidden', 'agent')
        ro = seed_folder(env, 1, 'ReadOnly', 'agent')
        seed_override(env, 1, hidden, READER, 'no_access')
        seed_override(env, 1, ro, READER, 'read_only')
        with env.request(READER):
            assert env.module.get_restricted_folder_ids(1, 'agent') == [hidden]

    def test_levels_argument_selects_read_only(self, env):
        hidden = seed_folder(env, 1, 'Hidden', 'agent')
        ro = seed_folder(env, 1, 'ReadOnly', 'agent')
        seed_override(env, 1, hidden, READER, 'no_access')
        seed_override(env, 1, ro, READER, 'read_only')
        with env.request(READER):
            assert env.module.get_restricted_folder_ids(
                1, 'agent', levels=['read_only']
            ) == [ro]

    def test_scoped_to_entity_type(self, env):
        agents = seed_folder(env, 1, 'Agents', 'agent')
        toolkits = seed_folder(env, 1, 'Toolkits', 'toolkit')
        seed_override(env, 1, agents, READER, 'no_access')
        seed_override(env, 1, toolkits, READER, 'no_access')
        with env.request(READER):
            assert env.module.get_restricted_folder_ids(1, 'agent') == [agents]
            assert env.module.get_restricted_folder_ids(1, 'toolkit') == [toolkits]

    def test_entity_type_list_covers_mixed_listings(self, env):
        agents = seed_folder(env, 1, 'Agents', 'agent')
        pipelines = seed_folder(env, 1, 'Pipelines', 'pipeline')
        seed_override(env, 1, agents, READER, 'no_access')
        seed_override(env, 1, pipelines, READER, 'no_access')
        with env.request(READER):
            got = env.module.get_restricted_folder_ids(1, ['agent', 'pipeline'])
        assert sorted(got) == sorted([agents, pipelines])

    def test_no_entity_type_returns_every_restricted_folder(self, env):
        agents = seed_folder(env, 1, 'Agents', 'agent')
        toolkits = seed_folder(env, 1, 'Toolkits', 'toolkit')
        seed_override(env, 1, agents, READER, 'no_access')
        seed_override(env, 1, toolkits, READER, 'no_access')
        with env.request(READER):
            assert sorted(env.module.get_restricted_folder_ids(1)) == sorted([agents, toolkits])

    def test_no_user_returns_empty(self, env):
        folder_id = seed_folder(env, 1, 'Hidden', 'agent')
        seed_override(env, 1, folder_id, READER, 'no_access')
        assert env.module.get_restricted_folder_ids(1, 'agent') == []


# --- folder_exclusion_clause ---------------------------------------------

class TestExclusionClause:
    def test_none_when_nothing_restricted(self, env):
        seed_folder(env, 1, 'Alpha', 'agent')
        with env.request(READER):
            clause = env.module.folder_exclusion_clause(
                1, 'agent', env.models.FolderItem.entity_id
            )
        assert clause is None

    def test_filters_entities_inside_restricted_folder(self, env):
        hidden = seed_folder(env, 1, 'Hidden', 'agent')
        visible = seed_folder(env, 1, 'Visible', 'agent')
        for entity_id in (10, 11, 12):
            seed_entity(env, 1, entity_id)
        seed_item(env, 1, hidden, 'agent', 10)
        seed_item(env, 1, visible, 'agent', 11)
        seed_override(env, 1, hidden, READER, 'no_access')

        EntityRow = env.models.EntityRow
        with env.request(READER):
            clause = env.module.folder_exclusion_clause(1, 'agent', EntityRow.id)
            with env.session(1) as session:
                rows = session.query(EntityRow.id).filter(clause).order_by(EntityRow.id).all()
        # 11 is in a folder without an exception, 12 is in no folder at all
        assert [r[0] for r in rows] == [11, 12]

    def test_count_is_computed_over_visible_rows_only(self, env):
        """The clause must be applied before count/limit or the page total lies."""
        hidden = seed_folder(env, 1, 'Hidden', 'agent')
        for entity_id in (10, 11, 12):
            seed_entity(env, 1, entity_id)
        seed_item(env, 1, hidden, 'agent', 10)
        seed_override(env, 1, hidden, READER, 'no_access')

        EntityRow = env.models.EntityRow
        with env.request(READER):
            clause = env.module.folder_exclusion_clause(1, 'agent', EntityRow.id)
            with env.session(1) as session:
                total = session.query(EntityRow).filter(clause).count()
        assert total == 2

    def test_clause_ignores_other_entity_types(self, env):
        """An id colliding across tables must not be hidden by another type's folder."""
        hidden = seed_folder(env, 1, 'Hidden', 'agent')
        toolkits = seed_folder(env, 1, 'Toolkits', 'toolkit')
        seed_item(env, 1, hidden, 'agent', 10)
        seed_item(env, 1, toolkits, 'toolkit', 10)
        seed_override(env, 1, hidden, READER, 'no_access')

        with env.request(READER):
            clause = env.module.folder_exclusion_clause(
                1, 'toolkit', env.models.EntityRow.id
            )
        assert clause is None

    def test_mixed_type_listing_hides_both_kinds(self, env):
        agents = seed_folder(env, 1, 'Agents', 'agent')
        pipelines = seed_folder(env, 1, 'Pipelines', 'pipeline')
        for entity_id in (10, 11, 12):
            seed_entity(env, 1, entity_id)
        seed_item(env, 1, agents, 'agent', 10)
        seed_item(env, 1, pipelines, 'pipeline', 11)
        seed_override(env, 1, agents, READER, 'no_access')
        seed_override(env, 1, pipelines, READER, 'no_access')

        EntityRow = env.models.EntityRow
        with env.request(READER):
            clause = env.module.folder_exclusion_clause(
                1, ['agent', 'pipeline'], EntityRow.id
            )
            with env.session(1) as session:
                rows = session.query(EntityRow.id).filter(clause).all()
        assert [r[0] for r in rows] == [12]


# --- filter_restricted_entity_ids ----------------------------------------

class TestFilterRestrictedIds:
    def test_drops_hidden_ids_keeps_order(self, env):
        hidden = seed_folder(env, 1, 'Hidden', 'agent')
        seed_item(env, 1, hidden, 'agent', 11)
        seed_override(env, 1, hidden, READER, 'no_access')
        with env.request(READER):
            assert env.module.filter_restricted_entity_ids(
                1, 'agent', [10, 11, 12]
            ) == [10, 12]

    def test_empty_input(self, env):
        with env.request(READER):
            assert env.module.filter_restricted_entity_ids(1, 'agent', []) == []

    def test_passthrough_when_nothing_restricted(self, env):
        with env.request(READER):
            assert env.module.filter_restricted_entity_ids(
                1, 'agent', [10, 11]
            ) == [10, 11]


# --- resolve_entity_access / bulk ----------------------------------------

class TestResolveEntityAccess:
    def test_entity_in_no_folder_is_full(self, env):
        with env.request(READER):
            assert env.module.resolve_entity_access(1, 'agent', 10) == 'full'

    @pytest.mark.parametrize('level', ['read_only', 'no_access'])
    def test_inherits_folder_level(self, env, level):
        folder_id = seed_folder(env, 1, 'Alpha', 'agent')
        seed_item(env, 1, folder_id, 'agent', 10)
        seed_override(env, 1, folder_id, READER, level)
        with env.request(READER):
            assert env.module.resolve_entity_access(1, 'agent', 10) == level

    def test_entity_type_list_resolves_either_type(self, env):
        folder_id = seed_folder(env, 1, 'Pipelines', 'pipeline')
        seed_item(env, 1, folder_id, 'pipeline', 10)
        seed_override(env, 1, folder_id, READER, 'no_access')
        with env.request(READER):
            assert env.module.resolve_entity_access(
                1, ['agent', 'pipeline'], 10
            ) == 'no_access'

    def test_wrong_entity_type_does_not_match(self, env):
        folder_id = seed_folder(env, 1, 'Pipelines', 'pipeline')
        seed_item(env, 1, folder_id, 'pipeline', 10)
        seed_override(env, 1, folder_id, READER, 'no_access')
        with env.request(READER):
            assert env.module.resolve_entity_access(1, 'toolkit', 10) == 'full'

    def test_bulk_returns_restricted_only(self, env):
        hidden = seed_folder(env, 1, 'Hidden', 'agent')
        ro = seed_folder(env, 1, 'ReadOnly', 'agent')
        seed_item(env, 1, hidden, 'agent', 10)
        seed_item(env, 1, ro, 'agent', 11)
        seed_override(env, 1, hidden, READER, 'no_access')
        seed_override(env, 1, ro, READER, 'read_only')
        with env.request(READER):
            got = env.module.resolve_entities_access_bulk(1, 'agent', [10, 11, 12])
        assert got == {10: 'no_access', 11: 'read_only'}

    def test_bulk_empty_without_user(self, env):
        folder_id = seed_folder(env, 1, 'Hidden', 'agent')
        seed_item(env, 1, folder_id, 'agent', 10)
        seed_override(env, 1, folder_id, READER, 'no_access')
        assert env.module.resolve_entities_access_bulk(1, 'agent', [10]) == {}


# --- folder listing / write path -----------------------------------------

class TestFolderListingAndWrites:
    def test_get_folders_hides_no_access_and_marks_read_only(self, env):
        hidden = seed_folder(env, 1, 'Hidden', 'agent')
        ro = seed_folder(env, 1, 'ReadOnly', 'agent')
        seed_folder(env, 1, 'Open', 'agent')
        seed_override(env, 1, hidden, READER, 'no_access')
        seed_override(env, 1, ro, READER, 'read_only')

        with env.request(READER):
            folders = env.module.get_folders(1, 'agent')
        by_name = {f['name']: f for f in folders}
        assert set(by_name) == {'Open', 'ReadOnly'}
        assert by_name['ReadOnly']['access_level'] == 'read_only'
        assert by_name['Open']['access_level'] == 'full'

    def test_get_folder_returns_none_on_no_access(self, env):
        folder_id = seed_folder(env, 1, 'Hidden', 'agent')
        seed_override(env, 1, folder_id, READER, 'no_access')
        with env.request(READER):
            assert env.module.get_folder(1, folder_id) is None

    def test_write_denied_for_read_only(self, env):
        folder_id = seed_folder(env, 1, 'ReadOnly', 'agent')
        seed_override(env, 1, folder_id, READER, 'read_only')
        with env.request(READER):
            result = env.module.update_folder(1, folder_id, name='Renamed')
        assert result['ok'] is False
        assert 'read-only' in result['error']

    def test_write_denied_for_no_access_is_not_found(self, env):
        """The error must not distinguish 'restricted' from 'nonexistent'."""
        folder_id = seed_folder(env, 1, 'Hidden', 'agent')
        seed_override(env, 1, folder_id, READER, 'no_access')
        with env.request(READER):
            result = env.module.delete_folder(1, folder_id)
        assert result['ok'] is False
        assert 'permission' in result['error']

    def test_delete_folder_removes_items_and_overrides(self, env):
        folder_id = seed_folder(env, 1, 'Alpha', 'agent')
        seed_item(env, 1, folder_id, 'agent', 10)
        seed_override(env, 1, folder_id, READER, 'read_only')
        with env.request(ADMIN):
            assert env.module.delete_folder(1, folder_id)['ok'] is True
        with env.session(1) as session:
            assert session.query(env.models.FolderItem).count() == 0
            assert session.query(env.models.FolderAccessOverride).count() == 0
            assert session.query(env.models.EntityFolder).count() == 0


# --- management RPCs ------------------------------------------------------

class TestSetFolderAccess:
    def test_upserts_and_replaces(self, env):
        folder_id = seed_folder(env, 1, 'Alpha', 'agent')
        env.members(READER, OTHER, ADMIN)
        with env.request(ADMIN):
            first = env.module.set_folder_access(
                1, folder_id, [{'user_id': READER, 'access_level': 'read_only'}]
            )
            assert first == {'ok': True, 'folder_id': folder_id, 'updated': 1}
            assert env.module.resolve_folder_access(1, folder_id, READER) == 'read_only'

            env.module.set_folder_access(
                1, folder_id, [{'user_id': READER, 'access_level': 'no_access'}]
            )
        with env.session(1) as session:
            rows = session.query(env.models.FolderAccessOverride).all()
        assert len(rows) == 1
        assert rows[0].access_level == 'no_access'
        assert rows[0].created_by == ADMIN

    def test_rejects_non_members(self, env):
        folder_id = seed_folder(env, 1, 'Alpha', 'agent')
        env.members(ADMIN)
        with env.request(ADMIN):
            result = env.module.set_folder_access(
                1, folder_id, [{'user_id': 999, 'access_level': 'no_access'}]
            )
        assert result['ok'] is False
        assert '999' in result['error']
        with env.session(1) as session:
            assert session.query(env.models.FolderAccessOverride).count() == 0

    def test_fails_closed_when_membership_unavailable(self, env):
        folder_id = seed_folder(env, 1, 'Alpha', 'agent')
        env.unregister_rpc('admin_get_users_ids_in_project')
        with env.request(ADMIN):
            result = env.module.set_folder_access(
                1, folder_id, [{'user_id': READER, 'access_level': 'no_access'}]
            )
        assert result['ok'] is False
        assert 'membership' in result['error']

    def test_rejects_non_team_project(self, env):
        folder_id = seed_folder(env, 1, 'Alpha', 'agent')
        env.team_project(False)
        env.members(READER, ADMIN)
        with env.request(ADMIN):
            result = env.module.set_folder_access(
                1, folder_id, [{'user_id': READER, 'access_level': 'no_access'}]
            )
        assert result['ok'] is False
        assert 'Team' in result['error']

    def test_rejects_read_write_level(self, env):
        """read_write is the RBAC default; it is expressed by removing the row."""
        folder_id = seed_folder(env, 1, 'Alpha', 'agent')
        env.members(READER, ADMIN)
        with env.request(ADMIN):
            result = env.module.set_folder_access(
                1, folder_id, [{'user_id': READER, 'access_level': 'read_write'}]
            )
        assert result['ok'] is False

    def test_unknown_folder(self, env):
        env.members(READER, ADMIN)
        with env.request(ADMIN):
            result = env.module.set_folder_access(
                1, 4242, [{'user_id': READER, 'access_level': 'no_access'}]
            )
        assert result == {'ok': False, 'error': 'Folder not found'}

    def test_fires_audit_event(self, env):
        folder_id = seed_folder(env, 1, 'Alpha', 'agent')
        env.members(READER, ADMIN)
        with env.request(ADMIN):
            env.module.set_folder_access(
                1, folder_id, [{'user_id': READER, 'access_level': 'no_access'}]
            )
        names = [name for name, _ in env.context.event_manager.fired]
        assert 'folder_access_override_set' in names


class TestRemoveAndPurge:
    def test_remove_restores_default(self, env):
        folder_id = seed_folder(env, 1, 'Alpha', 'agent')
        seed_override(env, 1, folder_id, READER, 'no_access')
        with env.request(ADMIN):
            result = env.module.remove_folder_access(1, folder_id, [READER])
            assert result['deleted'] == 1
            assert env.module.resolve_folder_access(1, folder_id, READER) == 'full'
        names = [name for name, _ in env.context.event_manager.fired]
        assert 'folder_access_override_removed' in names

    def test_purge_clears_every_folder_for_user(self, env):
        first = seed_folder(env, 1, 'Alpha', 'agent')
        second = seed_folder(env, 1, 'Beta', 'toolkit')
        seed_override(env, 1, first, READER, 'no_access')
        seed_override(env, 1, second, READER, 'read_only')
        seed_override(env, 1, first, OTHER, 'no_access')

        assert env.module.purge_user_folder_access(1, [READER])['deleted'] == 2
        with env.session(1) as session:
            remaining = session.query(env.models.FolderAccessOverride).all()
        assert [r.user_id for r in remaining] == [OTHER]

    def test_purge_noop_without_users(self, env):
        assert env.module.purge_user_folder_access(1, []) == {'ok': True, 'deleted': 0}


class TestListFolderAccess:
    def test_lists_overrides(self, env):
        folder_id = seed_folder(env, 1, 'Alpha', 'agent')
        seed_override(env, 1, folder_id, OTHER, 'read_only')
        seed_override(env, 1, folder_id, READER, 'no_access')
        result = env.module.list_folder_access(1, folder_id)
        assert result['ok'] is True
        assert result['total'] == 2
        assert [o['user_id'] for o in result['overrides']] == [READER, OTHER]

    def test_unknown_folder(self, env):
        assert env.module.list_folder_access(1, 4242) == {
            'ok': False, 'error': 'Folder not found'
        }


# --- tenant isolation -----------------------------------------------------

class TestTenantIsolation:
    def test_override_does_not_leak_across_projects(self, env):
        folder_one = seed_folder(env, 1, 'Alpha', 'agent')
        seed_override(env, 1, folder_one, READER, 'no_access')
        folder_two = seed_folder(env, 2, 'Alpha', 'agent')
        with env.request(READER):
            assert env.module.resolve_folder_access(1, folder_one) == 'no_access'
            assert env.module.resolve_folder_access(2, folder_two) == 'full'
            assert env.module.get_restricted_folder_ids(2, 'agent') == []
