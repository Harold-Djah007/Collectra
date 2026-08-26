from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals
from django.http import Http404, HttpResponse
from django.conf import settings

from . import exceptions as x
from django.utils.deprecation import MiddlewareMixin


class NoExceptionsMiddleware(MiddlewareMixin):
    """
    Catch all subclasses of HttpException

    Will pass errors through in DEBUG mode so Django's error
    debug tools can be used.
    set LET_HTTP_EXCEPTIONS_500 to change this behavior
    """
    def process_exception(self, request, exception):
        if not isinstance(exception, x.BaseHttpException):
            return None
        if getattr(settings, 'LET_HTTP_EXCEPTIONS_500', settings.DEBUG):
            print("\t\t" + exception.render())
            return None
        return HttpResponse(
            exception.render(),
            status=exception.status,
        )

