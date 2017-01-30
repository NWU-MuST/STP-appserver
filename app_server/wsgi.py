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
import math
import fcntl
import tempfile

from dispatcher import Dispatch
from service.httperrs import *

# Check binaries are installed
MP3SPLT="/usr/bin/mp3splt"; assert os.stat(MP3SPLT)
OGGENC="/usr/bin/oggenc"; assert os.stat(OGGENC)
OGGDEC="/usr/bin/oggdec"; assert os.stat(OGGDEC)
SOX="/usr/bin/sox"; assert(os.stat(SOX))

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

def fix_oggsplt_time(realtime):
    """ Convert seconds to weird MP3splt time format XX:XX:XX.XX
    """
    dt = datetime.timedelta(seconds=float(realtime))
    dts = str(dt)
    (hour, minute, second) = dts.split(":")
    minute = int(60.0 * float(hour) + float(minute))
    second = int(math.ceil(float(second)))
    return "{}.{}".format(minute, second)

# Cross domain access
ALLOW = [("Access-Control-Allow-Origin", "*"), ("Access-Control-Allow-Methods", "POST, PUT, GET, OPTIONS"),
        ("Access-Control-Allow-Headers", "Content-Type") ,("Access-Control-Max-Age", "86400"), ('Content-Type','application/json')]

#ENTRY POINT
def application(env, start_response):
    LOG.debug("Request: {}".format(env))
    try:
        if env['REQUEST_METHOD'] == 'GET':
            d = router.get(env)
            data = None
            response_header = []
            tmpin = tempfile.NamedTemporaryFile(delete=False)
            tmpin.close()
            tmpout = tempfile.NamedTemporaryFile(delete=False)
            tmpout.close()

            LOG.info("{}".format(d))
            if "audio" in d["mime"]: # Send back audio
                LOG.info(d["mime"])
                error = ""
                if "range" in d:
                    (start, end) = d['range']
                    start = fix_oggsplt_time(start)
                    end = fix_oggsplt_time(end)

                    mp3splt = subprocess.Popen((MP3SPLT, d["filename"], start, end, "-d", "/tmp", "-o", os.path.basename(tmpout.name)), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    mp3splt_stdo, mp3splt_stde = mp3splt.communicate()
                    LOG.info(mp3splt_stdo)
                    error = "{}{}".format(error, mp3splt_stde)

                    oggdec = subprocess.Popen((OGGDEC, "-o", tmpin.name, "{}.ogg".format(tmpout.name)), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    oggdec_stdo, oggdec_stde = oggdec.communicate()
                    LOG.info(oggdec_stdo)
                    error = "{}{}".format(error, oggdec_stde)
                    
                    sox = subprocess.Popen((SOX, "-t", "wav", tmpin.name, "-t", "wav", tmpout.name, "gain", "-n"), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    sox_stdo, sox_stde = sox.communicate()
                    LOG.info(sox_stdo)
                    error="{}{}".format(error, sox_stde)
                   
                    oggenc = subprocess.Popen((OGGENC, "-o", tmpin.name, tmpout.name), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    oggenc_stdo, oggenc_stde = oggenc.communicate()
                    LOG.info(oggenc_stdo)
                    error = "{}{}".format(error, oggenc_stde)

                    with open(tmpin.name, "rb") as f:
                        data = f.read()
                    os.remove("{}.ogg".format(tmpout.name))
                else:
                    oggdec = subprocess.Popen((OGGDEC, "-o", tmpin.name, d["filename"]), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    oggdec_stdo, oggdec_stde = oggdec.communicate()
                    LOG.info(oggdec_stdo)
                    error = "{}{}".format(error, oggdec_stde)

                    sox = subprocess.Popen((SOX, "-t", "wav", tmpin.name, "-t", "wav", tmpout.name, "gain", "-n"), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    sox_stdo, sox_stde = sox.communicate()
                    LOG.info(sox_stdo)
                    error="{}{}".format(error, sox_stde)

                    oggenc = subprocess.Popen((OGGENC, "-o", tmpin.name, tmpout.name), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    oggenc_stdo, oggenc_stde = oggenc.communicate()
                    LOG.info(oggenc_stdo)
                    error = "{}{}".format(error, oggenc_stde)

                    with open(tmpin.name, "rb") as f:
                        data = f.read()

                os.remove(tmpin.name)
                os.remove(tmpout.name)
                LOG.info(error)
                LOG.info(len(data))
                if error.lower().find('error:') != -1:
                    LOG.error(error)
                    raise RuntimeError("Cannot supply task's audio data!")
    
            else: # Send back MS-WORD document
                with open(d['filename'], 'rb') as infh:
                    data = infh.read()
                os.remove(d["filename"])
                response_header = [("Content-Disposition", 'attachment; filename="{}"'.format(d["savename"]))]

            response_header.extend([('Content-Type', str(d["mime"])), ('Content-Length', str(len(data)))])
            start_response('200 OK', response_header + ALLOW)
            return [data]

        elif env['REQUEST_METHOD'] == 'POST':
            d = router.post(env)
            response, response_header = build_json_response(d)
            start_response('200 OK', response_header + ALLOW)
            return [response]

        elif env['REQUEST_METHOD'] == 'PUT':
            d = router.put(env)
            response, response_header = build_json_response(d)
            start_response('200 OK', response_header + ALLOW)
            return [response]

        elif env['REQUEST_METHOD'] == 'OPTIONS':
            response_header = [("Access-Control-Allow-Origin", "*"), ("Access-Control-Allow-Methods", "POST, PUT, GET, OPTIONS"), 
            ("Access-Control-Allow-Headers", "Content-Type") ,("Access-Control-Max-Age", "86400")]
            start_response('200 OK', response_header)
            return []

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
