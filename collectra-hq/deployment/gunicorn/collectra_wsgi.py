"""Collectra WSGI entry point with support for chunked mobile submissions."""

from io import BytesIO

from deployment.gunicorn.commcarehq_wsgi import (
    application as commcarehq_application,
)


class BufferChunkedRequestBody:
    """Supply CONTENT_LENGTH after Gunicorn decodes a chunked request."""

    body_methods = {"POST", "PUT", "PATCH"}

    def __init__(self, application):
        self.application = application

    def __call__(self, environ, start_response):
        method = environ.get("REQUEST_METHOD", "").upper()

        if method in self.body_methods and not environ.get("CONTENT_LENGTH"):
            body = environ["wsgi.input"].read()
            environ["wsgi.input"] = BytesIO(body)
            environ["CONTENT_LENGTH"] = str(len(body))
            environ.pop("HTTP_TRANSFER_ENCODING", None)

        return self.application(environ, start_response)


application = BufferChunkedRequestBody(commcarehq_application)

# Serve Django static assets during local demos and temporary tunnels.
from django.contrib.staticfiles.handlers import StaticFilesHandler
application = StaticFilesHandler(application)
