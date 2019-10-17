# easy\_py\_server

> A flexible web server plugin providing a robust HTTP service for your projects.

* Flexible to integrate with your existing code **without** any configuration file or environ settings.
* Spring MCV like parameter injection implemented by python decorator: `@post`, `@get` and etc.
* Easy to manage `static resources`,`session`, `cookies`, `path parameter`, `redirection`, `file uploading` and etc.
* A single process multiple threads server framework that allows you share objects in your code.
* Easy to customize, writen in pure python

## Get started
#### Environment
* python3

#### Install
```bash
pip3 install git+https://github.com/scientificRat/easy_py_server.git
```

#### Demo
```python
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
    request.set_session_attribute("data", data)
    return "set: " + str(data)


# read session
@httpd.get("/query")
def query(request: Request):
    data = request.get_session_attribute("data")
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


# redirection
@httpd.get("/redirect")
def redirect():
    resp = Response()
    resp.set_redirection_url("/cat.jpg")
    return resp


if __name__ == '__main__':
    # start the server (default listen on port 8090) (blocking)
    Response.DEFAULT_CONTENT_TYPE = "application/json; charset=utf-8"
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

### Bind Service 

You can bind a service by adding decorator `@requestMapping`, `@get`, `@post` before your function definition. Feel free
 to use these decorators, they will register your functions as service callback without changing the definition 
 of your original code.
Decorator `@requestMapping` has a full support for different methods, 
```python
@httpd.requestMapping(path="/path/to/your/api", methods=[Method.GET])
def f(request: Request):
    return Response()
```
You can bind `GET`/`POST` methods with a simpler `@get`/`@post` like it's shown in the demo code:
```python
@httpd.get("/api")
def demo(a: int, b: int):
    return dict(success=True, content="%d + %d = %d" % (a, b, a + b))
```

### Parameter Injection

Parameters such as a, b and request shown above can be automatically injected when your service is called.
They will be parsed from your http request with the same names as your variables. For instance, you can 
access `demo` function shown above by visiting the following url: 
```text
http://<your-server-address>:<port>/api?a=1&b=12
```
The value of a, i.e. 1 and the value of b will be passed to your service function when this url is visited.

#### Specify Types
The parameters will be interpreted as `string` object by default. You can change this behavior by specify the 
type and then these parameters will be automatically converted to your desired types.

#### Access session and cookies
They are encapsulated inside the `Request` object, so you can get them by getting a `Request` object first.
This object is defined in `datastruct.py`, you can check it for more details by yourself.
```python
@httpd.get("/")
def index(req: Request):
    req.get_session()
    req.set_cookie()
    return None
```

### Automatic Response Construction
You can return a python object without explicitly constructing `Response` object.

* dict -> json
* string -> text
* PIL -> image

# Attention !
* No supporting for `ipv6` and `https`, they'll come soon.  
* With potential security issues.
