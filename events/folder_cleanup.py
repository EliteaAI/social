"""Event handlers for cleaning up folder items when entities are deleted."""

from pylon.core.tools import web, log

from ..models.enums.entity import EntityType


class Event:
    """Handle entity deletion events to clean up orphan folder items."""

    @web.event("application_deleted")
    def on_application_deleted(self, context, event, payload):
        """Clean up folder items when an application (agent/pipeline) is deleted."""
        project_id = payload.get('project_id')
        app_id = payload.get('id') or payload.get('application_id')
        app_type = payload.get('type', '')  # 'openai' for agents, 'pipeline' for pipelines

        if not project_id or not app_id:
            return

        # Map application type to entity type
        entity_type = EntityType.pipeline.value if app_type == 'pipeline' else EntityType.agent.value

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
        """Clean up folder items when a toolkit/MCP is deleted."""
        project_id = payload.get('project_id')
        tool_id = payload.get('id') or payload.get('tool_id')
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

    @web.event("skill_deleted")
    def on_skill_deleted(self, context, event, payload):
        """Clean up folder items when a skill is deleted."""
        project_id = payload.get('project_id')
        skill_id = payload.get('id') or payload.get('skill_id')

        if not project_id or not skill_id:
            return

        try:
            result = self.remove_entity_from_folders(
                project_id=project_id,
                entity_type=EntityType.skill.value,
                entity_id=skill_id
            )
            if result.get('deleted', 0) > 0:
                log.info("Cleaned up %s folder items for deleted skill %s",
                         result['deleted'], skill_id)
        except Exception as e:
            log.warning("Failed to clean up folder items for skill %s: %s",
                        skill_id, e)

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
