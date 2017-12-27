from http.server import HTTPServer, BaseHTTPRequestHandler, HTTPStatus
import os


class EasyServerHandler(BaseHTTPRequestHandler):
    server_version = "EasyServer"
    resource_dir = 'www'
    error_message_format = """\
    <!DOCTYPE>
    <html>
        <head>
            <meta http-equiv="Content-Type" content="text/html;charset=utf-8">
            <title>Error Page</title>
        </head>
        <body>
            <h1>%(code)d %(message)s</h1>
            <p>Error code explanation:%(code)s --- %(explain)s.</p>
        </body>
    </html>
    """

    def version_string(self):
        return self.server_version

    def send_raw_content(self, content):
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-type", 'text/html')
        self.send_header("Content-Length", len(content))
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self):
        listeners_dic = self.server.get_listeners

        if self.path in listeners_dic:
            self.send_raw_content(listeners_dic[self.path]().encode('utf-8'))
        else:
            # static resources
            path = self.resource_dir + self.path
            if path == '/':
                path = ''
            if len(path) == 0 or path[-1] == '/':
                indexes = ["index.html", "index.htm"]
                for index in indexes:
                    if os.path.isfile(path + index):
                        path += index
            if os.path.isdir(path):  # forbidden to access director
                self.send_error(HTTPStatus.FORBIDDEN, "Request forbidden")
                return
            extensions_map = {
                'py': 'text/plain', 'c': 'text/plain', 'h': 'text/plain', 'cpp': 'text/plain',
                'html': 'text/html', 'htm': 'text/html',
                'jpeg': 'image/jpeg', 'jpg': 'image/jpeg',
                'gif': 'image/gif',
                'png': 'image/png',
                'svg': 'image/svg+xml',
                'css': 'text/css',
                'js': 'application/javascript',
                'json': 'application/json'
            }
            postfix = path.split('.')[-1].lower()
            ctype = 'text/plain'
            if len(postfix) != len(path):
                if postfix in extensions_map:
                    ctype = extensions_map[postfix]
            try:
                f = open(path, 'rb')
            except OSError:
                self.send_error(HTTPStatus.NOT_FOUND, "Not found")
                return
            try:
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-type", ctype)
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
        listeners_dic = self.server.get_listeners
        if self.path in listeners_dic:
            self.send_raw_content(listeners_dic[self.path]().encode('utf-8'))
        else:
            self.send_error(HTTPStatus.BAD_REQUEST, "Bad Request")


class EasyServer(HTTPServer):
    def __init__(self, server_address, RequestHandlerClass):
        super().__init__(server_address, RequestHandlerClass)
        self.get_listeners = {}
        self.post_listeners = {}

    def addGETListener(self, path, listener):
        self.get_listeners[path] = listener

    def addPOSTListener(self, path, listener):
        self.post_listeners[path] = listener


if __name__ == '__main__':
    httpd = EasyServer(('127.0.0.1', 8090), EasyServerHandler)
    httpd.serve_forever()
