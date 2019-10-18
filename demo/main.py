from easy_py_server import EasyPyServer, Request, Response, MultipartFile

httpd = EasyPyServer('0.0.0.0', 8090)


# method GET
@httpd.get("/api")
def demo(a: int, b: int):
    return dict(success=True, content="%d + %d = %d" % (a, b, a + b))


# method POST
@httpd.post("/post")
def post(key):
    return str(key)


# uploading file
@httpd.post("/multipart")
def post(save_name: str, file: MultipartFile):
    save_path = '{}.txt'.format(save_name)
    file.save(save_path)
    return dict(success=True, message="save to {}".format(save_path))


# path parameter
@httpd.get("/api/:id")
def demo(id):
    return 'api' + id


# set session
@httpd.get("/set/:data")
def set(request: Request, data):
    request.set_session_attribute("data", data)
    return "set: " + str(data)


# read session
@httpd.get("/query")
def query(request: Request):
    data = request.get_session_attribute("data")
    return "get: " + str(data)


# redirection
@httpd.get("/redirect")
def redirect():
    resp = Response()
    resp.set_redirection_url("/cat.jpg")
    return resp


if __name__ == '__main__':
    # start the server (default is blocking)
    httpd.start_serve(blocking=True)
