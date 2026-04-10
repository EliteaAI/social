from flask import request
from tools import api_tools, config as c, auth, db
from pydantic.v1 import ValidationError
from ...models.feedbacks import Feedback
from ...models.pd.feedbacks import FeedbackModel

from pylon.core.tools import log



class ProjectAPI(api_tools.APIModeHandler):
    @auth.decorators.check_api({
        "permissions": ["models.social.feedbacks.list"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
            c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": True},
        }})
    def get(self, project_id: int | None = None, **kwargs):
        args = dict(request.args)    
        result = self.module.list_feedbacks(args)
        return result['result'], 200



        

class API(api_tools.APIBase):
    url_params = api_tools.with_modes(
        [
            "",
            "<int:project_id>",
        ]
    )

    mode_handlers = {
        c.DEFAULT_MODE: ProjectAPI,
    }

    @auth.decorators.check_api({
        "permissions": ["models.social.feedbacks.create"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": True},
            c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": True},
        }})
    def post(self, project_id: int | None = None, **kwargs):
        data = request.get_json()
        author_id = auth.current_user().get("id")
        data['user_id'] = author_id
        data['user_agent'] = str(request.user_agent)
        if request.referrer:
            data['referrer'] = str(request.referrer)

        try:
            data_model = FeedbackModel.parse_obj(data)
        except ValidationError as e:
            return {"ok": False, "errors": e.errors()}, 400

        with db.with_project_schema_session(None) as session:
            feedback = Feedback(**data_model.dict())
            session.add(feedback)
            session.commit()
            return {'id': feedback.id}, 201
