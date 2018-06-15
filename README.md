# easy\_py\_server
> A easy and simple web framework for **Python3**

* You can simply integrate this server with you code **without** any installation or configuration
* Support `static resources`,`HTTP session`,`path parameter` ....
* Python decorator based API
* Easy to customize

## Get started
#### Environment
* python3

#### Install
```bash
pip3 install git+https://github.com/scientificRat/easy_py_server.git@new_version
```

#### Demo
```python
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


```


#### Create directory for static resources(Optional)
```bash
mkdir www
# ... add some files into this directory
```

#### Run and have fun :)
```bash
python3 your-source.py
# your 'www' directory should be in the same directory of 'your-source.py'
```

## Documentation

For normal usages you only need to known `httpd`, `class Method`, `class Request`,`class Response`
You can import them by

```python
from easy_py_server import httpd, Method, Request, Response
```
You can bind request by adding decorator `@requestMapping` before your bindding function definition

```python
@httpd.requestMapping(path="/path/to/your/api",methods=[Method.GET],content_type="text/plain")
def f(request:Request,response:Response):
    pass
```

You can bind `GET`/`POST` methods simply by adding `@get`/`@post` like it's shown  in the demo code

you can get request **parameters** and **session** by `Request` which is the first parameter of you binding function

.....unfinished

# Attention!
The author is lazy and only implement GET and POST method, you can give a pull request if you like :)

