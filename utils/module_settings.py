"""Elitea Builder module defaults (#7383). Pure helpers, no pylon imports."""

BUILDER_DEFAULT_FIELDS = {
    'default_elitea_builder_enabled': (
        'default_internal_mcp_enabled',
        'default_skill_builder_enabled',
        'default_project_context_builder_enabled',
    ),
    'default_agent_elitea_builder_enabled': (
        'default_agent_internal_mcp_enabled',
        'default_agent_skill_builder_enabled',
        'default_agent_project_context_builder_enabled',
    ),
}
LEGACY_BUILDER_DEFAULT_FIELDS = frozenset(
    old for olds in BUILDER_DEFAULT_FIELDS.values() for old in olds
)
# What a column reads when the user never set it, neither the new key nor any old builder key (AC-5, AC-6)
UNSET_DEFAULTS = {
    'default_elitea_builder_enabled': True,
    'default_agent_elitea_builder_enabled': True,
}

# Other modules on by default for Chats and Agents when the user never set them (#7383: the Builder asks through
# Ask User)
UNSET_MODULE_DEFAULTS = {'default_ask_user_enabled': True, 'default_agent_ask_user_enabled': True}


def _value(field: str, stored: dict, legacy: dict) -> bool:
    return bool(stored[field]) if field in stored else bool(legacy.get(field, False))


def resolve_builder_defaults(stored: dict, legacy: dict) -> dict:
    """New key if present (stored, then legacy); else OR of the old keys, each stored-or-legacy; else the default."""
    stored = stored or {}
    legacy = legacy or {}
    result = {}
    for new_field, old_fields in BUILDER_DEFAULT_FIELDS.items():
        if new_field in stored or new_field in legacy:
            result[new_field] = _value(new_field, stored, legacy)
        elif any(old in stored or old in legacy for old in old_fields):
            result[new_field] = any(_value(old, stored, legacy) for old in old_fields)
        else:
            result[new_field] = UNSET_DEFAULTS[new_field]
    return result


def resolve_module_defaults(stored: dict, legacy: dict) -> dict:
    """Builder defaults plus the other modules that read as on when never set."""
    stored = stored or {}
    legacy = legacy or {}
    result = resolve_builder_defaults(stored, legacy)
    for field, default in UNSET_MODULE_DEFAULTS.items():
        result[field] = bool(stored[field]) if field in stored else bool(legacy.get(field, default))
    return result


def migrate_module_settings(stored: dict, legacy: dict):
    """Return (settings, changed): stored row with the new builder keys filled in; old keys kept."""
    stored = stored or {}
    if all(field in stored for field in BUILDER_DEFAULT_FIELDS):
        return stored, False
    return {**stored, **resolve_builder_defaults(stored, legacy)}, True
