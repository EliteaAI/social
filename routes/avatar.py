import json
import flask
from pathlib import Path

from pylon.core.tools import web, log

from werkzeug.exceptions import NotFound


class Route:
    @web.route("/avatar/<path:sub_path>")
    def avatar(self, sub_path):
        return flask.send_from_directory(self.avatar_path, sub_path)
