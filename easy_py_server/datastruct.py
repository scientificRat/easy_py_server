from http.server import HTTPStatus
from http.client import HTTPMessage
from typing import (Optional, Dict, Any)
from enum import Enum
from .exception import IllegalAccessException


class Request:
    def __init__(self, session: dict, params: dict, cookies: dict = None, raw_headers: HTTPMessage = None):
        if session is None:
            session = {}
        self.session = session
        self.params = params
        self.cookies = cookies
        self.raw_headers = raw_headers

    def get_parm(self, key: str, required=True) -> str:
        value = self.params.get(key, None)
        if required and value is None:
            raise IllegalAccessException("Parameter '%s' is required" % (key,))
        return value

    def get_session(self) -> Dict[Any, Any]:
        return self.session

    def get_session_attribute(self, key: Any) -> Optional[Any]:
        return self.session.get(key, None)

    def remove_session(self, key: Any):
        self.session.pop(key, None)

    def set_session_attribute(self, key: Any, value: Any):
        self.session[key] = value

    def get_cookie(self, key):
        if self.cookies is not None:
            return self.cookies[key]
        return None


class Response:
    DEFAULT_CONTENT_TYPE = "text/html; charset=utf-8"

    def __init__(self, content=None, content_type=None):
        self.content = content
        self.content_type = content_type
        self.status = HTTPStatus.OK
        self.error_message = None
        self.new_session = None
        self.set_cookie_dict = {}
        self.additional_headers = {}
        self.redirection_url = None

    def set_content_type(self, content_type: str) -> None:
        self.content_type = content_type

    def get_content_type(self) -> str:
        return self.content_type if self.content_type is not None else self.DEFAULT_CONTENT_TYPE

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

    def set_new_session(self, session):
        self.new_session = session

    def get_new_session(self):
        return self.new_session

    def set_cookie(self, key, value):
        self.set_cookie_dict[key] = value

    def get_cookie_dict(self):
        return self.set_cookie_dict

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


class MultipartFile:
    def __init__(self, filename: str, content_type: str, data: bytes):
        self.filename = filename
        self.content_type = content_type
        self.data = data
        self.__data_pointer = 0

    def save(self, file: str):
        with open(file, 'wb') as f:
            f.write(self.data)

    def read(self, cnt):
        end = max(self.__data_pointer + cnt, len(self.data))
        rst = self.data[self.__data_pointer: end]
        self.__data_pointer += cnt
        return rst
