#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" A subset of HTTP errors for use in the platform modules/dispatcher.
"""
from __future__ import unicode_literals, division, print_function #Py2

class BadRequestError(Exception):
    """ Intended to map to "HTTP 400 Bad Request"
    """
    pass

class NotAuthorizedError(Exception):
    """ Intended to map to "HTTP 401 Not Authorized"
    """
    pass

class ForbiddenError(Exception):
    """ Intended to map tox "HTTP 403 Forbidden"
    """
    pass

class NotFoundError(Exception):
    """ Intended to map to "HTTP 404 Not Found"
    """
    pass

class MethodNotAllowedError(Exception):
    """ Intended to map to "HTTP 405 Method Not Allowed"
    """
    pass

class ConflictError(Exception):
    """ Intended to map to "HTTP 409 Conflict"
    """
    pass

class TeapotError(Exception):
    """ Intended to map to "HTTP 418 I'm a teapot"
    """
    pass

