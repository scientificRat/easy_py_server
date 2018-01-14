from http.server import HTTPServer, BaseHTTPRequestHandler, HTTPStatus
from typing import Optional, Callable, Dict, Tuple, Sequence, Any
from enum import Enum
import os, sys
import re
import uuid
import traceback
import urllib.parse
import time, threading, datetime

__all__ = ["IllegalAccessException", "Request", "Response", "RequestListener", "Method", "Httpd"]


class IllegalAccessException(Exception):
    pass


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
    def __init__(self):
        self.__content_type = "text/html; charset=utf-8"
        self.__status = HTTPStatus.OK
        self.__error_message = None

    def setContentType(self, content_type: str) -> None:
        self.__content_type = content_type

    def getContentType(self) -> str:
        return self.__content_type

    def setStatus(self, status: HTTPStatus):
        self.__status = status

    def getStatus(self):
        return self.__status

    def setStatusCode(self, code: int):
        self.__status = HTTPStatus(code)

    def error(self, message: str, status=HTTPStatus.BAD_REQUEST):
        self.__error_message = message
        self.__status = status

    def getErrorMessage(self):
        return self.__error_message


RequestListener = Callable[[Request, Response], Any]


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


class EasyServerHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"
    server_version = "EasyServer/0.2.1"
    resource_dir = 'www/'
    error_message_format = """<!DOCTYPE html>
    <html>
        <head>
            <meta http-equiv="Content-Type" content="text/html;charset=utf-8">
            <title>Error Page</title>
        </head>
        <body>
            <h1>%(code)d %(message)s</h1><p>Error code explanation: <b>%(code)s</b> </p>details: <br><pre>%(explain)s</pre>
        </body>
    </html>
    """
    extensions_map = {
        'py': 'text/plain', 'c': 'text/plain', 'h': 'text/plain', 'cpp': 'text/plain', 'hpp': 'text/plain',
        'txt': 'text/plain',
        'html': 'text/html', 'htm': 'text/html', 'htx': 'text/html',
        'csv': 'text/csv',
        'jpeg': 'image/jpeg', 'jpg': 'image/jpeg', 'jpe': 'image/jpeg',
        'gif': 'image/gif',
        'png': 'image/png',
        'svg': 'image/svg+xml',
        'tif': 'image/tiff', 'tiff': "image/tiff",
        'ico': 'application/x-ico',
        'css': 'text/css',
        'js': 'application/javascript',
        'json': 'application/json',
        'pdf': 'application/pdf',
        'woff': 'application/font-woff',
        'mp3': 'audio/mp3',
        'mp4': 'audio/mp4',
        'wma': 'audio/x-ms-wma',
        'avi': 'video/avi',
    }
    SESSION_COOKIE_NAME = "EASY_SESSION_ID"
    DEFAULT_SESSION_EXPIRE_SECONDS = 12 * 3600

    def version_string(self):
        return self.server_version

    def on_exception(self, e):
        e_str = ""
        if isinstance(e, IllegalAccessException):
            e_str = str(e)
        else:
            # TODO: not good implementation
            exc_type, exc_value, exc_traceback = sys.exc_info()
            err_list = traceback.format_exception(exc_type, exc_value, exc_traceback, limit=5)
            for item in err_list:
                e_str += str(item)

        self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, None, e_str)

    def find_and_call_api_listener(self, path: str, param: dict, method: Method):
        listeners_dic = self.server.listeners_dic
        entity = listeners_dic.get(path, None)
        if entity is None:
            for k in listeners_dic:
                match = re.fullmatch(k, path)
                if match is not None and len(listeners_dic[k]) == 3:
                    path_param_values = match.groups()
                    _, _, params_key = listeners_dic[k]
                    if len(path_param_values) == len(params_key):
                        for i in range(0, len(params_key)):
                            param[params_key[i]] = urllib.parse.unquote(path_param_values[i])
                        entity = listeners_dic[k]
                        break
        if entity is None:
            return False
        listener, methods, _ = entity
        if listener is not None:
            if method not in methods:
                self.send_error(HTTPStatus.METHOD_NOT_ALLOWED)
                return True
            session = self.get_session()
            current_none_session = False
            if session is None:
                current_none_session = True
            request, response = Request(session, param), Response()
            try:
                rtn = listener(request, response)
                # if error message is set, ignore any return content
                if response.getErrorMessage() is not None:
                    self.send_error(response.getStatus(), None, response.getErrorMessage())
                    return True
                if type(rtn) == str:
                    content = rtn.encode("utf-8")
                elif type(rtn) == bytes or rtn is None:
                    content = rtn
                else:
                    content = bytes(rtn)
            except Exception as e:
                self.on_exception(e)
                return True
            self.send_response(response.getStatus())
            self.send_header("Content-type", response.getContentType())
            self.send_header("Content-Length", len(content))
            if current_none_session and request.getSession() is not None:
                self.set_new_session_cookie(request.getSession())
            self.end_headers()
            self.wfile.write(content)
            return True
        else:
            return False

    def get_session(self) -> Optional[dict]:
        cookie_str = self.headers.get('Cookie', "")
        cookies = re.findall(self.SESSION_COOKIE_NAME + "=([a-zA-Z0-9_-]*)", cookie_str)  # time consuming
        if len(cookies) <= 0:
            return None
        for c in cookies:
            if c in self.server.sessions:
                return self.server.sessions.get(c, None)
        return None

    def set_new_session_cookie(self, session):
        new_session_code = str(uuid.uuid1()).replace("-", "")
        while new_session_code in self.server.sessions:
            new_session_code = str(uuid.uuid1()).replace("-", "")

        def clean_expire_session():
            time.sleep(self.DEFAULT_SESSION_EXPIRE_SECONDS)
            self.server.sessions.pop(new_session_code)

        threading.Thread(target=clean_expire_session).start()
        self.server.sessions[new_session_code] = session
        expire_date = self.date_time_string(time.time() + self.DEFAULT_SESSION_EXPIRE_SECONDS)
        set_cookie_str = self.SESSION_COOKIE_NAME + "=" + new_session_code + "; path=/; expires=" + expire_date
        self.send_header("Set-Cookie", set_cookie_str)

    def deal_static_file_request(self, path):
        path = self.resource_dir + path[1:]
        if len(path) == 0 or path[-1] == '/':
            indexes = ["index.html", "index.htm"]
            for index in indexes:
                if os.path.isfile(path + index):
                    path += index
        if os.path.isdir(path):
            self.send_error(HTTPStatus.FORBIDDEN)
            return

        postfix = path.split('.')[-1].lower()
        default_type = 'application/octet-stream'
        content_type = default_type if len(postfix) == len(path) else self.extensions_map.get(postfix, default_type)
        try:
            f = open(path, 'rb')
        except OSError:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            fs = os.fstat(f.fileno())
            last_modified = self.headers.get("If-Modified-Since", None)
            if last_modified is not None:
                last_modified_time = time.strptime(last_modified, '%a, %d %b %Y %H:%M:%S %Z')
                if time.gmtime(fs.st_mtime) == last_modified_time:
                    self.send_response(HTTPStatus.NOT_MODIFIED)
                    self.end_headers()
                    return
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-type", content_type)
            self.send_header("Content-Length", str(fs.st_size))
            self.send_header("Last-Modified", self.date_time_string(fs.st_mtime))
            self.end_headers()
            while True:
                buf = f.read(1024 * 16)
                if not buf:
                    break
                self.wfile.write(buf)
            return
        except EnvironmentError:
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR)
        finally:
            f.close()

    @staticmethod
    def parse_parameter(src_str):
        param = {}
        for item in re.findall(r'(^|&)([^=]+)=([^&]*)', src_str):
            param[urllib.parse.unquote(item[1])] = urllib.parse.unquote(item[2])
        return param

    @staticmethod
    def parse_url_path(path) -> Tuple[str, Dict[str, str]]:
        row = path.split('?')
        param = {} if len(row) < 2 else EasyServerHandler.parse_parameter(row[1])
        return row[0], param

    def parse_request_body(self):
        request_len = int(self.headers.get("Content-Length", 0))
        request_type = self.headers.get("Content-Type", None)
        body = self.rfile.read(request_len)
        print(request_type)
        param_more = None
        if re.match("application/x-www-form-urlencoded", request_type) is not None:
            param_more = self.parse_parameter(bytes.decode(body))
        # todo
        return body, param_more

    def do_GET(self):
        # 解析并分离URL参数
        path, param = self.parse_url_path(self.path)
        # 首先尝试调用api listener, 如果没有对应的listener则认为是静态资源
        if not self.find_and_call_api_listener(path, param, Method.GET):
            self.deal_static_file_request(path)

    def do_POST(self):
        path, param = self.parse_url_path(self.path)
        request_len = int(self.headers.get("Content-Length", 0))
        data = self.rfile.read(request_len)
        # todo: deal content data
        print(self.headers.get("Content-Type", None))
        param_more = {} if data is None else self.parse_parameter(bytes.decode(data))
        param.update(param_more)
        if not self.find_and_call_api_listener(path, param, Method.POST):
            self.send_error(HTTPStatus.NOT_FOUND)

    def do_HEAD(self):
        pass


class EasyServer(HTTPServer):
    listeners_dic = {}

    def __init__(self, port: int = 8090, address: str = "0.0.0.0"):
        super().__init__((address, port), EasyServerHandler)
        self.sessions = {}
        print("[%s] server start at %s:%s" % (datetime.datetime.now().ctime(), address, str(port)))

    @classmethod
    def addRequestListener(cls, path: str, methods: Sequence[Method], listener: RequestListener):
        path_params = tuple(re.findall("(:[^/]+)", path))
        for parm in path_params:
            path = path.replace(parm, "([^/]+)")
        if len(path_params) != 0:
            path = re.compile(path)
        cls.listeners_dic[path] = (listener, methods, path_params)


class Httpd(object):
    server = None

    @classmethod
    def start_serve(cls, port: int = 8090, address: str = "0.0.0.0", blocking=True):
        if cls.server is None:
            try:
                cls.server = EasyServer(port, address)
                if not blocking:
                    thread = threading.Thread(target=cls.server.serve_forever)
                    thread.start()
                    return thread
                else:
                    cls.server.serve_forever()
            except Exception as e:
                print(str(e))

    @classmethod
    def requestMapping(cls, path, methods=[m for m in Method], content_type="text/html; charset=utf-8"):
        def converter(listener: RequestListener):
            def new_listener(request, response):
                response.setContentType(content_type)
                return listener(request, response)

            EasyServer.addRequestListener(path, methods, new_listener)
            return new_listener

        return converter

    @classmethod
    def get(cls, path, content_type="text/html; charset=utf-8"):
        return cls.requestMapping(path, [Method.GET], content_type)

    @classmethod
    def post(cls, path, content_type="text/html; charset=utf-8"):
        return cls.requestMapping(path, [Method.POST], content_type)
