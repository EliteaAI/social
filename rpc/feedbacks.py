from pydantic.v1 import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy import desc

from tools import auth
from pylon.core.tools import web, log

from ..models.feedbacks import Feedback
from ..models.pd.feedbacks import FeedbackModel, FeedbackUpdateModel


class RPC:
    @web.rpc("social_get_feedback_validator", "get_feedback_validator")
    def get_feedback_validator(self, operation="create"):
        if operation == "update":
            return FeedbackUpdateModel
        return FeedbackModel

    @web.rpc(f'social_feedback_create', "feedback_create")
    def create_feedback(self, data: dict) -> dict:
        if not data.get('user_id'):
            data['user_id'] = auth.current_user().get("id")
        try:
            FeedbackModel.validate(data)
        except ValidationError as e:
            return {'ok': False, 'error': str(e)}

        try:
            feedback = Feedback(**data)
            feedback.insert()
        except Exception as e:
            return {"ok": False, "error": str(e)}
        return {'ok': True, 'result': feedback}
    

    @web.rpc("social_list_feedbacks", "list_feedbacks")
    def list_feedbacks(self, args: dict) -> dict:
        offset = args.pop("offset", None)
        limit = args.pop("limit", None)
        sort_by = args.pop("sort_by", "id")
        sort_order = args.pop("sort_order", "asc")

        filters = []
        # direct filtering
        for field, value in args.items():
            if not hasattr(Feedback, field):
                pass
            filters.append(getattr(Feedback, field)==value)
        
        query = Feedback.query.filter(*filters)
        total = query.count()
        
        if sort_order.lower() == "asc":
            query = query.order_by(getattr(Feedback, sort_by, sort_by))
        else:
            query = query.order_by(desc(getattr(Feedback, sort_by, sort_by)))

        query = query.limit(limit).offset(offset)
        feedbacks = query.all()
        result = {'total': total, 'rows': [feedback.to_json() for feedback in feedbacks]}
        return {"ok": True, "result": result}
    
    
    @web.rpc("social_get_feedback", "get_feedback")
    def get_feedback(self, id: int) -> dict:
        if feedback := Feedback.query.get(id):
            return {"ok": True, "result": feedback}
        return {"ok": False, "error": f"Feedback with id '{id}' not found"}


    @web.rpc("social_delete_feedback", "delete_feedback")
    def delete_feedback(self, id: int) -> dict:
        if feedback := Feedback.query.get(id):
            feedback.delete()
            return {"ok": True, "result": "Successfully deleted"}
        return {"ok": False, "error": f"Feedback with id '{id}' not found"}
    

    @web.rpc("social_update_feedback", "update_feedback")
    def update_feedback(self, id: int, payload: dict) -> dict:
        feedback = Feedback.query.get(id)

        if not feedback:
            return {"ok": False, "error": f"Feedback with id '{id}' not found"}
        
        try:
            FeedbackUpdateModel.validate(payload)
        except ValidationError as e:
            return {'ok': False, 'error': str(e)}
        
        for field, value in payload.items():
            if hasattr(feedback, field):
                setattr(feedback, field, value)
        
        feedback.commit()
        return {"ok": True, "result": feedback}

