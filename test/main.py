from easy_py_server import Httpd, Request, Response


@Httpd.get("/api", content_type="application/json; charset=utf-8")
def demo(request, response):
    try:
        a = int(request.getParam("a"))
        b = int(request.getParam("b"))
    except ValueError:
        response.error("parameter is not number")
        return None
    return "{\"success\":true, \"content\": \"%d + %d = %d\"}" % (a, b, a + b)


@Httpd.get("/student/:name")
def demo(req: Request, resp: Response):
    name = req.getParam(":name")
    return "学生名字：" + name


@Httpd.get("/set/:curr")
def set(request, response):
    curr = request.getParam(":curr")
    request.setSessionAttribute("curr", curr)
    return "set：" + str(curr)


@Httpd.get("/q")
def q(request, response):
    curr = request.getSessionAttribute("curr")
    return "get：" + str(curr)


@Httpd.post("/w")
def w(request, response):
    t = request.getParam("t")
    return str(t)


Httpd.start_serve()
