"""Unit tests for per-persona personalization merge/hydrate logic (#5392, #6285, #6303).

These mirror api/v2/author.py::_merge_personalization and _hydrate_personalization. author.py
imports flask/tools at module load, so the pure logic is copied here (kept byte-identical to the
source) rather than importing the module. Guards the highest-severity rollout bug: a legacy-shaped
PUT must never wipe personas it didn't send.
"""
# Mirror of constants.py::PROJECT_SCOPED_SETTINGS_FIELDS — keep in sync.
_PROJECT_SCOPED_SETTINGS_FIELDS = (
    'default_internal_mcp_enabled',
    'default_skill_builder_enabled',
    'default_project_context_builder_enabled',
    'default_ask_user_enabled',
    'default_image_generation_enabled',
    'default_data_analysis_enabled',
    'default_planner_enabled',
    'default_pyodide_enabled',
    'default_swarm_enabled',
    'default_lazy_tools_mode_enabled',
    'default_agent_internal_mcp_enabled',
    'default_agent_skill_builder_enabled',
    'default_agent_project_context_builder_enabled',
    'default_agent_ask_user_enabled',
    'default_agent_image_generation_enabled',
    'default_agent_data_analysis_enabled',
    'default_agent_planner_enabled',
    'default_agent_pyodide_enabled',
    'default_agent_swarm_enabled',
    'default_agent_lazy_tools_mode_enabled',
    'midturn_injection_enabled',
)


def _hydrate_personalization(personalization):
    # Mirror of api/v2/author.py::_hydrate_personalization — keep in sync.
    if not personalization:
        return personalization
    result = dict(personalization)
    persona = result.get('persona') or 'generic'
    instructions_map = result.get('personality_instructions')
    if not isinstance(instructions_map, dict):
        instructions_map = {}
        if result.get('default_instructions'):
            instructions_map[persona] = result['default_instructions']
    result['personality_instructions'] = instructions_map
    for field in _PROJECT_SCOPED_SETTINGS_FIELDS:
        result.pop(field, None)
    return result


def _merge_personalization(existing, incoming):
    # Mirror of api/v2/author.py::API._merge_personalization — keep in sync.
    existing = dict(existing or {})
    merged = dict(incoming)

    persona = merged.get('persona') or existing.get('persona') or 'generic'
    existing_map = existing.get('personality_instructions')
    existing_map = dict(existing_map) if isinstance(existing_map, dict) else {}

    if 'personality_instructions' in incoming and isinstance(incoming.get('personality_instructions'), dict):
        merged_map = {**existing_map, **incoming['personality_instructions']}
    else:
        merged_map = existing_map
        if 'default_instructions' in incoming:
            merged_map[persona] = incoming.get('default_instructions') or ''

    merged['personality_instructions'] = merged_map
    merged['default_instructions'] = merged_map.get(persona, '')
    return merged


class TestHydrate:
    def test_none_passthrough(self):
        assert _hydrate_personalization(None) is None

    def test_legacy_row_seeds_dict_under_current_persona(self):
        out = _hydrate_personalization({'persona': 'qa', 'default_instructions': 'foo'})
        assert out['personality_instructions'] == {'qa': 'foo'}

    def test_existing_dict_preserved(self):
        out = _hydrate_personalization(
            {'persona': 'qa', 'personality_instructions': {'qa': 'a', 'generic': 'b'}}
        )
        assert out['personality_instructions'] == {'qa': 'a', 'generic': 'b'}


class TestMerge:
    def test_new_shape_merges_over_existing_keys(self):
        existing = {'persona': 'qa', 'personality_instructions': {'qa': 'a', 'generic': 'b'}}
        incoming = {'persona': 'qa', 'personality_instructions': {'qa': 'a2'}}
        out = _merge_personalization(existing, incoming)
        # generic must survive even though the client only sent qa.
        assert out['personality_instructions'] == {'qa': 'a2', 'generic': 'b'}
        assert out['default_instructions'] == 'a2'  # server-owned mirror

    def test_legacy_payload_edits_current_persona_slot_not_generic(self):
        # THE critical bug: legacy client sends only default_instructions while on persona=qa.
        existing = {'persona': 'qa', 'personality_instructions': {'qa': 'old', 'generic': 'keep'}}
        incoming = {'persona': 'qa', 'default_instructions': 'new'}  # no personality_instructions key
        out = _merge_personalization(existing, incoming)
        assert out['personality_instructions'] == {'qa': 'new', 'generic': 'keep'}
        assert out['default_instructions'] == 'new'

    def test_legacy_payload_never_wipes_untouched_personas(self):
        existing = {'persona': 'nerdy', 'personality_instructions': {'generic': 'g', 'qa': 'q'}}
        incoming = {'persona': 'nerdy', 'default_instructions': 'n'}
        out = _merge_personalization(existing, incoming)
        assert out['personality_instructions'] == {'generic': 'g', 'qa': 'q', 'nerdy': 'n'}

    def test_server_owns_mirror_ignoring_client_default_instructions(self):
        # Client tries to set a bogus mirror; server recomputes from the map.
        existing = {'persona': 'qa', 'personality_instructions': {'qa': 'real'}}
        incoming = {'persona': 'qa', 'personality_instructions': {'qa': 'real'},
                    'default_instructions': 'BOGUS'}
        out = _merge_personalization(existing, incoming)
        assert out['default_instructions'] == 'real'

    def test_empty_existing(self):
        out = _merge_personalization(None, {'persona': 'qa', 'default_instructions': 'x'})
        assert out['personality_instructions'] == {'qa': 'x'}
