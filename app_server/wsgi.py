#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import unicode_literals, division, print_function, with_statement #Py2

import sys
import os
import uwsgi
import json
import logging
import logging.handlers

from dispatcher import Dispatch
from service.httperrs import *

#SETUP LOGGING

#The following ensures that we can override "funcName" when logging
# from wrapper functions, from:
# http://stackoverflow.com/questions/7003898/using-functools-wraps-with-a-logging-decorator
class CustomFormatter(logging.Formatter):
    """Custom formatter, overrides funcName with value of funcname if it
       exists
    """
    def format(self, record):
        if hasattr(record, 'funcname'):
            record.funcName = record.funcname
        return super(CustomFormatter, self).format(record)

LOGNAME = "APP"
LOGFNAME = os.path.join(os.getenv("PERSISTENT_FS"), "appserver.log")
LOGLEVEL = logging.DEBUG
try:
    fmt = "%(asctime)s [%(levelname)s] %(name)s in %(funcName)s(): %(message)s"
    LOG = logging.getLogger(LOGNAME)
    formatter = CustomFormatter(fmt)
    ofstream = logging.handlers.TimedRotatingFileHandler(LOGFNAME, when="D", interval=1, encoding="utf-8")
    ofstream.setFormatter(formatter)
    LOG.addHandler(ofstream)
    LOG.setLevel(LOGLEVEL)
    #If we want console output:
    # console = logging.StreamHandler()
    # console.setFormatter(formatter)
    # LOG.addHandler(console)
except Exception as e:
    print("FATAL ERROR: Could not create logging instance: {}".format(e), file=sys.stderr)
    sys.exit(1)

#SETUP ROUTER
router = Dispatch(os.environ['services_config'])
router.load()

#PERFORM CLEANUP WHEN SERVER SHUTDOWN
def app_shutdown():
    LOG.info('Shutting down subsystem instance...')
    sys.stdout.flush()
    router.shutdown()
uwsgi.atexit = app_shutdown

def build_json_response(data):
    if type(data) is dict:
        response = json.dumps(data)
    else:
        response = json.dumps({'message' : repr(data)})
    response_header = [('Content-Type','application/json'), ('Content-Length', str(len(response)))]
    return response, response_header

#ENTRY POINT
def application(env, start_response):
    LOG.debug("Request: {}".format(env))
    try:

        if env['REQUEST_METHOD'] == 'GET':
            d = router.get(env)
            with open(d['filename'], 'rb') as infh:
                data = infh.read()
            response_header = [('Content-Type', str(d["mime"])), ('Content-Length', str(len(data)))]
            start_response('200 OK', response_header)
            return [data]

        elif env['REQUEST_METHOD'] == 'POST':
            d = router.post(env)
            response, response_header = build_json_response(d)
            start_response('200 OK', response_header)
            return [response]

        elif env['REQUEST_METHOD'] == 'PUT':
            d = router.put(env)
            response, response_header = build_json_response(d)
            start_response('200 OK', response_header)
            return [response]

        else:
            raise MethodNotAllowedError("Supported methods are: GET, POST or PUT")

    except BadRequestError as e:
        response, response_header = build_json_response(e)
        start_response("400 Bad Request", response_header)
        return [response]
    except NotAuthorizedError as e:
        response, response_header = build_json_response(e)
        start_response("401 Not Authorized", response_header)
        return [response]
    except ForbiddenError as e:
        response, response_header = build_json_response(e)
        start_response("403 Forbidden", response_header)
        return [response]
    except NotFoundError as e:
        response, response_header = build_json_response(e)
        start_response("404 Not Found", response_header)
        return [response]
    except MethodNotAllowedError as e:
        response, response_header = build_json_response(e)
        start_response("405 Method Not Allowed", response_header)
        return [response]
    except ConflictError as e:
        response, response_header = build_json_response(e)
        start_response("409 Conflict", response_header)
        return [response]
    except TeapotError as e:
        response, response_header = build_json_response(e)
        start_response("418 I'm a teapot", response_header)
        return [response]
    except NotImplementedError as e:
        response, response_header = build_json_response(e)
        start_response("501 Not Implemented", response_header)
        return [response]
    except Exception as e:
        response, response_header = build_json_response(e)
        start_response("500 Internal Server Error", response_header)
        return [response]

