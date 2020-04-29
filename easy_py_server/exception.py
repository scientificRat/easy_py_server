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


class WarpedInternalServerException(HttpException):
    def __init__(self, original_error, overwrite_info=None):
        if isinstance(original_error, WarpedInternalServerException):
            self.error = original_error.error
        else:
            self.error = original_error
        if overwrite_info is None:
            overwrite_info = str(self.error)
        self.info = overwrite_info
        HttpException.__init__(self, HTTPStatus.INTERNAL_SERVER_ERROR, self.info)

    def __str__(self):
        return "InternalServerException: \n" + str(self.info)
