from http import HTTPStatus
from http.client import HTTPMessage
from typing import (Optional, Dict, Any)
from enum import Enum
from .exception import IllegalAccessException


class Request:
    def __init__(self, params: dict, cookies: dict = None, session: dict = None, raw_headers: HTTPMessage = None):
        self.params = params
        self.cookies = cookies
        self.session = session
        self.raw_headers = raw_headers  # type: HTTPMessage

    def get_parm(self, key: str, required=True) -> str:
        value = self.params.get(key, None)
        if required and value is None:
            raise IllegalAccessException("Parameter '%s' is required" % (key,))
        return value

    def get_session(self) -> Dict[Any, Any]:
        return self.session if self.session is not None else {}

    def get_session_attribute(self, key: Any) -> Optional[Any]:
        return self.session.get(key, None) if self.session is not None else None

    def remove_session(self, key: Any):
        if self.session is not None:
            self.session.pop(key, None)

    def set_session_attribute(self, key: Any, value: Any):
        if self.session is None:
            self.session = {}
        self.session[key] = value

    def get_cookie(self, key):
        if self.cookies is not None:
            return self.cookies[key]
        return None


class Response:

    def __init__(self, content=None, content_type=None, status=HTTPStatus.OK, headers: Dict = None):
        self.content = content
        self.content_type = content_type
        self.status = status
        self.error_message = None
        self.set_cookie_str_list = []
        self.additional_headers = {}
        self.redirection_url = None
        self.headers = {} if headers is None else headers

    def set_header(self, key, value):
        self.headers[key] = value

    def set_content_type(self, content_type: str) -> None:
        self.content_type = content_type

    def get_content_type(self) -> str:
        return self.content_type

    def set_status(self, status: HTTPStatus):
        self.status = status

    def get_status(self):
        return self.status

    def set_status_by_code(self, code: int):
        self.status = HTTPStatus(code)

    def set_content(self, content: Any):
        self.content = content

    def get_content(self):
        return self.content

    def set_cookie_str(self, cookie_str):
        self.set_cookie_str_list.append(cookie_str)

    def set_cookie_kv(self, key, value):
        self.set_cookie_str("%s=%s" % (str(key), str(value)))

    def get_cookie_str_list(self):
        return self.set_cookie_str_list

    def add_header(self, key: str, value: str):
        self.additional_headers[key] = value

    def get_additional_headers(self):
        return self.additional_headers

    def set_redirection_url(self, url):
        self.redirection_url = url

    def get_redirection_url(self):
        return self.redirection_url

    def error(self, message: str, status=HTTPStatus.BAD_REQUEST):
        self.error_message = message
        self.status = status

    def get_error_message(self):
        return self.error_message


# response file for download
class ResponseFile(Response):
    def __init__(self, file_bytes, filename=None):
        headers = {'Content-Transfer-Encoding': 'binary'}
        if filename is not None:
            headers['Content-Disposition'] = 'attachment; filename="{}"'.format(filename)
        super().__init__(file_bytes, content_type="application/octet-stream", headers=headers)


# reference from RFC 7231
class Method(Enum):
    GET = 1
    HEAD = 2
    POST = 3
    PUT = 4
    DELETE = 5
    CONNECT = 6
    OPTIONS = 7
    TRACE = 8
    PATCH = 9


# upload file
class MultipartFile:
    def __init__(self, filename: str, content_type: str, data: bytes):
        self.filename = filename
        self.content_type = content_type
        self.data = data
        self.__data_pointer = 0

    def save(self, file: str):
        with open(file, 'wb') as f:
            f.write(self.data)

    def read(self, cnt=-1):
        if cnt < 0:
            cnt = len(self.data)
        end = max(self.__data_pointer + cnt, len(self.data))
        rst = self.data[self.__data_pointer: end]
        self.__data_pointer = end
        return rst
