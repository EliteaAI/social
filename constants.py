from .models.enums.entity import EntityType, FOLDER_ENTITY_TYPES


PROMPT_LIB_MODE = 'prompt_lib'


# Project-scoped settings fields (#6285, #6303): served via project-scoped module_settings
# API/RPCs, not the legacy global social_users.personalization blob.
PROJECT_SCOPED_SETTINGS_FIELDS = (
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


# Mapping of folder entity types to their database table names (for validation/lookup)
ENTITY_TABLE_MAP = {
    EntityType.agent: "applications",
    EntityType.pipeline: "applications",
    EntityType.skill: "skills",
    EntityType.toolkit: "elitea_tools",
    EntityType.mcp: "elitea_tools",
    EntityType.configuration: "configuration",
}


def is_valid_folder_entity(entity_type: str) -> bool:
    """Check if entity_type is valid for folder organization."""
    try:
        return EntityType(entity_type) in FOLDER_ENTITY_TYPES
    except ValueError:
        return False
