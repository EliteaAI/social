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
    - skill_deleted: {'id': ..., 'name': ..., 'project_id': ...}

    Also purges folder access exceptions (#6524) when a user leaves the project.
    """

    @web.event("application_deleted")
    def on_application_deleted(self, context, event, payload):
        """Clean up folder items when an application (agent/pipeline) is deleted.

        Payload is ApplicationDetailModel.model_dump() with project_id added.
        """
        project_id = payload.get('project_id')
        app_id = payload.get('id')

        if not project_id or not app_id:
            return

        # agent_type lives in version_details and is absent when the deleted app had no
        # default version, so both types are cleared: application ids are unique.
        entity_types = [EntityType.agent.value, EntityType.pipeline.value]

        try:
            result = self.remove_entity_from_folders(
                project_id=project_id,
                entity_type=entity_types,
                entity_id=app_id
            )
            if result.get('deleted', 0) > 0:
                log.info("Cleaned up %s folder items for deleted application %s",
                         result['deleted'], app_id)
        except Exception as e:
            log.warning("Failed to clean up folder items for application %s: %s",
                        app_id, e)

    @web.event("toolkit_deleted")
    def on_toolkit_deleted(self, context, event, payload):
        """Clean up folder items when a toolkit/MCP is deleted.

        Payload is ToolDetails.dict() with owner_id set to project_id.
        NOTE: The event passes project_id as 'owner_id', not 'project_id'.
        """
        project_id = payload.get('owner_id')
        tool_id = payload.get('id')

        if not project_id or not tool_id:
            return

        # Local MCPs are flagged by meta.mcp rather than type='mcp', so both types are
        # cleared instead of re-deriving the distinction: toolkit ids are unique.
        entity_types = [EntityType.toolkit.value, EntityType.mcp.value]

        try:
            result = self.remove_entity_from_folders(
                project_id=project_id,
                entity_type=entity_types,
                entity_id=tool_id
            )
            if result.get('deleted', 0) > 0:
                log.info("Cleaned up %s folder items for deleted toolkit %s",
                         result['deleted'], tool_id)
        except Exception as e:
            log.warning("Failed to clean up folder items for toolkit %s: %s",
                        tool_id, e)

    @web.event("skill_deleted")
    def on_skill_deleted(self, context, event, payload):
        """Clean up folder items when a skill is deleted.

        Payload from elitea_core skill_utils.delete_skill():
        - id: skill ID
        - name: skill name
        - project_id: project ID
        """
        project_id = payload.get('project_id')
        skill_id = payload.get('id')

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

    @web.event("user_removed_from_project")
    def on_user_removed_from_project(self, context, event, payload):
        """Drop folder access exceptions of users who left the project (#6524).

        Payload: {'project_id': int, 'user_ids': [int, ...]}. A non-member cannot reach
        the project at all, so the rows are dead weight that would silently re-apply if
        the user were ever re-invited.
        """
        project_id = payload.get('project_id')
        user_ids = payload.get('user_ids') or []

        if not project_id or not user_ids:
            return

        try:
            result = self.purge_user_folder_access(
                project_id=project_id,
                user_ids=[int(i) for i in user_ids]
            )
            if result.get('deleted', 0) > 0:
                log.info("Purged %s folder access exceptions in project %s for users %s",
                         result['deleted'], project_id, user_ids)
        except Exception as e:
            log.warning("Failed to purge folder access for users %s in project %s: %s",
                        user_ids, project_id, e)

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
