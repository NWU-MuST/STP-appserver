#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import unicode_literals, division, print_function, with_statement #Py2

import sys
import os
import uwsgi
import json
import logging
import logging.handlers
import subprocess
import datetime

from dispatcher import Dispatch
from service.httperrs import *

#SETUP LOGGING
LOGNAME = "APP"
LOGFNAME = os.path.join(os.getenv("PERSISTENT_FS"), "appserver.log")
LOGLEVEL = logging.DEBUG
try:
    fmt = "%(asctime)s [%(levelname)s] %(name)s in %(funcName)s(): %(message)s"
    LOG = logging.getLogger(LOGNAME)
    formatter = logging.Formatter(fmt)
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

def fix_oggsplt_time(realtime):
    dt = datetime.timedelta(seconds=float(realtime))
    dts = str(dt)
    (hour, minute, second) = dts.split(":")
    minute = 60.0 * float(hour) + float(minute)
    second = float(second)
    return "{}.{}".format(minute, second)

#ENTRY POINT
def application(env, start_response):
    LOG.debug("Request: {}".format(env))
    try:

        if env['REQUEST_METHOD'] == 'GET':
            d = router.get(env)
            data = None
            if 'range' not in d:
                with open(d['filename'], 'rb') as infh:
                    data = infh.read()
            else:
                (start, end) = d['range']
                start = fix_oggsplt_time(start)
                end = fix_oggsplt_time(end)
                cmd = "oggsplt {} {} {} -o -".format(d["filename"], start, end)
                p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True)
                (child_stdout, child_stderr) = (p.stdout, p.stderr)
                data = child_stdout.read()
                err = child_stderr.read()
                if len(err) != 0:
                    LOG.error(err)
                    raise RuntimeError("Cannot supply task's audio data!")

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

