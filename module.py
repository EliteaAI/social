#!/usr/bin/python3
# coding=utf-8

#   Copyright 2026 EPAM Systems
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

""" Module """
from pathlib import Path

from pylon.core.tools import log  # pylint: disable=E0611,E0401
from pylon.core.tools import module


class Module(module.ModuleModel):
    """ Task module """

    def __init__(self, context, descriptor):
        self.context = context
        self.descriptor = descriptor
        #
        if "avatar_path" in self.descriptor.config:
            self.avatar_path = Path(self.descriptor.config["avatar_path"])
        else:
            self.avatar_path = Path(__file__).parent.joinpath("data", "avatar")
        #
        self._register_openapi()

    def _register_openapi(self):
        """Register API endpoints with OpenAPI registry."""
        try:
            from tools import openapi_registry  # pylint: disable=E0401,C0415
            from .api import v2 as api_v2
            openapi_registry.register_plugin(
                plugin_name="social",
                version=self.descriptor.metadata.get("version", "1.0.0"),
                description="Social features — likes, pins, feedbacks, author profiles.",
                tags=[
                    {
                        "name": "social",
                        "description": "Social features — likes, pins, feedbacks, and author profiles.",
                    },
                ],
                api_module=api_v2,
            )
        except Exception as e:  # pylint: disable=W0703
            log.warning("Failed to register OpenAPI for social plugin: %s", e)

    def init(self):
        """ Init module """
        log.info('Initializing Social Plugin')
        self.avatar_path.mkdir(parents=True, exist_ok=True)
        self.init_db()
        self._register_permissions()
        self.descriptor.init_all()
        self._seed_default_survey()

    def init_db(self):
        from tools import db
        from .models.likes import Like
        from .models.users import User
        from .models.feedbacks import Feedback
        from .models.surveys import Survey, SurveyQuestion, SurveyAnswer
        db.get_shared_metadata().create_all(bind=db.engine)

    def _register_permissions(self):
        from tools import auth, config as c  # pylint: disable=E0401,C0415
        # Admin: manage survey configuration
        auth.register_permissions({
            "permissions": ["models.admin.surveys.manage"],
            "recommended_roles": {
                c.ADMINISTRATION_MODE: {"admin": True, "editor": False, "viewer": False},
            }})
        # Admin: view survey response reports (Reports menu)
        auth.register_permissions({
            "permissions": ["models.admin.surveys.reports.view"],
            "recommended_roles": {
                c.ADMINISTRATION_MODE: {"admin": True, "editor": False, "viewer": False},
            }})
        # NOTE: end-user survey endpoints (active / response / shown / dismiss) are login-only
        # (authenticated via the forward-auth proxy, keyed by user_id) and are not project-scoped,
        # so they use @api_tools.endpoint_metrics without check_api — no extra permission needed.

    def _seed_default_survey(self):
        """Seed the default 'NPS Elitea' survey once (AC2)."""
        from tools import db  # pylint: disable=E0401,C0415
        from .models.surveys import Survey, SurveyQuestion  # pylint: disable=C0415
        try:
            with db.with_project_schema_session(None) as session:
                exists = session.query(Survey).filter(Survey.name == "NPS Elitea").first()
                if exists:
                    return
                survey = Survey(
                    name="NPS Elitea",
                    description="Net Promoter Score survey for Elitea (internal note for POs/Admins).",
                    enabled=False,
                    dismissible=True,
                )
                session.add(survey)
                session.flush()
                session.add(SurveyQuestion(
                    survey_id=survey.id,
                    title="How likely are you to recommend Elitea to a friend or colleague?",
                    question_type="slider",
                    options={
                        "min": 0,
                        "max": 10,
                        "min_label": "Not likely",
                        "max_label": "Very likely",
                        "style": "buttons",
                    },
                    position=0,
                ))
                session.commit()
                log.info("Seeded default 'NPS Elitea' survey")
        except Exception as e:  # pylint: disable=W0703
            log.warning("Failed to seed default NPS survey: %s", e)

    def deinit(self):  # pylint: disable=R0201
        """ De-init module """
        log.info('De-initializing')
