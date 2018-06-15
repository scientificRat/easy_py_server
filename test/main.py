from easy_py_server import httpd, Request, Response
import json


# get method
@httpd.get("/api", content_type="application/json; charset=utf-8")
def demo(a: int, b: int):
    return json.dumps({"success": True, "content": "%d + %d = %d" % (a, b, a + b)})


# path parameter
@httpd.get("/api/:id")
def demo(id):
    return 'api ' + id


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


if __name__ == '__main__':
    # start the server (default listen on port 8090) (blocking)
    httpd.start_serve()
