from tools import api_tools

from ...constants import PROMPT_LIB_MODE


class PromptLibAPI(api_tools.APIModeHandler):
    @api_tools.endpoint_metrics
    def post(self, project_id: int, entity: str, entity_id: int):
        result = self.module.pin(
            project_id=project_id, entity=entity, entity_id=entity_id
        )
        if result.get('ok'):
            return result, 201
        return result, 400

    @api_tools.endpoint_metrics
    def delete(self, project_id: int, entity: str, entity_id: int):
        result = self.module.unpin(
            project_id=project_id, entity=entity, entity_id=entity_id
        )
        return result, 204


class API(api_tools.APIBase):
    url_params = api_tools.with_modes(
        [
            "<int:project_id>/<string:entity>/<int:entity_id>",
        ]
    )

    mode_handlers = {
        PROMPT_LIB_MODE: PromptLibAPI,
    }

