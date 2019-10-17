from .datastruct import HTTPStatus


class HttpException(Exception):
    def __init__(self, http_status, info=""):
        self.http_status = http_status
        self.info = info

    def __str__(self):
        return "HttpException: " + str(self.http_status) + " " + str(self.info)


class IllegalAccessException(HttpException):
    def __init__(self, error):
        HttpException.__init__(self, HTTPStatus.UNPROCESSABLE_ENTITY, error)


class InternalServerException(HttpException):
    def __init__(self, error, info=""):
        HttpException.__init__(self, HTTPStatus.INTERNAL_SERVER_ERROR, info)
        self.error = error

    def __str__(self):
        return "InternalException: " + str(self.info) + "\n" + str(self.error)
