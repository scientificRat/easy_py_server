from http.server import HTTPServer, BaseHTTPRequestHandler, HTTPStatus
import os
import sys
import re
import uuid
import traceback

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


class EasyServerHandler(BaseHTTPRequestHandler):
    server_version = "EasyServer"
    resource_dir = 'www/'  # !!! must with /
    SESSION_COOKIE_NAME = "EASY_SESSION_ID"
    error_message_format = ERROR_MESSAGE_FORMAT

    def version_string(self):
        return self.server_version

    def on_exception(self):
        exc_type, exc_value, exc_traceback = sys.exc_info()
        err_list = traceback.format_exception(exc_type, exc_value, exc_traceback, limit=5)
        e_str = ""
        for item in err_list:
            e_str += str(item)
        self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, "Internal Server Error", e_str)

    def find_and_call_api_listener(self, path, param, listeners_dic):
        if path in listeners_dic:
            session = self.get_session()
            try:
                response_type = listeners_dic[path][1]
                rtn = listeners_dic[path][0](session, param)
                if type(rtn) == str:
                    content = rtn.encode("utf-8")
                elif type(rtn) == bytes:
                    content = rtn
                else:
                    content = bytes(rtn)
            except:
                self.on_exception()
                return
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-type", response_type)
            self.send_header("Content-Length", len(content))
            if session is None:
                self.send_header("Set-Cookie", self.SESSION_COOKIE_NAME + "=" + str(uuid.uuid1()).replace("-", ""))
            self.end_headers()
            self.wfile.write(content)
            return True
        else:
            return False

    def get_session(self):
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
            param[item[1]] = item[2]
        return param

    def do_GET(self):
        # 解析并分离URL参数
        row = self.path.split('?')
        param = {} if len(row) < 2 else self.parse_parameter(row[1])
        path = row[0]  # split 结果无论如何有一个
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


class OnRequestListener:
    def __call__(self, session: dict, parameters: dict):
        pass


class EasyServer(HTTPServer):
    def __init__(self, address="localhost", port=8090):
        super().__init__((address, port), EasyServerHandler)
        self.get_listeners = {}
        self.post_listeners = {}
        self.sessions = {}

    def get(self, path, listener: OnRequestListener, response_type="text/html; charset=utf-8"):
        """
        :param path: response url
        :param listener:  func(session, param)  session and param are both dict type
        :param response_type: response header Content-type value
        :return: None
        """
        self.get_listeners[path] = listener, response_type

    def post(self, path, listener: OnRequestListener, response_type="text/html; charset=utf-8"):
        """
        :param path: response url
        :param listener:  func(session, param)  session and param are both dict type
        :param response_type: response header Content-type value
        :return: None
        """
        self.post_listeners[path] = listener, response_type


if __name__ == '__main__':
    httpd = EasyServer()
    httpd.get("/api/test", lambda session, param: "API1: " + param['a'])
    httpd.post("/api/test2", lambda session, param: "API2: " + param['b'])
    httpd.serve_forever()
