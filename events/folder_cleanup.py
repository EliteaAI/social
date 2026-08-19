"""Event handlers for cleaning up folder items when entities are deleted."""

from pylon.core.tools import web, log

from ..models.enums.entity import EntityType


class Event:
    """Handle entity deletion events to clean up orphan folder items.

    Event payload structures (from elitea_core):
    - application_deleted: ApplicationDetailModel.model_dump() + {'project_id': ...}
      - agent_type is in version_details.agent_type, NOT at top level
    - toolkit_deleted: ToolDetails.dict() + {'owner_id': project_id}
      - project_id is passed as 'owner_id', NOT 'project_id'
    - configuration_deleted: ConfigurationDetails.model_dump()
      - has both 'id' and 'project_id'

    NOTE: skill_deleted event does not exist in elitea_core yet.
    Skill folder items will need manual cleanup or the event needs to be added.
    """

    @web.event("application_deleted")
    def on_application_deleted(self, context, event, payload):
        """Clean up folder items when an application (agent/pipeline) is deleted.

        Payload is ApplicationDetailModel.model_dump() with project_id added.
        The agent_type ('pipeline' vs 'openai'/etc) is nested in version_details.
        """
        project_id = payload.get('project_id')
        app_id = payload.get('id')

        if not project_id or not app_id:
            return

        # agent_type is nested in version_details, not at top level
        version_details = payload.get('version_details', {}) or {}
        agent_type = version_details.get('agent_type', '')

        # Map: 'pipeline' -> pipeline folder, anything else -> agent folder
        entity_type = EntityType.pipeline.value if agent_type == 'pipeline' else EntityType.agent.value

        try:
            result = self.remove_entity_from_folders(
                project_id=project_id,
                entity_type=entity_type,
                entity_id=app_id
            )
            if result.get('deleted', 0) > 0:
                log.info("Cleaned up %s folder items for deleted %s %s",
                         result['deleted'], entity_type, app_id)
        except Exception as e:
            log.warning("Failed to clean up folder items for %s %s: %s",
                        entity_type, app_id, e)

    @web.event("toolkit_deleted")
    def on_toolkit_deleted(self, context, event, payload):
        """Clean up folder items when a toolkit/MCP is deleted.

        Payload is ToolDetails.dict() with owner_id set to project_id.
        NOTE: The event passes project_id as 'owner_id', not 'project_id'.
        """
        # toolkit_deleted passes project_id as 'owner_id'
        project_id = payload.get('owner_id')
        tool_id = payload.get('id')
        tool_type = payload.get('type', '')  # 'mcp' for MCP servers

        if not project_id or not tool_id:
            return

        # Map toolkit type to entity type
        entity_type = EntityType.mcp.value if tool_type == 'mcp' else EntityType.toolkit.value

        try:
            result = self.remove_entity_from_folders(
                project_id=project_id,
                entity_type=entity_type,
                entity_id=tool_id
            )
            if result.get('deleted', 0) > 0:
                log.info("Cleaned up %s folder items for deleted %s %s",
                         result['deleted'], entity_type, tool_id)
        except Exception as e:
            log.warning("Failed to clean up folder items for %s %s: %s",
                        entity_type, tool_id, e)

    # NOTE: skill_deleted event does not exist in elitea_core.
    # The skill deletion API (elitea_core/api/v2/skill.py) does not fire any event.
    # Skill folder items will leak until either:
    # 1. elitea_core adds a skill_deleted event, or
    # 2. A periodic cleanup job is implemented
    # Keeping this handler commented out to avoid confusion about dead code.
    #
    # @web.event("skill_deleted")
    # def on_skill_deleted(self, context, event, payload):
    #     """Clean up folder items when a skill is deleted."""
    #     project_id = payload.get('project_id')
    #     skill_id = payload.get('id') or payload.get('skill_id')
    #     if not project_id or not skill_id:
    #         return
    #     try:
    #         result = self.remove_entity_from_folders(
    #             project_id=project_id,
    #             entity_type=EntityType.skill.value,
    #             entity_id=skill_id
    #         )
    #         if result.get('deleted', 0) > 0:
    #             log.info("Cleaned up folder items for deleted skill %s", skill_id)
    #     except Exception as e:
    #         log.warning("Failed to clean up folder items for skill %s: %s", skill_id, e)

    @web.event("configuration_deleted")
    def on_configuration_deleted(self, context, event, payload):
        """Clean up folder items when a configuration is deleted."""
        project_id = payload.get('project_id')
        config_id = payload.get('id') or payload.get('configuration_id')

        if not project_id or not config_id:
            return

        try:
            result = self.remove_entity_from_folders(
                project_id=project_id,
                entity_type=EntityType.configuration.value,
                entity_id=config_id
            )
            if result.get('deleted', 0) > 0:
                log.info("Cleaned up %s folder items for deleted configuration %s",
                         result['deleted'], config_id)
        except Exception as e:
            log.warning("Failed to clean up folder items for configuration %s: %s",
                        config_id, e)
