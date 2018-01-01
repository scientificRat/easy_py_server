# easy\_py\_server  
> A easy and simple web framework for **Python3**     

* You can simply integrate this server with you code **without** any installation or configuration  
* Support `static resources`,`HTTP session`,`path parameter` ....
* Python decorator based API  
* Easy to customize  

## Get started  
#### Environment
* python3

#### Download
```bash
git clone https://github.com/scientificRat/easy_py_server.git 
```
#### Demo
```python
from easy_py_server import Httpd
@Httpd.get("/api/test")
def test(request, response):
    a = request.getParam("a")
    return "parameter a = %s"%(a,)

# with path parameters
@Httpd.get("/api/:id")
def demo(request, response):
    id = request.getParam(":id")
    return "id = %s"%(id,)
    
@Httpd.get("/api", content_type="application/json; charset=utf-8")
def demo(request, response):
    try:
        a = int(request.getParam("a"))
        b = int(request.getParam("b"))
    except ValueError:
        response.error("parameter is not number")
        return None
    return "{\"success\":true, \"content\": %d + %d = %d}" % (a, b, a + b)
    
    
# start the server (default listen on port 8090) (blocking)
Httpd.start_serve()

```


#### Create director for static resources(Optional)  
```bash
mkdir www 
# ... add some files into this director
```

#### Run and have fun :)
```bash
python3 your-source.py
# your 'www' director should be in the same director of 'your-source.py' 
```

## Documentation

For normal usages you only need to known `class Httpd` , `class Method`, `class Request`,`class Response`
You can import them by   

```python
from easy_py_server import Httpd, Method, Request, Response
```
You can bind request by adding decorator `@requestMapping` before your bindding function definition

```python  
@Httpd.requestMapping(path="/path/to/your/api",methods=[Method.GET],content_type="text/plain")
def f(request,response):
    pass
```

You can bind `GET`/`POST` methods simply by adding `@get`/`@post` like it's shown  in the demo code

you can get request **parameters** and **session** by `Request` which is the first parameter of you binding function

.....unfinished

# Attention!
The author is lazy and only implement GET and POST method, you can give a pull request if you like :)

