from uuid import uuid4

from pathlib import Path

from flask import request, url_for
from tools import config as c, api_tools, auth, register_openapi


class AdminApi(api_tools.APIModeHandler):

    @register_openapi(
        name="List Avatars",
        description="List all available avatar images with their URLs.",
        available_to_users=True,
    )
    @auth.decorators.check_api({
        "permissions": ["models.social.avatar.get"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": False, "viewer": False},
        }})
    def get(self, **kwargs):
        return [
            {
                'name': i.name,
                'url': url_for('social.static', filename=f'{self.module.avatar_path.name}/{i.name}', _external=True)
            } for i in self.module.avatar_path.iterdir()
        ], 200

    @register_openapi(
        name="Upload Avatar",
        description="Upload a new avatar image (multipart/form-data). Accepts 'file' field plus optional 'width' and 'height' form fields.",
        request_body={
            "required": True,
            "content": {
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "file": {
                                "type": "string",
                                "format": "binary",
                                "description": "Avatar image file to upload.",
                            },
                            "width": {
                                "type": "integer",
                                "default": 64,
                                "description": "Target width in pixels for the saved image.",
                            },
                            "height": {
                                "type": "integer",
                                "default": 64,
                                "description": "Target height in pixels for the saved image.",
                            },
                        },
                        "required": ["file"],
                    }
                }
            },
        },
        available_to_users=True,
    )
    @auth.decorators.check_api({
        "permissions": ["models.social.avatar.post"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": False, "viewer": False},
        }})
    def post(self, **kwargs):
        if 'file' not in request.files:
            return {'error': 'No file in request.files'}, 400
        file = request.files['file']
        final_width = int(request.form.get('width', 64))
        final_height = int(request.form.get('height', 64))

        file_name = f'{uuid4()}.png'
        file_path: Path = self.module.avatar_path.joinpath(file_name)
        url_for: str = 'social.avatar'

        result = self.module.save_image(file, file_path, url_for, final_width, final_height)
        if result['ok']:
            return result['data'], 200
        else:
            return result['error'], 400

    @register_openapi(
        name="Delete Avatar",
        description="Delete an avatar image by file name.",
        parameters=[
            {"name": "file_name", "in": "path", "schema": {"type": "string"},
             "description": "Avatar file name to delete."},
        ],
        available_to_users=True,
    )
    @auth.decorators.check_api({
        "permissions": ["models.social.avatar.delete"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": False, "viewer": False},
        }})
    def delete(self, file_name: str, **kwargs):
        file_path: Path = self.module.avatar_path.joinpath(file_name)
        result = self.module.remove_image(file_path)

        if result['ok']:
            return result['data'], 200
        else:
            return result['error'], 400


class API(api_tools.APIBase):
    url_params = api_tools.with_modes([
        '',
        '<string:mode>/<string:file_name>'
    ])

    mode_handlers = {
        c.ADMINISTRATION_MODE: AdminApi,
    }
