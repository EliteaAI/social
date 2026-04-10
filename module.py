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

from tools import theme


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

    def init(self):
        """ Init module """
        log.info('Initializing Social Plugin')
        self.avatar_path.mkdir(parents=True, exist_ok=True)
        self.init_db()
        self.descriptor.init_all()

    def init_db(self):
        from tools import db
        from .models.likes import Like
        from .models.users import User
        from .models.feedbacks import Feedback
        db.get_shared_metadata().create_all(bind=db.engine)

    def deinit(self):  # pylint: disable=R0201
        """ De-init module """
        log.info('De-initializing')
