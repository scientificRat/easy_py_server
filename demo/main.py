from easy_py_server import EasyPyServer, Request, Response, MultipartFile

app = EasyPyServer('0.0.0.0', 8090, static_folder="www")


# method GET
@app.get("/api")
def demo(a: int, b: int):
    return dict(success=True, content="%d + %d = %d" % (a, b, a + b))


@app.get("/")
def demo_index(a: int):
    return a


# method POST
@app.post("/post")
def post(key):
    return str(key)


# uploading file
@app.post("/multipart")
def post(save_name: str, file: MultipartFile):
    save_path = '{}.txt'.format(save_name)
    file.save(save_path)
    return dict(success=True, message="save to {}".format(save_path))


# path parameter
@app.get("/api/:id")
def demo_path(id: int):
    return 'api' + id


@app.get("/sum_2/:a/and/:b")
def sum_2(a: int, b: int):
    return a + b


# set session
@app.get("/set/:data")
def set(request: Request, data):
    request.set_session_attribute("data", data)
    return "set: " + str(data)


# read session
@app.get("/query")
def query(request: Request):
    data = request.get_session_attribute("data")
    return "get: " + str(data)


# redirection
@app.get("/redirect")
def redirect():
    resp = Response()
    resp.set_redirection_url("/cat.jpg")
    return resp


if __name__ == '__main__':
    # start the server (default is blocking)
    app.run(blocking=False)
