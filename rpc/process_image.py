import os
from io import BytesIO
from pathlib import Path

from flask import url_for
from PIL import Image

from ..utils.image_utils import sizeof_fmt, SUPPORTED_FORMATS

from pylon.core.tools import web, log


class RPC:
    @web.rpc(f'social_save_image', "save_image")
    def save_image(
            self,
            file: BytesIO,
            file_path: Path,
            flask_route_url: str,
            final_width: int = 64,
            final_height: int = 64,
            project_id: int = None
    ) -> dict:
        """
        :param file: image data to be saved
        :param file_path: path of the image on disk
        :param flask_route_url: API route you should create to have file path URL, i.e. social/routes/avatar
        :param final_width: image width
        :param final_height: image height
        :return: dict containing file metadata and its url on the server
        """
        # Check file size - works for both BytesIO and SpooledTemporaryFile (files >= 512 KB)
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)
        
        if file_size == 0:
            return {'ok': False, 'error': 'The file is empty'}

        try:
            _, ext = os.path.splitext(file.filename)
            if ext.lower() not in SUPPORTED_FORMATS:
                return {'ok': False, 'error': 'Unsupported image format'}

            pillow_img = Image.open(file.stream)

            if pillow_img.width < final_width or pillow_img.height < final_height:
                return {'ok': False, 'error': 'Image dimensions are too small'}

            pillow_img.thumbnail(size=(final_width, final_height))
            pillow_img.save(file_path)
        except Exception as e:
            error_msg = f'Error during uploading the image {file_path.name}'
            log.error(f'{error_msg}: {str(e)}')
            return {'ok': False, 'error': error_msg}

        # Use file_size already calculated above
        initial_file_size = file_size

        file_name: str = file_path.name

        sub_path = f'{project_id}/{file_name}' if project_id else str(file_name)

        return {
            'ok': True,
            'data': {
                'initial_file_size': sizeof_fmt(initial_file_size),
                'resulting_file_size': sizeof_fmt(file_path.stat().st_size),
                'size': f'{final_width}x{final_height}',
                'name': file_name,
                'url': url_for(flask_route_url, sub_path=sub_path, _external=True),
            }
        }

    @web.rpc(f'social_remove_image', "remove_image")
    def remove_image(
            self, file_path: Path
    ) -> dict:
        """
        :param file_path: image file name saved on the server
        :return: ok True/False
        """
        if not file_path.exists():
            error_msg = f'File not found: {file_path.name}'
            log.error(error_msg)
            return {'ok': False, 'error': error_msg}

        try:
            file_path.unlink()
            log.debug(f'Successfully removed the image {file_path.name}')
        except FileNotFoundError:
            error_msg = f'File not found during removal: {file_path.name}'
            log.error(f'{error_msg}')
            return {'ok': False, 'error': error_msg}
        except PermissionError:
            error_msg = f'Permission denied when removing the image {file_path.name}'
            log.error(f'{error_msg}')
            return {'ok': False, 'error': error_msg}
        except OSError as e:
            error_msg = f'Error during removing the image {file_path.name}: {str(e)}'
            log.error(error_msg)
            return {'ok': False, 'error': error_msg}

        return {'ok': True, 'data': {}}
