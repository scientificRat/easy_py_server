# easy\_py\_server

[![PyPI version](https://badge.fury.io/py/easy-py-server.svg)](https://badge.fury.io/py/easy-py-server)

> A flexible microframework providing reliable HTTP service for your projects.

* Easy to make HTTP services by pure python.
* Flexible to integrate with your existing code **without** any configuration file or environ settings.
* Spring MCV like parameter injection implemented by python decorator: `@post`, `@get` etc.
* Easy to manage `static resources`,`session`, `cookies`, `path parameter`, `redirection`, `file uploading` etc.
* A single process multiple threads server framework that allows you share objects in your code.
* Easy to customize. `easy-py-server` is written in pure python for easy debugging and customizing.

## Get started
### Environment
* python >= 3.5

### Install
stable version:
```bash
pip3 install easy-py-server
```
working version:
```bash
pip3 install git+https://github.com/scientificRat/easy_py_server.git
```

### Demo 

```python
from easy_py_server import EasyPyServer, Request, Response, MultipartFile, ResponseFile, ResponseConfig

eps = EasyPyServer('0.0.0.0', 8090, static_folder="www")


# method GET
@eps.get("/api")
def demo(a: int, b: int):
    return dict(success=True, content="%d + %d = %d" % (a, b, a + b))


# method POST
@eps.post("/post")
def post(key):
    return str(key)


# ajax json
@eps.post("/ajax-json")
def json_request(r: Request):
    print(r.params)
    return "Got"


# 自定义header
@eps.post("/cross", ResponseConfig(headers={'Access-Control-Allow-Origin': '*'}))
def cross_access():
    return "post allow"


# 自定义header
@eps.get("/cross", ResponseConfig(headers={'Access-Control-Allow-Origin': '*'}))
def cross_access_get():
    return "get allow"


# uploading file
@eps.post("/multipart")
def post(save_name: str, file: MultipartFile):
    save_path = '{}.txt'.format(save_name)
    file.save(save_path)
    return dict(success=True, message="save to {}".format(save_path))


# download file
@eps.get("/download")
def download():
    with open("www/cat.jpg", 'rb') as f:
        all_bytes = f.read()
    return ResponseFile(all_bytes, filename="download_cat.jpg")


# path parameter
@eps.get("/api/:id")
def demo_path(id: int):
    return 'api' + str(id)


@eps.get("/sum_2/:a/and/:b")
def sum_2(a: int, b: int):
    return a + b


# same path, different methods
@eps.get("/sum_3")
def sum_3_get(a: float, b: float, c: float):
    # dict object can be automatically converted to json string to response
    return dict(success=True, rst=(a + b + c), message="by get method")


@eps.post("/sum_3")
def sum_3_post(a: float, b: float, c: float):
    # dict object can be automatically converted to json string to response
    return dict(success=True, rst=(a + b + c), message="by post method")


@eps.get("/sum_many")
def sum_many(arr: list):
    return sum(arr)


# set session
@eps.get("/set/:data")
def set(request: Request, data):
    request.set_session_attribute("data", data)
    return "set: " + str(data)


# read session
@eps.get("/query")
def query(request: Request):
    data = request.get_session_attribute("data")
    return "get: " + str(data)


# redirection
@eps.get("/redirect")
def redirect():
    resp = Response()
    resp.set_redirection_url("/cat.jpg")
    return resp


if __name__ == '__main__':
    # start the server (default is blocking)
    eps.run(blocking=True)

```

### Create directory for static resources(Optional)
```bash
mkdir www
# ... add some files into this directory
```

### Run and have fun :)
```bash
python3 your-source.py
# your 'www' directory should be in the same directory of 'your-source.py'
```

## Documentation

For normal usages, you only need to know `class EasyPyServer`, `class Method`, `class Request`,`class Response`, `class ResponseConfig`
.You can easily import them by
```python
from easy_py_server import EasyPyServer, Method, Request, Response, ResponseConfig
```

### Creating Server
```python
from easy_py_server import EasyPyServer
# create 
eps = EasyPyServer(listen_address="0.0.0.0", port=8090)
# run
eps.start_serve(blocking=True)
```

### Registering Service 

You can register a service by adding a decorator such as `@route`, `@get`, `@post`  to your function. Feel free
 to use these decorators, they will register your functions as callback without changing the original code of your definition. Among them, decorator `@route` has full support for different methods: 

```python
@eps.route(path="/path/to/your/api", methods=[Method.GET])
def f(request: Request):
    return Response()
```
You can bind `GET`/`POST` methods with a simpler `@get`/`@post` like it's shown in the demo code:
```python
@eps.get("/api")
def demo(a: int, b: int):
    return dict(success=True, content="%d + %d = %d" % (a, b, a + b))
```
You can use the decorators to specify the response's `Content-Type` or customize headers. For example, you can set  `Access-Control-Allow-Origin: *` to enable cross site accessing.
```python
@eps.post("/cross", ResponseConfig(headers={'Access-Control-Allow-Origin': '*'}))
def cross_access():
    return "post allow"
```

> note: Decorators are the recommended way to register your service, but you can also
> use the naive <server object>.add_request_listener() to do it. 


```python
from easy_py_server import EasyPyServer, Method
def func():
    pass
httpd = EasyPyServer()
httpd.add_request_listener("/",[Method.GET],func)

```
### Parameter Injection

Parameters such as `a`, `b` and `request` shown above can be automatically injected to your service function when it is requested.
These parameters will be parsed from the HTTP request depending on the names of your variables. For instance, you can 
access `demo` function (shown above) and inject parameters `a` and `b`  by visiting the URL: 
```text
http://<your-server-address>:<port>/api?a=1&b=12
```
The value of parameter `a` will be parsed as 1 and as 12 for `b`.

#### Specifying Types
The parameters will be interpreted as `string` object by default. You can change this behavior by specifying explict 
types to make them automatically converted to your desired types.
```python
# post multipart file
@httpd.post("/multipart")
def post(save_name: str, file: MultipartFile):
    save_path = '{}.txt'.format(save_name)
    file.save(save_path)
    return dict(success=True, message="save to {}".format(save_path))
```
#### Special types
* `Request`: http request object, encapsulating  `session`, `parameters` ,`cookies`
* `MultipartFile`: supporting for uploading files.

#### Access session and cookies
They are encapsulated inside the `Request` object, so you can get them by getting a `Request` object first. It's defined in `datastruct.py`, you can check this file for more details.
```python
@httpd.get("/")
def index(req: Request):
    req.get_session()
    req.set_cookie()
    return None
```

### Automatic Response Construction
You can return a python object without explicitly constructing `Response` object. They'll be automatically converted a correct HTTP response to the client. The supporting objects are listed as following:

* dict -> json
* string -> text
* PIL -> image
* bytes -> octet-stream
* other -> octet-stream

As an example, you can easily return a PIL image:
```python
from PIL import Image
@httpd.get("/show_image")
def show_image(image_path: str):
    try:
        img = Image.open(image_path, mode='r')
    except IOError as e:
        return None
    return img
```


## More
* Supporting for `ipv6` and `https` will come soon.  
