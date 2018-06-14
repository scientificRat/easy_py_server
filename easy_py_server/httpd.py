from .new_server import EasyServer
from .datastruct import *
import threading

__server = None


def start_serve(port: int = 8090, address: str = "0.0.0.0", blocking=True):
    global __server
    if __server is None:
        try:
            __server = EasyServer(port, address)
            if not blocking:
                thread = threading.Thread(target=__server.serve_forever)
                thread.start()
                return thread
            else:
                __server.serve_forever()
        except Exception as e:
            print(str(e))


def requestMapping(path, methods=[m for m in Method], content_type="text/html; charset=utf-8"):
    def converter(listener):
        EasyServer.addRequestListener(path, methods, listener)
        return listener

    return converter


def get(path, content_type="text/html; charset=utf-8"):
    return requestMapping(path, [Method.GET], content_type)


def post(path, content_type="text/html; charset=utf-8"):
    return requestMapping(path, [Method.POST], content_type)
