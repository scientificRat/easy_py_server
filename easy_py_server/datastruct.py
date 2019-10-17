from http.server import HTTPStatus
from typing import (Optional, Dict, Any)
from enum import Enum
from .exception import IllegalAccessException


class Request:
    def __init__(self, session: dict, param: dict, cookies: dict = None):
        if session is None:
            session = {}
        self.__session = session
        self.__params = param
        self.__cookies = cookies

    def get_parm(self, key: str, required=True) -> str:
        value = self.__params.get(key, None)
        if required and value is None:
            raise IllegalAccessException("Parameter '%s' is required" % (key,))
        return value

    def get_session(self) -> Dict[Any, Any]:
        return self.__session

    def get_session_attribute(self, key: Any) -> Optional[Any]:
        return self.__session.get(key, None)

    def remove_session(self, key: Any):
        self.__session.pop(key, None)

    def set_session_attribute(self, key: Any, value: Any):
        self.__session[key] = value

    def get_cookie(self, key):
        if self.__cookies is not None:
            return self.__cookies[key]
        return None


class Response:
    DEFAULT_CONTENT_TYPE = "text/html; charset=utf-8"

    def __init__(self, content=None, content_type=None):
        self.__content = content
        self.__content_type = content_type
        self.__status = HTTPStatus.OK
        self.__error_message = None
        self.__new_session = None
        self.__set_cookie_dict = {}
        self.__additional_headers = {}
        self.__redirection_url = None

    def set_content_type(self, content_type: str) -> None:
        self.__content_type = content_type

    def get_content_type(self) -> str:
        return self.__content_type if self.__content_type is not None else self.DEFAULT_CONTENT_TYPE

    def set_status(self, status: HTTPStatus):
        self.__status = status

    def get_status(self):
        return self.__status

    def set_status_by_code(self, code: int):
        self.__status = HTTPStatus(code)

    def set_content(self, content: Any):
        self.__content = content

    def get_content(self):
        return self.__content

    def set_new_session(self, session):
        self.__new_session = session

    def get_new_session(self):
        return self.__new_session

    def set_cookie(self, key, value):
        self.__set_cookie_dict[key] = value

    def get_cookie_dict(self):
        return self.__set_cookie_dict

    def add_header(self, key: str, value: str):
        self.__additional_headers[key] = value

    def get_additional_headers(self):
        return self.__additional_headers

    def set_redirection_url(self, url):
        self.__redirection_url = url

    def get_redirection_url(self):
        return self.__redirection_url

    def error(self, message: str, status=HTTPStatus.BAD_REQUEST):
        self.__error_message = message
        self.__status = status

    def get_error_message(self):
        return self.__error_message


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
