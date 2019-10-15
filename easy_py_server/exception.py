from .datastruct import HTTPStatus


# fixme:目前这个错回返回500？？
class IllegalAccessException(Exception):
    pass


class HttpException(Exception):
    def __init__(self, http_status, info=""):
        self.http_status = http_status
        self.info = info

    def __str__(self):
        return "HttpException: " + str(self.http_status) + " " + str(self.info)


class InternalException(HttpException):
    def __init__(self, error, info=""):
        HttpException.__init__(self, HTTPStatus.INTERNAL_SERVER_ERROR, info)
        self.error = error

    def __str__(self):
        return "InternalException: " + str(self.info) + "\n" + str(self.error)
