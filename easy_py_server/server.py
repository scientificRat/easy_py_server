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
from http.server import (HTTPServer, BaseHTTPRequestHandler)
from typing import (Tuple, Sequence)
from PIL.ImageFile import ImageFile
from .datastruct import *
from .exception import *
from easy_py_server import __version__


class EasyServerHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "EasyServer/" + __version__
    resource_dir = 'www/'
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

    def version_string(self):
        return self.server_version

    def handle(self):
        """
        override to support http1.1
        `while loop` may course blocking (which is not allowed in select/poll IO model)
        """
        self.close_connection = True
        self.handle_one_request()

    def on_internal_exception(self, e):
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

    # fixme: I need a better function name
    def generate_pass_parameter_list(self, listener, session, request_param_dic):
        request, response = None, None
        pass_param_list = []
        for name, parameter in inspect.signature(listener).parameters.items():
            # session and something
            if parameter.annotation == Request:
                request = Request(session, request_param_dic)
                pass_param_list.append(request)
                continue
            # TODO: I hope to add `httpSession`
            # request parameters
            if name not in request_param_dic:
                if ":" + name in request_param_dic:
                    value = request_param_dic[":" + name]
                elif parameter.default != inspect.Parameter.empty:
                    value = parameter.default
                else:
                    raise HttpException(HTTPStatus.BAD_REQUEST, "parameter '%s' is required" % name)
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
                        value = tp(value)
                except Exception as e:
                    raise InternalException(e, "type converting error")
            pass_param_list.append(value)
        return pass_param_list, request

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

    def call_listener(self, listener, param):
        session = self.get_session()
        current_none_session = session is None
        pass_param_list, request = self.generate_pass_parameter_list(listener, session, param)
        try:
            # call the listener
            rtn = listener(*pass_param_list)
            response = self.convert_rtn(rtn)
            if current_none_session and request is not None and request.getSession() is not None:
                response.setNewSession(request.getSession())
            return response
        except HttpException as e:
            raise e
        except Exception as e:
            raise InternalException(e)

    def convert_rtn(self, rtn):
        if type(rtn) == Response:
            return rtn
        response = Response()
        response.setContent(rtn)
        origin_content = response.getContent()
        # TODO: Identify json object, video object and so on
        if type(origin_content) == str:
            response.setContent(origin_content.encode('utf-8'))
        elif type(origin_content) == dict:
            response.setContent(json.dumps(origin_content, ensure_ascii=False).encode('utf-8'))
            response.setContentType('application/json; charset=utf-8')
        elif isinstance(origin_content, ImageFile):
            img_byte_array = io.BytesIO()
            origin_content.save(img_byte_array, format=origin_content.format)
            response.setContent(img_byte_array.getvalue())
            response.setContentType(origin_content.get_format_mimetype())
        elif type(origin_content) == bytes or origin_content is None:
            response.setContentType('application/octet-stream')
        else:
            response.setContent(bytes(origin_content))
        return response

    def make_response(self, response: Response):
        # if error message is set, ignore any return content
        if response.getErrorMessage() is not None:
            self.send_error(response.getStatus(), None, response.getErrorMessage())
        else:
            self.send_response(response.getStatus())
            self.send_header("Content-type", response.getContentType())
            self.send_header("Content-Length", len(response.getContent()))
            if response.getNewSession() is not None:
                self.set_new_session_cookie(response.getNewSession())
            self.end_headers()
            self.wfile.write(response.getContent())

    def deal_http_exception(self, e):
        if isinstance(e, InternalException):
            self.on_internal_exception(e)
        else:
            self.send_error(e.http_status, None, e.info)

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
        # for security
        if len(re.findall('(/../)', path)) != 0:
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
            match = re.findall(br'filename="([\S]+)"', head)
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
                    raise NotImplementedError("Wrong request head")
        return body, param_more

    def default_response_process(self, method):
        path, param = self.parse_url_path(self.path)
        body, param_more = self.parse_request_body()
        param.update(param_more)
        try:
            listener = self.find_listener(path, param, method)
            if listener is None:
                raise HttpException(HTTPStatus.NOT_FOUND)
            else:
                response = self.call_listener(listener, param)
                self.make_response(response)
        except HttpException as e:
            self.deal_http_exception(e)

    def do_GET(self):
        # parse and separate request url
        path, param = self.parse_url_path(self.path)
        # find listener. request will be regarded as static resource if no listener existed
        try:
            listener = self.find_listener(path, param, Method.GET)
            if listener is None:
                self.deal_static_file_request(path)
            else:
                response = self.call_listener(listener, param)
                self.make_response(response)
        except HttpException as e:
            self.deal_http_exception(e)

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


class EasyServer(HTTPServer):
    listeners_dic = {}

    def __init__(self, port: int = 8090, address: str = "0.0.0.0"):
        super().__init__((address, port), EasyServerHandler)
        self.sessions = {}
        print("[%s] server start at %s:%s" % (datetime.datetime.now().ctime(), address, str(port)))

    @classmethod
    def addRequestListener(cls, path: str, methods: Sequence[Method], listener):
        path_params = re.findall("(:[^/]+)", path)
        for parm in path_params:
            path = path.replace(parm, r"([\S]+)")
        if len(path_params) != 0:
            path = re.compile(path)
        cls.listeners_dic[path] = (listener, methods, path_params)
