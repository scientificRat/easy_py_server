import datetime
import inspect
import io
import json
import os
import re
import sys
import threading
import time
import traceback
import urllib.parse
import uuid
import termcolor
from http.server import (HTTPServer, BaseHTTPRequestHandler)
from typing import (Tuple, Sequence)
from socketserver import ThreadingMixIn
from PIL.ImageFile import ImageFile
from .datastruct import *
from .exception import *
from easy_py_server import __version__


class EasyServerHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_name = "EasyPyServer"
    server_version = server_name + "/" + __version__
    resource_dir = None  # static file folder
    verbose_exception = True
    error_message_format = """<!DOCTYPE html>
    <html>
        <head>
            <meta http-equiv="Content-Type" content="text/html;charset=utf-8">
            <title>Error Page</title>
        </head>
        <body style='font-family:sans-serif'>
            <h1 style='background: #646;color:#fff;margin: 0px;padding: 10px;font-family: cursive,sans-serif;'>EasyPyServer</h1>
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

    def __init__(self, conn_sock, client_address, server):
        # client_address : (ip, port)
        assert isinstance(server, EasyPyServer)
        self.server: EasyPyServer = server
        super().__init__(conn_sock, client_address, server)

    def version_string(self):
        return self.server_version

    @classmethod
    def set_server_name(cls, name):
        cls.server_name = name

    @classmethod
    def set_resource_dir(cls, resource_dir):
        cls.resource_dir = resource_dir

    @classmethod
    def set_error_format(cls, template):
        cls.error_message_format = template

    def find_listener(self, path: str, param: dict, method: Method):
        listeners_dic = self.server.listeners_dic
        entity = listeners_dic.get(path, None)
        # if has path parameters, the key will be the regular expression not the raw path
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
            return None
        listener, methods, _ = entity
        if listener is not None:
            if method not in methods:
                raise HttpException(HTTPStatus.METHOD_NOT_ALLOWED)
        return listener

    def call_listener(self, listener, request: Request) -> Response:
        pass_param_list = self.generate_listener_parameters(listener, request)
        request_with_session = True if request.session is not None else False
        try:
            # call the listener
            rtn = listener(*pass_param_list)
            response = self.convert_rtn(rtn)
            session = request.get_session()
            if session is not None and not request_with_session:
                # set new sessions
                session_cookie_str = self.create_new_session(session)
                response.set_cookie_str(session_cookie_str)
            return response
        except HttpException as e:
            raise e
        except Exception as e:
            raise WarpedInternalServerException(e)

    def make_response(self, response: Response):
        # if error message is set, ignore any return content
        if response.get_error_message() is not None:
            self.send_error(response.get_status(), None, response.get_error_message())
        else:
            self.send_response(response.get_status())
            if response.get_status() == HTTPStatus.PERMANENT_REDIRECT:
                self.send_header("Location", response.get_redirection_url())
                self.end_headers()
                return
            # send response with content
            content_type = response.get_content_type()
            if content_type is None:
                content_type = self.server.default_response_type
            self.send_header("Content-type", content_type)
            content = response.get_content()
            if content is None:
                content = b""
            self.send_header("Content-Length", len(content))
            for cookie_str in response.get_cookie_str_list():
                self.send_header("Set-Cookie", cookie_str)
            for key, value in response.get_additional_headers().items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(content)

    def make_response_on_exception(self, e):
        e: HttpException = self.cvt_exception(e)
        e_str = e.info
        if isinstance(e, WarpedInternalServerException):
            e_str += "\n\n"
            exc_type, exc_value, exc_traceback = sys.exc_info()
            err_list = traceback.format_exception(exc_type, exc_value, exc_traceback, limit=5)
            for item in err_list:
                e_str += str(item)
        self.send_error(e.http_status, None, e_str)

    def get_session(self, cookies) -> Optional[dict]:
        if cookies is not None and self.SESSION_COOKIE_NAME in cookies:
            return self.server.sessions.get(cookies[self.SESSION_COOKIE_NAME], None)

    def get_cookie(self) -> Optional[dict]:
        cookie_str = self.headers.get('Cookie', "")
        match = re.findall(r"([\S]*)=([\S]*)(;|$)", cookie_str)
        cookie_dict = {}
        for key, value, _ in match:
            cookie_dict[key] = value
        return cookie_dict

    def create_new_session(self, session: dict) -> str:
        new_session_code = str(uuid.uuid1()).replace("-", "")
        while new_session_code in self.server.sessions:
            new_session_code = str(uuid.uuid1()).replace("-", "")

        def clean_expire_session():
            time.sleep(self.DEFAULT_SESSION_EXPIRE_SECONDS)
            self.server.sessions.pop(new_session_code)

        threading.Thread(target=clean_expire_session).start()
        self.server.sessions[new_session_code] = session
        expire_date = self.date_time_string(time.time() + self.DEFAULT_SESSION_EXPIRE_SECONDS)
        session_cookie_str = self.SESSION_COOKIE_NAME + "=" + new_session_code + "; path=/; expires=" + expire_date
        return session_cookie_str

    def deal_static_file_request(self, path):
        if self.resource_dir is None:
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        path = os.path.join(self.resource_dir, path[1:])
        # for security
        if len(re.findall(r'(/\.\./)', path)) != 0:
            self.send_error(HTTPStatus.FORBIDDEN)
            return
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

    def parse_request_body(self):
        request_len = int(self.headers.get("Content-Length", 0))
        request_type = self.headers.get("Content-Type", None)
        body: bytes = self.rfile.read(request_len)
        param_more = {}
        if request_type is not None:
            if re.match("application/x-www-form-urlencoded", request_type) is not None:
                param_more = self.parse_parameter(bytes.decode(body))
            elif re.match("multipart/form-data", request_type) is not None:
                boundary = re.findall(r'boundary=([\S]+)', request_type)
                if len(boundary) == 1:
                    boundary = ("--{}".format(boundary[0])).encode()
                    param_more_raw = self.parse_multipart_form_data(body, boundary)
                    for name, (filename, content_type, data) in param_more_raw.items():
                        if filename is None:
                            param_more[name] = data
                        else:
                            param_more[name] = MultipartFile(filename, content_type, data)
                else:
                    raise NotImplementedError("Unsupported request type: %s" % request_type)
        return body, param_more

    def construct_request_object(self, param) -> Request:
        cookies = self.get_cookie()
        session = self.get_session(cookies)
        raw_headers: HTTPMessage = self.headers
        return Request(param, cookies, session, raw_headers)

    def default_response_process(self, method):
        try:
            path, param = self.parse_url_path(self.path)
            body, param_more = self.parse_request_body()
            param.update(param_more)
            listener = self.find_listener(path, param, method)
            if listener is None:
                raise HttpException(HTTPStatus.NOT_FOUND)
            else:
                request = self.construct_request_object(param)
                response = self.call_listener(listener, request)
                self.make_response(response)
        except Exception as e:
            self.make_response_on_exception(e)

    def do_GET(self):
        try:
            # parse and separate request url
            path, param = self.parse_url_path(self.path)
            # find listener. request will be regarded as static resource if no listener existed
            listener = self.find_listener(path, param, Method.GET)
            if listener is None:
                self.deal_static_file_request(path)
            else:
                request = self.construct_request_object(param)
                response = self.call_listener(listener, request)
                self.make_response(response)
        except Exception as e:
            self.make_response_on_exception(e)

    def do_POST(self):
        self.default_response_process(Method.POST)

    # fixme: should not be default, especially for static files
    def do_HEAD(self):
        self.default_response_process(Method.POST)

    def do_DELETE(self):
        self.default_response_process(Method.POST)

    def do_PUT(self):
        self.default_response_process(Method.POST)

    def do_CONNECT(self):
        self.default_response_process(Method.POST)

    def do_OPTIONS(self):
        self.default_response_process(Method.POST)

    def do_TRACE(self):
        self.default_response_process(Method.POST)

    def do_PATCH(self):
        self.default_response_process(Method.POST)

    def log_request(self, code="-", size="-"):
        # copy from werkzeug
        try:
            path = urllib.parse.unquote(self.path)
            msg = "%s %s %s" % (self.command, path, self.request_version)
        except AttributeError:
            # path isn't set if the requestline was bad
            msg = self.requestline
        code = str(int(code))
        color = termcolor.colored
        if code[0] == "1":  # 1xx - Informational
            msg = color(msg, attrs=["bold"])
        elif code[0] == "2":  # 2xx - Success
            msg = color(msg, color="white")
        elif code == "304":  # 304 - Resource Not Modified
            msg = color(msg, color="cyan")
        elif code[0] == "3":  # 3xx - Redirection
            msg = color(msg, color="green")
        elif code == "404":  # 404 - Resource Not Found
            msg = color(msg, color="yellow")
        elif code[0] == "4":  # 4xx - Client Error
            msg = color(msg, color="red", attrs=["bold"])
        else:  # 5xx, or any other response
            msg = color(msg, color="magenta", attrs=["bold"])
        self.log("info", '"%s" %s %s', msg, code, size)

    def log_error(self, *args):
        self.log("error", *args)

    def log_message(self, format, *args):
        self.log("info", format, *args)

    def log(self, type, message, *args):
        print(
            "[%s] %s - - [%s] %s"
            % (type, self.address_string(), self.log_date_time_string(), message % args),
        )

    @staticmethod
    def cvt_exception(e) -> HttpException:
        if isinstance(e, HttpException):
            return e
        if isinstance(e, NotImplementedError):
            return HttpException(HTTPStatus.NOT_IMPLEMENTED, info=str(e))
        else:
            return WarpedInternalServerException(e)

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

    @staticmethod
    def parse_multipart_form_data(body: bytes, boundary: bytes):
        """
        Parse multipart/form-data
        :param body: body in bytes
        :param boundary: boundary string in bytes
        :return: DICT { parm_name: (filename, content_type, data) }
        """
        end = body.rfind(b'--\r\n')
        if end > 0 and len(body) - end == 4:
            #  remove tail
            body = body[:end]
        parts = body.split(boundary)
        rst = {}
        for part in parts:
            if len(part) == 0:
                continue
            splits = part.split(b'\r\n\r\n')
            assert len(splits) == 2
            head, data = splits
            data = data[:-2]  # remove \r\n
            # parse name
            match = re.findall(br'name="([\S]+)"', head)
            name = urllib.parse.unquote(match[0].decode())
            # parse filename
            filename = None
            match = re.findall(br'filename="([\S ]+)"', head)
            if len(match) > 0:
                filename = urllib.parse.unquote(match[0].decode())
            # parse Content-Type
            content_type = None
            if filename is not None:
                match = re.findall(br'Content-Type: ([\S]+)$|;', head)
                if len(match) > 0:
                    content_type = match[0]
            if filename is None:
                data = urllib.parse.unquote(data.decode())
            rst[name] = (filename, content_type, data)
        return rst

    @staticmethod
    def generate_listener_parameters(listener, request: Request):
        pass_param_list = []
        request_param_dic = request.params
        for name, parameter in inspect.signature(listener).parameters.items():
            # special objects
            # TODO: I hope to add `httpSession` `Cookies` objects, Request is not convenient
            if parameter.annotation == Request:
                pass_param_list.append(request)
                continue
            elif parameter.annotation == Response:
                pass_param_list.append(Response())  # empty response
            # request parameters
            if name not in request_param_dic:
                if ":" + name in request_param_dic:
                    value = request_param_dic[":" + name]
                elif parameter.default != inspect.Parameter.empty:
                    value = parameter.default
                else:
                    raise HttpException(HTTPStatus.UNPROCESSABLE_ENTITY, "parameter '%s' is required" % name)
            else:
                value = request_param_dic[name]
            if parameter.annotation != inspect.Parameter.empty:
                tp = parameter.annotation
                try:
                    if tp == MultipartFile:
                        pass
                    elif tp == dict:
                        value = json.loads(value)
                    else:
                        value = tp(value)  # force convert
                except Exception as e:
                    raise WarpedInternalServerException(e, "Type converting error")
            pass_param_list.append(value)
        return pass_param_list

    @staticmethod
    def convert_rtn(rtn) -> Response:
        if isinstance(rtn, Response):
            redirect_url = rtn.get_redirection_url()
            if redirect_url is not None:
                rtn = Response()
                rtn.set_status(HTTPStatus.PERMANENT_REDIRECT)  # 308 PERMANENT REDIRECT
                rtn.set_redirection_url(redirect_url)
            return rtn
        response = Response()
        response.set_content(rtn)
        origin_content = response.get_content()
        # TODO: Identify video object and so on
        if type(origin_content) == str:
            response.set_content(origin_content.encode('utf-8'))
            response.set_content_type("text/html; charset=utf-8")
        elif type(origin_content) == dict:
            response.set_content(json.dumps(origin_content, ensure_ascii=False).encode('utf-8'))
            response.set_content_type('application/json; charset=utf-8')
        elif isinstance(origin_content, ImageFile):
            img_byte_array = io.BytesIO()
            origin_content.save(img_byte_array, format=origin_content.format)
            response.set_content(img_byte_array.getvalue())
            response.set_content_type(origin_content.get_format_mimetype())
        elif type(origin_content) == bytes or origin_content is None:
            response.set_content_type('application/octet-stream')
        else:
            response.set_content(bytes(origin_content))
        return response


class EasyPyServer(ThreadingMixIn, HTTPServer):

    def __init__(self, listen_address: str = "0.0.0.0", port: int = 8090,
                 server_app_name="EasyPyServer",
                 static_folder="www",
                 default_response_type="text/html; charset=utf-8",
                 handler=EasyServerHandler):
        self.server_app_name = server_app_name
        self.static_folder = os.path.abspath(static_folder)
        if not os.path.exists(self.static_folder):
            self.static_folder = None
            print("[Warning] The setting static folder does not exist: {}".format(self.static_folder), file=sys.stderr)
        handler.server_name = self.server_app_name
        handler.resource_dir = self.static_folder

        self.listen_address = listen_address
        self.port = port
        self.handler = handler
        self.sessions = {}
        self.listeners_dic = {}
        self.default_response_type = default_response_type
        super().__init__((listen_address, port), handler)

    def start_serve(self, blocking=True):
        if not blocking:
            thread = threading.Thread(target=self.serve_forever)
            thread.start()
            return thread
        else:
            self.serve_forever()

    def run(self, blocking=True):
        self.start_serve(blocking)

    def serve_forever(self, poll_interval=0.5):
        print("[%s] server running on http://%s:%d" % (
            datetime.datetime.now().ctime(), self.listen_address, self.port))
        super(EasyPyServer, self).serve_forever()

    def add_request_listener(self, path: str, methods: Sequence[Method], listener):
        path_params = re.findall("(:[^/]+)", path)
        for parm in path_params:
            path = path.replace(parm, r"([\S]+)")
        if len(path_params) != 0:
            path = re.compile(path)
        self.listeners_dic[path] = (listener, methods, path_params)

    # decorators
    def route(self, path, methods=None):
        if methods is None:
            methods = [m for m in Method]

        def converter(listener):
            self.add_request_listener(path, methods, listener)
            return listener

        return converter

    def get(self, path):
        return self.route(path, [Method.GET])

    def post(self, path):
        return self.route(path, [Method.POST])
