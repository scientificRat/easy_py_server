from easy_py_server import EasyPyServer, Request, Response, MultipartFile, ResponseFile

app = EasyPyServer('0.0.0.0', 8090, static_folder="www")


# method GET
@app.get("/api")
def demo(a: int, b: int):
    return dict(success=True, content="%d + %d = %d" % (a, b, a + b))


# method POST
@app.post("/post")
def post(key):
    return str(key)


# ajax json
@app.post("/ajax-json")
def json_request(r: Request):
    print(r.params)
    return "Got"


# uploading file
@app.post("/multipart")
def post(save_name: str, file: MultipartFile):
    save_path = '{}.txt'.format(save_name)
    file.save(save_path)
    return dict(success=True, message="save to {}".format(save_path))


# download file
@app.get("/download")
def download():
    with open("www/cat.jpg", 'rb') as f:
        all_bytes = f.read()
    return ResponseFile(all_bytes, filename="download_cat.jpg")


# path parameter
@app.get("/api/:id")
def demo_path(id: int):
    return 'api' + str(id)


@app.get("/sum_2/:a/and/:b")
def sum_2(a: int, b: int):
    return a + b


# same path, different methods
@app.get("/sum_3")
def sum_3_get(a: float, b: float, c: float):
    # dict object can be automatically converted to json string to response
    return dict(success=True, rst=(a + b + c), message="by get method")


@app.post("/sum_3")
def sum_3_post(a: float, b: float, c: float):
    # dict object can be automatically converted to json string to response
    return dict(success=True, rst=(a + b + c), message="by post method")


@app.get("/sum_many")
def sum_many(arr: list):
    return sum(arr)


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
    app.run(blocking=True)
