from http.server import HTTPServer, BaseHTTPRequestHandler, HTTPStatus
from typing import Optional, Callable, Dict, Any
import os, sys
import re
import uuid
import traceback
import urllib.parse

ERROR_MESSAGE_FORMAT = """
    <!DOCTYPE>
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


class IllegalAccessException(Exception):
    pass


class Request:
    def __init__(self, session: dict, param: dict):
        self._session = session
        self._param = param

    def getParam(self, key: str) -> str:
        value = self._param.get(key, None)
        if value is None:
            raise IllegalAccessException("Parameter '%s' is required" % (key,))
        return value

    def getSession(self, key) -> Optional[Any]:
        return self._session.get(key, None)

    def removeSession(self, key):
        self._session.pop(key, None)

    def setSession(self, key, value):
        self._session[key] = value


class Response:
    def __init__(self):
        self._content_type = "text/html; charset=utf-8"
        self._status = HTTPStatus.OK
        self._error_message = None

    def setContentType(self, content_type: str) -> None:
        self._content_type = content_type

    def getContentType(self) -> str:
        return self._content_type

    def setStatus(self, status: HTTPStatus):
        self._status = status

    def getStatus(self):
        return self._status

    def setStatusCode(self, code: int):
        self._status = HTTPStatus(code)

    def error(self, message: str, status=HTTPStatus.BAD_REQUEST):
        self._error_message = message
        self._status = status

    def getErrorMessage(self):
        return self._error_message


RequestListener = Callable[[Request, Response], Any]


class EasyServerHandler(BaseHTTPRequestHandler):
    server_version = "EasyServer"
    resource_dir = 'www/'  # !!! must with /
    SESSION_COOKIE_NAME = "EASY_SESSION_ID"
    error_message_format = ERROR_MESSAGE_FORMAT

    def version_string(self):
        return self.server_version

    def on_exception(self, e):
        e_str = ""
        if isinstance(e, IllegalAccessException):
            e_str = str(e)
        else:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            err_list = traceback.format_exception(exc_type, exc_value, exc_traceback, limit=5)
            for item in err_list:
                e_str += str(item)

        self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, "Internal Server Error", e_str)

    def find_and_call_api_listener(self, path: str, param: dict, listeners_dic):
        listener = listeners_dic.get((path,), None)
        if listener is None:
            for k in listeners_dic:
                match = re.fullmatch(k[0], path)
                if match is not None:
                    path_param_values = match.groups()
                    if len(path_param_values) == len(k) - 1:
                        for i in range(1, len(k)):
                            param[k[i]] = urllib.parse.unquote(path_param_values[i - 1])
                            listener = listeners_dic[k]
                        break
        if listener is not None:
            session = self.get_session()
            request = Request(session if session is not None else {}, param)
            response = Response()
            try:
                rtn = listener(request, response)
                # if error message is set, ignore any return content
                if response.getErrorMessage() is not None:
                    self.send_error(response.getStatus(), None, response.getErrorMessage())
                    return
                if type(rtn) == str:
                    content = rtn.encode("utf-8")
                elif type(rtn) == bytes:
                    content = rtn
                else:
                    content = bytes(rtn)
            except Exception as e:
                self.on_exception(e)
                return
            self.send_response(response.getStatus())
            self.send_header("Content-type", response.getContentType())
            self.send_header("Content-Length", len(content))
            if session is None:
                self.send_header("Set-Cookie", self.SESSION_COOKIE_NAME + "=" + str(uuid.uuid1()).replace("-", ""))
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
        if cookies[0] in self.server.sessions:
            return self.server.sessions[cookies[0]]
        else:
            return None

    @staticmethod
    def parse_parameter(src_str):
        param = {}
        for item in re.findall(r'(^|&)([a-zA-Z0-9_-]+)=([^&]*)', src_str):
            param[item[1]] = urllib.parse.unquote(item[2])
        return param

    def do_GET(self):
        # 解析并分离URL参数
        row = self.path.split('?')
        param = {} if len(row) < 2 else self.parse_parameter(row[1])
        path = row[0]
        # 首先尝试调用api listener, 如果没有对应的listener则认为是静态资源
        if not self.find_and_call_api_listener(path, param, self.server.get_listeners):
            # static resources
            path = self.resource_dir + path[1:]
            if len(path) == 0 or path[-1] == '/':
                indexes = ["index.html", "index.htm"]
                for index in indexes:
                    if os.path.isfile(path + index):
                        path += index
            if os.path.isdir(path):  # forbidden to access directors
                self.send_error(HTTPStatus.FORBIDDEN, "Request forbidden")
                return

            postfix = path.split('.')[-1].lower()
            default_type = 'application/octet-stream'
            content_type = default_type if len(postfix) == len(path) else extensions_map.get(postfix, default_type)
            try:
                f = open(path, 'rb')
            except OSError:
                self.send_error(HTTPStatus.NOT_FOUND, "Not found")
                return
            try:
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-type", content_type)
                fs = os.fstat(f.fileno())
                self.send_header("Content-Length", str(fs[6]))
                self.send_header("Last-Modified", self.date_time_string(fs.st_mtime))
                self.end_headers()
                while 1:
                    buf = f.read(1024 * 16)
                    if not buf:
                        break
                    self.wfile.write(buf)
                return
            except:
                self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, "Internal Server Error")
            finally:
                f.close()

    def do_POST(self):
        # 忽略'?'后的部分
        path = self.path.split('?')[0]
        request_len = int(self.headers.get("Content-Length", 0))
        data = self.rfile.read(request_len)
        param = {} if data is None else self.parse_parameter(bytes.decode(data))
        if not self.find_and_call_api_listener(path, param, self.server.post_listeners):
            self.send_error(HTTPStatus.BAD_REQUEST, "Bad Request")


class EasyServer(HTTPServer):
    def __init__(self, port: int = 8090, address: str = "localhost"):
        super().__init__((address, port), EasyServerHandler)
        self.get_listeners = {}
        self.post_listeners = {}
        self.sessions = {}
        print("Server start at " + address + ":" + str(port))

    def addGetListener(self, path, listener: RequestListener):
        """
        Set http method GET listener
        :param path:  binding url
        :param listener:  func(request: Request, response: Response)-> Any
        :return: self
        """
        path_params = tuple(re.findall("(:[^/]+)", path))
        for parm in path_params:
            path = path.replace(parm, "([^/]+)")
        self.get_listeners[(path,) + path_params] = listener
        return self

    def addPostListener(self, path, listener):
        """
        Set http method POST listener
        :param path:  binding url
        :param listener:  func(request: Request, response: Response)-> Any
        :return: self
        """
        path_params = tuple(re.findall("(:[^/]+)", path))
        for parm in path_params:
            path = path.replace(parm, "([^/]+)")
        self.post_listeners[(path,) + path_params] = listener
        return self

    def get(self, path, content_type="text/html; charset=utf-8"):
        def wrapper(listener: RequestListener):
            def new_listener(request, response):
                response.setContentType(content_type)
                return listener(request, response)

            self.addGetListener(path, new_listener)
            return new_listener

        return wrapper

    def post(self, path, content_type="text/html; charset=utf-8"):
        def wrapper(listener: RequestListener):
            def new_listener(request, response):
                response.setContentType(content_type)
                return listener(request, response)

            self.addPostListener(path, new_listener)
            return new_listener

        return wrapper


if __name__ == '__main__':
    httpd = EasyServer()
    httpd.addGetListener("/demo1", lambda request, response: "a=" + request.getParam('a'))


    @httpd.get("/api",content_type="application/json; charset=utf-8")
    def demo(req: Request, resp: Response):
        try:
            a = int(req.getParam("a"))
            b = int(req.getParam("b"))
        except ValueError:
            resp.error("parameter is not number")
            return None
        return "{\"success\":true, \"content\": %d + %d = %d}" % (a, b, a + b)


    @httpd.get("/student/:name")
    def demo(req: Request, resp: Response):
        name = req.getParam(":name")
        return "学生名字：" + name


    httpd.addGetListener("/demo2", demo)
    httpd.serve_forever()
