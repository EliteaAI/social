"""Unit tests for pydantic model validation."""
import sys
import pytest
from pydantic.v1 import ValidationError


@pytest.fixture(scope='module')
def feedbacks_module(models_path):
    """Load the feedbacks module."""
    pd_path = models_path / "pd"
    sys.path.insert(0, str(pd_path))
    try:
        import feedbacks
        return feedbacks
    finally:
        sys.path.remove(str(pd_path))


class TestFeedbackModel:
    """Tests for FeedbackModel validation."""

    def test_valid_feedback(self, feedbacks_module):
        FeedbackModel = feedbacks_module.FeedbackModel
        feedback = FeedbackModel(
            rating=4,
            user_id=123,
            referrer="https://example.com",
            description="Great platform!",
            user_agent="Mozilla/5.0"
        )
        assert feedback.rating == 4
        assert feedback.user_id == 123
        assert feedback.description == "Great platform!"

    def test_rating_min_boundary(self, feedbacks_module):
        FeedbackModel = feedbacks_module.FeedbackModel
        feedback = FeedbackModel(
            rating=0,
            user_id=1,
            referrer=None,
            description="Poor experience",
            user_agent=None
        )
        assert feedback.rating == 0

    def test_rating_max_boundary(self, feedbacks_module):
        FeedbackModel = feedbacks_module.FeedbackModel
        feedback = FeedbackModel(
            rating=5,
            user_id=1,
            referrer=None,
            description="Excellent!",
            user_agent=None
        )
        assert feedback.rating == 5

    def test_rating_below_minimum_fails(self, feedbacks_module):
        FeedbackModel = feedbacks_module.FeedbackModel
        with pytest.raises(ValidationError):
            FeedbackModel(
                rating=-1,
                user_id=1,
                referrer=None,
                description="Test",
                user_agent=None
            )

    def test_rating_above_maximum_fails(self, feedbacks_module):
        FeedbackModel = feedbacks_module.FeedbackModel
        with pytest.raises(ValidationError):
            FeedbackModel(
                rating=6,
                user_id=1,
                referrer=None,
                description="Test",
                user_agent=None
            )

    def test_optional_fields_can_be_none(self, feedbacks_module):
        FeedbackModel = feedbacks_module.FeedbackModel
        feedback = FeedbackModel(
            rating=3,
            user_id=1,
            referrer=None,
            description="Average",
            user_agent=None
        )
        assert feedback.referrer is None
        assert feedback.user_agent is None

    def test_missing_required_field_fails(self, feedbacks_module):
        FeedbackModel = feedbacks_module.FeedbackModel
        with pytest.raises(ValidationError):
            FeedbackModel(
                rating=3,
                user_id=1,
                referrer=None,
                # missing description
                user_agent=None
            )


class TestFeedbackUpdateModel:
    """Tests for FeedbackUpdateModel - all fields optional."""

    def test_empty_update(self, feedbacks_module):
        FeedbackUpdateModel = feedbacks_module.FeedbackUpdateModel
        update = FeedbackUpdateModel()
        assert update.rating is None
        assert update.description is None

    def test_partial_update(self, feedbacks_module):
        FeedbackUpdateModel = feedbacks_module.FeedbackUpdateModel
        update = FeedbackUpdateModel(rating=5)
        assert update.rating == 5
        assert update.description is None

    def test_full_update(self, feedbacks_module):
        FeedbackUpdateModel = feedbacks_module.FeedbackUpdateModel
        update = FeedbackUpdateModel(
            rating=4,
            user_id=456,
            referrer="https://new.com",
            description="Updated feedback"
        )
        assert update.rating == 4
        assert update.user_id == 456

    def test_rating_validation_still_applies(self, feedbacks_module):
        FeedbackUpdateModel = feedbacks_module.FeedbackUpdateModel
        with pytest.raises(ValidationError):
            FeedbackUpdateModel(rating=10)
