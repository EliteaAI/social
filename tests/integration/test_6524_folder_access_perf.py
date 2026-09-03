"""Issue #6524 - the cost side of folder permissions.

The entity pages are the hot path: every listing calls into this resolver, so the
guarantees below are the ones that keep the feature from taxing projects that never use
it. They are asserted by counting the SQL actually issued through the engine.

Run via:
    python3 tests/run_tests.py integration/test_6524_folder_access_perf.py -v
"""

from stubs.folder_env import seed_entity, seed_folder, seed_item, seed_override


READER = 7
ADMIN = 1


def _selects(statements):
    return [s for s in statements if s.lstrip().upper().startswith('SELECT')]


class TestZeroOverrideFastPath:
    def test_clause_is_none_and_costs_one_lookup(self, env):
        """A project with no exceptions must not pay for a subquery at all."""
        seed_folder(env, 1, 'Alpha', 'agent')
        with env.request(READER):
            env.statements.clear()
            clause = env.module.folder_exclusion_clause(
                1, 'agent', env.models.EntityRow.id
            )
        assert clause is None
        assert len(_selects(env.statements)) == 1

    def test_listing_query_gains_no_subquery(self, env):
        for entity_id in (10, 11):
            seed_entity(env, 1, entity_id)
        with env.request(READER):
            clause = env.module.folder_exclusion_clause(
                1, 'agent', env.models.EntityRow.id
            )
            with env.session(1) as session:
                query = session.query(env.models.EntityRow.id)
                if clause is not None:
                    query = query.filter(clause)
                env.statements.clear()
                query.all()
        assert 'EXISTS' not in env.statements[-1].upper()

    def test_no_user_context_short_circuits_before_sql(self, env):
        folder_id = seed_folder(env, 1, 'Hidden', 'agent')
        seed_override(env, 1, folder_id, READER, 'no_access')
        env.statements.clear()
        assert env.module.get_restricted_folder_ids(1, 'agent') == []
        assert _selects(env.statements) == []

    def test_non_team_project_short_circuits_before_sql(self, env):
        folder_id = seed_folder(env, 1, 'Hidden', 'agent')
        seed_override(env, 1, folder_id, READER, 'no_access')
        env.team_project(False)
        with env.request(READER):
            env.statements.clear()
            assert env.module.get_restricted_folder_ids(1, 'agent') == []
        assert _selects(env.statements) == []


class TestRequestMemo:
    def test_restricted_ids_queried_once_per_request(self, env):
        folder_id = seed_folder(env, 1, 'Hidden', 'agent')
        seed_override(env, 1, folder_id, READER, 'no_access')
        with env.request(READER):
            env.statements.clear()
            for _ in range(5):
                assert env.module.get_restricted_folder_ids(1, 'agent') == [folder_id]
        assert len(_selects(env.statements)) == 1

    def test_memo_does_not_survive_the_request(self, env):
        folder_id = seed_folder(env, 1, 'Hidden', 'agent')
        seed_override(env, 1, folder_id, READER, 'no_access')
        env.statements.clear()
        for _ in range(2):
            with env.request(READER):
                env.module.get_restricted_folder_ids(1, 'agent')
        assert len(_selects(env.statements)) == 2

    def test_no_memo_outside_a_request(self, env):
        """Background callers must not accumulate state on a missing flask.g."""
        folder_id = seed_folder(env, 1, 'Hidden', 'agent')
        seed_override(env, 1, folder_id, READER, 'no_access')
        env.statements.clear()
        for _ in range(3):
            env.module.get_restricted_folder_ids(1, 'agent', user_id=READER)
        assert len(_selects(env.statements)) == 3

    def test_folder_level_memoized_per_folder(self, env):
        folder_id = seed_folder(env, 1, 'Alpha', 'agent')
        seed_override(env, 1, folder_id, READER, 'read_only')
        with env.request(READER):
            env.statements.clear()
            for _ in range(4):
                assert env.module.resolve_folder_access(1, folder_id) == 'read_only'
        assert len(_selects(env.statements)) == 1

    def test_entity_level_memoized_for_list_entity_types(self, env):
        """The mixed agent/pipeline key must be hashable *and* hit the memo."""
        folder_id = seed_folder(env, 1, 'Pipelines', 'pipeline')
        seed_item(env, 1, folder_id, 'pipeline', 10)
        seed_override(env, 1, folder_id, READER, 'no_access')
        with env.request(READER):
            env.statements.clear()
            for _ in range(3):
                assert env.module.resolve_entity_access(
                    1, ['agent', 'pipeline'], 10
                ) == 'no_access'
        assert len(_selects(env.statements)) == 1

    def test_project_kind_rpc_called_once_per_request(self, env):
        folder_id = seed_folder(env, 1, 'Alpha', 'agent')
        with env.request(READER):
            for _ in range(4):
                env.module.resolve_folder_access(1, folder_id)
        kind_calls = [c for c in env.context.rpc_manager.calls
                      if c[0] == 'projects_is_team_project']
        assert len(kind_calls) == 1


class TestNoNPlusOne:
    def test_get_folders_counts_in_one_aggregate(self, env):
        folder_ids = [seed_folder(env, 1, f'F{i}', 'agent') for i in range(12)]
        for i, folder_id in enumerate(folder_ids):
            seed_item(env, 1, folder_id, 'agent', 100 + i)

        with env.request(READER):
            env.statements.clear()
            folders = env.module.get_folders(1, 'agent', include_counts=True)

        assert len(folders) == 12
        assert all(f['entities_count'] == 1 for f in folders)
        counts = [s for s in env.statements if 'count(' in s.lower()]
        assert len(counts) == 1
        assert len(_selects(env.statements)) == 4  # 2 restricted lookups + folders + counts

    def test_get_folders_cost_is_flat_in_folder_count(self, env):
        def cost(folder_total):
            env.truncate()
            for i in range(folder_total):
                seed_folder(env, 1, f'F{i}', 'agent')
            with env.request(READER):
                env.statements.clear()
                env.module.get_folders(1, 'agent', include_counts=True)
                return len(_selects(env.statements))

        assert cost(3) == cost(30)

    def test_bulk_access_is_one_query(self, env):
        folder_id = seed_folder(env, 1, 'Hidden', 'agent')
        entity_ids = list(range(100, 150))
        for entity_id in entity_ids:
            seed_item(env, 1, folder_id, 'agent', entity_id)
        seed_override(env, 1, folder_id, READER, 'no_access')

        with env.request(READER):
            env.statements.clear()
            result = env.module.resolve_entities_access_bulk(1, 'agent', entity_ids)
        assert len(result) == 50
        assert len(_selects(env.statements)) == 1

    def test_filter_restricted_ids_is_one_query(self, env):
        folder_id = seed_folder(env, 1, 'Hidden', 'agent')
        for entity_id in range(100, 140):
            seed_item(env, 1, folder_id, 'agent', entity_id)
        seed_override(env, 1, folder_id, READER, 'no_access')

        with env.request(READER):
            env.module.get_restricted_folder_ids(1, 'agent')  # warm the memo
            env.statements.clear()
            visible = env.module.filter_restricted_entity_ids(
                1, 'agent', list(range(100, 160))
            )
        assert visible == list(range(140, 160))
        assert len(_selects(env.statements)) == 1
