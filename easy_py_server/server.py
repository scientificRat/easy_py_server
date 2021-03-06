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
from http import HTTPStatus
from typing import (Tuple, Sequence, Callable)
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
    error_content_type = "text/html; charset=utf-8"
    error_message_format = """<!DOCTYPE html>
    <html>
        <head>
            <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
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
        'jpeg': 'image/jpeg', 'jpg': 'image/jpeg', 'jpe': 'image/jpeg', 'jfif': 'image/jpeg',
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
    DEFAULT_INDEX_FILES = ('index.html', 'index.htm')

    def __init__(self, conn_sock, client_address, server):
        # client_address : (ip, port)
        assert isinstance(server, EasyPyServer)
        self.server = server  # type: EasyPyServer
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
                if match is not None:
                    if method not in listeners_dic[k]:
                        raise HttpException(HTTPStatus.METHOD_NOT_ALLOWED)
                    path_param_values = match.groups()
                    _, params_key, _ = listeners_dic[k][method]
                    if len(path_param_values) == len(params_key):
                        for i in range(0, len(params_key)):
                            param[params_key[i]] = urllib.parse.unquote(path_param_values[i])
                        entity = listeners_dic[k]
                        break
        if entity is None:
            return None, None
        if method not in entity:
            raise HttpException(HTTPStatus.METHOD_NOT_ALLOWED)
        listener, _, response_config = entity[method]
        return listener, response_config

    def call_listener(self, listener, request: Request) -> Response:
        pass_param_list = self.generate_listener_parameters(listener, request)
        request_with_session = True if request.session is not None else False
        try:
            # call the listener
            rtn = listener(*pass_param_list)
            response = self.convert_rtn(rtn)
            session = request.get_session()
            if session is not None and len(session) > 0 and not request_with_session:
                # set new sessions
                session_cookie_str = self.create_new_session(session)
                response.set_cookie_str(session_cookie_str)
            return response
        except HttpException as e:
            raise e
        except Exception as e:
            raise WarpedInternalServerException(e)

    def make_response(self, response: Response, response_config: ResponseConfig):
        """
        Response to client according to `Response`
        :param response: Response object
        :param response_config: ResponseConfig which is set by add_listener
        :return: None
        """
        # if error message is set, ignore any return content
        if response.get_error_message() is not None:
            self.send_error(response.get_status(), None, response.get_error_message())
        else:
            self.send_response(response.get_status())
            # send customized headers
            for k, v in response.headers.items():
                self.send_header(k, v)
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
            self.send_header("Content-Length", str(len(content)))
            for cookie_str in response.get_cookie_str_list():
                self.send_header("Set-Cookie", cookie_str)
            for key, value in response.get_additional_headers().items():
                self.send_header(key, value)
            if response_config is not None and response_config.headers is not None:
                for key, value in response_config.headers.items():
                    self.send_header(key, value)
            self.end_headers()
            self.wfile.write(content)

    def make_response_on_exception(self, e):
        e = self.convert_exception(e)
        e_str = e.info
        if isinstance(e, WarpedInternalServerException):
            if e_str is None:
                e_str = ""
            e_str += "\n\n"
            if self.verbose_exception:
                # concat traceback error
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

    def _clean_expire_session(self, session_code):
        time.sleep(self.DEFAULT_SESSION_EXPIRE_SECONDS)
        self.server.sessions.pop(session_code)

    def create_new_session(self, session: dict) -> str:
        new_session_code = str(uuid.uuid1()).replace("-", "")
        while new_session_code in self.server.sessions:
            new_session_code = str(uuid.uuid1()).replace("-", "")

        # fixme: 开线程清理的做法可能不得当, 可以只用一个清理线程
        threading.Thread(target=self._clean_expire_session, args=(new_session_code,), daemon=True).start()
        self.server.sessions[new_session_code] = session
        expire_date = self.date_time_string(int(time.time()) + self.DEFAULT_SESSION_EXPIRE_SECONDS)
        session_cookie_str = self.SESSION_COOKIE_NAME + "=" + new_session_code + "; path=/; expires=" + expire_date
        return session_cookie_str

    def deal_static_file_request(self, path, response_config: ResponseConfig):
        if self.resource_dir is None:
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        # for security
        if len(re.findall(r'(/\.\./)', path)) != 0:
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        path = os.path.join(self.resource_dir, path[1:])
        if not os.path.exists(path):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if os.path.isdir(path):
            for index in self.DEFAULT_INDEX_FILES:
                new_path = os.path.join(path, index)
                if os.path.isfile(new_path) and os.path.exists(new_path):
                    path = new_path
                    break
        if os.path.isdir(path):
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        file_basename = os.path.basename(path)
        postfix = file_basename.split('.')[-1].lower()
        default_type = 'application/octet-stream'
        if response_config is not None and response_config.content_type is not None:
            content_type = response_config.content_type
        else:
            if len(postfix) == len(file_basename):
                content_type = default_type
            else:
                content_type = self.extensions_map.get(postfix, default_type)
        # read file
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
            self.send_header("Last-Modified", self.date_time_string(int(fs.st_mtime)))
            if response_config is not None and response_config.headers is not None:
                for key in response_config.headers:
                    self.send_header(key, str(response_config.headers[key]))
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
        body = self.rfile.read(request_len)  # type: bytes
        param_more = {}
        if request_type is not None:
            if re.match("application/x-www-form-urlencoded", request_type) is not None:
                # todo: 传入参数有嵌套时没能正确处理 例如k[m]=2
                param_more = self.parse_parameter(bytes.decode(body))
            elif re.match('application/json', request_type) is not None:
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
        raw_headers = self.headers  # type: HTTPMessage
        return Request(param, cookies, session, raw_headers)

    def default_response_process(self, method):
        try:
            path, param = self.parse_url_path(self.path)
            body, param_more = self.parse_request_body()
            param.update(param_more)
            listener, response_config = self.find_listener(path, param, method)
            if listener is None:
                raise HttpException(HTTPStatus.NOT_FOUND)
            else:
                request = self.construct_request_object(param)
                response = self.call_listener(listener, request)
                self.make_response(response, response_config)
        except Exception as e:
            print(traceback.format_exc())
            print(e)
            self.make_response_on_exception(e)

    def do_GET(self):
        try:
            # parse and separate request url
            path, param = self.parse_url_path(self.path)
            # find listener. request will be regarded as static resource if no listener existed
            listener, response_config = self.find_listener(path, param, Method.GET)
            if listener is None:
                self.deal_static_file_request(path, response_config)
            else:
                request = self.construct_request_object(param)
                response = self.call_listener(listener, request)
                self.make_response(response, response_config)
        except Exception as e:
            print(traceback.format_exc())
            print(e)
            self.make_response_on_exception(e)

    def do_POST(self):
        self.default_response_process(Method.POST)

    # fixme: should not be default, especially for static files
    def do_HEAD(self):
        self.default_response_process(Method.HEAD)

    def do_DELETE(self):
        self.default_response_process(Method.DELETE)

    def do_PUT(self):
        self.default_response_process(Method.PUT)

    def do_CONNECT(self):
        self.default_response_process(Method.CONNECT)

    def do_OPTIONS(self):
        self.default_response_process(Method.OPTIONS)

    def do_TRACE(self):
        self.default_response_process(Method.TRACE)

    def do_PATCH(self):
        self.default_response_process(Method.PATCH)

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

    def address_string(self):
        # return the Host property in request header
        # the super method returns the socket client IP which is not expected under a proxy request
        return self.headers.get("X-Real-IP", super(EasyServerHandler, self).address_string())

    def log(self, type, message, *args):
        rst = "[%s] %s - - [%s] %s" % (type, self.address_string(), self.log_date_time_string(), message % args)
        if type == 'error':
            rst = termcolor.colored(rst, color="red", attrs=["bold"])
        print(rst)

    @staticmethod
    def convert_exception(e) -> HttpException:
        if isinstance(e, HttpException):
            return e
        if isinstance(e, NotImplementedError):
            return HttpException(HTTPStatus.NOT_IMPLEMENTED, info=str(e))
        else:
            return WarpedInternalServerException(e)

    @staticmethod
    def parse_parameter(src_str):
        param = {}
        match = re.findall(r'(^|&)([^=]+)=([^&]*)', src_str)
        if len(match) > 0:
            for item in re.findall(r'(^|&)([^=]+)=([^&]*)', src_str):
                key = urllib.parse.unquote(item[1])
                value = urllib.parse.unquote(item[2])
                enforced_list_param = False
                # to deal with params like arr[]=10&arr[]=12&arr[]=15
                if len(key) > 2 and key[-2:] == '[]':
                    key = key[:-2]
                    enforced_list_param = True
                # to deal with params like arr=10&arr=12&arr=15
                if key in param:
                    if type(param[key]) == list:
                        param[key].append(value)
                    else:
                        param[key] = [param[key], value]
                else:
                    param[key] = value if not enforced_list_param else [value]
        else:
            try:
                param = json.loads(src_str)
            except json.JSONDecodeError as e:
                pass
        # make all the request param string
        for key in param:
            if type(param[key]) != str:
                param[key] = json.dumps(param[key])
        return param

    @staticmethod
    def parse_url_path(path) -> Tuple[str, Dict[str, str]]:
        row = path.split('?')
        path = row[0]
        if len(path) > 1 and path[-1] == '/':
            path = path[:-1]
        param = {} if len(row) < 2 else EasyServerHandler.parse_parameter(row[1])
        return urllib.parse.unquote(path), param

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
            # get value from request parameters
            if name not in request_param_dic:
                if ":" + name in request_param_dic:
                    value = request_param_dic[":" + name]
                elif parameter.default != inspect.Parameter.empty:
                    value = parameter.default
                else:
                    raise HttpException(HTTPStatus.UNPROCESSABLE_ENTITY, "parameter '%s' is required" % name)
            else:
                value = request_param_dic[name]
            # 根据参数annotation类型转换数据
            #   条件：有注解、value非None (None无法转换类型)
            if parameter.annotation != inspect.Parameter.empty and value is not None:
                tp = parameter.annotation
                try:
                    if tp == MultipartFile:
                        if not isinstance(value, MultipartFile):
                            # 不用转换，Request中的param 已经对文件转换为了MultipartFile，这里只需要检查一下类型
                            raise ValueError("parameter '%s' is required to be a Multipart file" % name)
                    elif tp in (dict, list):
                        value = json.loads(value)
                    elif tp == tuple:
                        value = tuple(json.loads(value))
                    elif tp == bool:
                        try:
                            # may be a list/dict/bool/int, 这样做是为了正确处理传入的true/false 1,0 这种字符串的bool值
                            possible_value = json.loads(value)
                        except json.JSONDecodeError as e:
                            possible_value = value
                        value = bool(possible_value)
                    else:
                        value = tp(value)  # force convert
                except Exception as e:
                    raise WarpedInternalServerException(e, "Type converting error")
            pass_param_list.append(value)
        return pass_param_list

    @staticmethod
    def convert_rtn(rtn) -> Response:
        # todo: 或许应该区分一个RawResponse和便于用户使用的Response（设置header，同时自动解析content）
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
        # auto content type inferring and response construction
        # todo: This should support customization
        if type(origin_content) == str:
            response.set_content(origin_content.encode('utf-8'))
            response.set_content_type("text/html; charset=utf-8")
        elif type(origin_content) in [dict, list, tuple]:
            response.set_content(json.dumps(origin_content, ensure_ascii=False).encode('utf-8'))
            response.set_content_type('application/json; charset=utf-8')
        elif type(origin_content) in [int, float, complex]:
            origin_content = str(origin_content)
            response.set_content(origin_content.encode('utf-8'))
            response.set_content_type("text/html; charset=utf-8")
        elif isinstance(origin_content, ImageFile):
            # PIL image
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
                 verbose_exception=True,
                 default_response_type="text/html; charset=utf-8",
                 http_request_handler=EasyServerHandler):
        self.server_app_name = server_app_name
        self.static_folder = os.path.abspath(static_folder)
        self.verbose_exception = verbose_exception
        if not os.path.exists(self.static_folder):
            print("[Warning] The setting static folder does not exist: {}".format(self.static_folder), file=sys.stderr)
            self.static_folder = None

        self.handler = http_request_handler  # be compatible with customized handler
        self.handler.server_name = self.server_app_name
        self.handler.resource_dir = self.static_folder
        self.handler.verbose_exception = self.verbose_exception

        self.listen_address = listen_address
        self.port = port
        self.sessions = {}
        self.listeners_dic = {}
        self.default_response_type = default_response_type
        super().__init__((listen_address, port), self.handler)

    def start_serve(self, blocking=True):
        if not blocking:
            thread = threading.Thread(target=self.serve_forever)
            thread.setDaemon(True)
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

    def server_close(self) -> None:
        super(EasyPyServer, self).server_close()
        # self._BaseServer__shutdown_request = True
        self.shutdown()

    def add_request_listener(self, path: str, methods: Sequence[Method], listener: Callable,
                             response_config: ResponseConfig = None):
        path_params = re.findall("(:[^/]+)", path)
        for parm in path_params:
            path = path.replace(parm, r"([\S]+)")
        if len(path_params) != 0:
            path = re.compile(path)
        if path in self.listeners_dic:
            for method in methods:
                self.listeners_dic[path][method] = listener, path_params, response_config
        else:
            self.listeners_dic[path] = {method: (listener, path_params, response_config) for method in methods}

    # decorators
    def route(self, path, methods=None, response_config=None):
        if methods is None:
            methods = [m for m in Method]

        def converter(listener):
            self.add_request_listener(path, methods, listener, response_config)
            return listener

        return converter

    def get(self, path, response_config=None):
        return self.route(path, [Method.GET], response_config)

    def post(self, path, response_config=None):
        return self.route(path, [Method.POST], response_config)
