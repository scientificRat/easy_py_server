from easy_py_server import httpd, Request, Response, MultipartFile


# get method
@httpd.get("/api")
def demo(a: int, b: int):
    return dict(success=True, content="%d + %d = %d" % (a, b, a + b))


# path parameter
@httpd.get("/api/:id")
def demo(id):
    return 'api' + id


# set session
@httpd.get("/set/:data")
def set(request: Request, data):
    request.setSessionAttribute("data", data)
    return "set: " + str(data)


# read session
@httpd.get("/query")
def query(request: Request):
    data = request.getSessionAttribute("data")
    return "get: " + str(data)


# post method
@httpd.post("/post")
def post(key):
    return str(key)


# post multipart file
@httpd.post("/multipart")
def post(save_name: str, file: MultipartFile):
    save_path = '{}.txt'.format(save_name)
    file.save(save_path)
    return dict(success=True, message="save to {}".format(save_path))


if __name__ == '__main__':
    # start the server (default listen on port 8090) (blocking)
    Response.DEFAULT_CONTENT_TYPE = "application/json; charset=utf-8"
    httpd.start_serve()
