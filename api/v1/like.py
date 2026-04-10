from queue import Empty

from sqlalchemy.exc import IntegrityError
from tools import api_tools, auth

from ...constants import PROMPT_LIB_MODE


class PromptLibAPI(api_tools.APIModeHandler):
    @api_tools.endpoint_metrics
    def post(self, project_id: int, entity: str, entity_id: int):
        try:
            result = self.module.like(
                project_id=project_id, entity=entity, entity_id=entity_id
            )
        except IntegrityError:
            return {"ok": False, "error": "Already liked"}, 400
        return result, 201

    @api_tools.endpoint_metrics
    def delete(self, project_id: int, entity: str, entity_id: int):
        result = self.module.dislike(
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
