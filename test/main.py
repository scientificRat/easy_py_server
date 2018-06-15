from easy_py_server import httpd, Request, Response
import json


@httpd.get("/api", content_type="application/json; charset=utf-8")
def demo(a: int, b: int):
    return json.dumps({"success": True, "content": "%d + %d = %d" % (a, b, a + b)})


@httpd.get("/student/:name")
def demo(name):
    return "学生名字：" + name


@httpd.get("/set/:curr")
def set(request: Request, curr):
    request.setSessionAttribute("curr", curr)
    return "set：" + str(curr)


@httpd.get("/q")
def q(request: Request):
    curr = request.getSessionAttribute("curr")
    return "get：" + str(curr)


@httpd.post("/w")
def w(t):
    return str(t)


if __name__ == '__main__':
    httpd.start_serve()
