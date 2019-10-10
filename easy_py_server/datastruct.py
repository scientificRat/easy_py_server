from http.server import HTTPStatus
from typing import (Optional, Dict, Any)
from enum import Enum
from .exception import IllegalAccessException


class Request:
    def __init__(self, session: dict, param: dict):
        if session is None:
            session = {}
        self.__session = session
        self.__params = param

    def getParam(self, key: str, required=True) -> str:
        value = self.__params.get(key, None)
        if required and value is None:
            raise IllegalAccessException("Parameter '%s' is required" % (key,))
        return value

    def getSession(self) -> Dict[Any, Any]:
        return self.__session

    def getSessionAttribute(self, key: Any) -> Optional[Any]:
        return self.__session.get(key, None)

    def removeSession(self, key: Any):
        self.__session.pop(key, None)

    def setSessionAttribute(self, key: Any, value: Any):
        self.__session[key] = value


class Response:
    DEFAULT_CONTENT_TYPE = "text/html; charset=utf-8"

    def __init__(self, content=None, content_type=None):
        self.__content = content
        self.__content_type = content_type
        self.__status = HTTPStatus.OK
        self.__error_message = None
        self.__new_session = None

    def setContentType(self, content_type: str) -> None:
        self.__content_type = content_type

    def getContentType(self) -> str:
        return self.__content_type if self.__content_type is not None else self.DEFAULT_CONTENT_TYPE

    def setStatus(self, status: HTTPStatus):
        self.__status = status

    def getStatus(self):
        return self.__status

    def setStatusCode(self, code: int):
        self.__status = HTTPStatus(code)

    def setContent(self, content: Any):
        self.__content = content

    def getContent(self):
        return self.__content

    def setNewSession(self, session):
        self.__new_session = session

    def getNewSession(self):
        return self.__new_session

    def error(self, message: str, status=HTTPStatus.BAD_REQUEST):
        self.__error_message = message
        self.__status = status

    def getErrorMessage(self):
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
