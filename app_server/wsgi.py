#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import unicode_literals, division, print_function, with_statement #Py2

import sys
import os
import uwsgi
import json
from dispatcher import Dispatch

router = Dispatch(os.environ['services_config'])
router.load()

# Perform cleanup when server shutdown
def app_shutdown():
    print('Shutting down subsystem instance...')
    sys.stdout.flush()
    router.shutdown()

uwsgi.atexit = app_shutdown

# Entry point

#DEMIT: Need to revisit/review how Error Handling interacts with
#dispatcher.py methods (exceptions vs returns)
def application(env, start_response):
    print(env)
    if env['REQUEST_METHOD'] == 'GET':
        (status, response) = router.get(env)
        #DEMIT: Error handling is broken here, if the above does not
        #200 OK, then we fail with cryptic KeyError("filename") below:
        try:
            response = json.loads(response)
            f = open(response['filename'], 'rb')
            data = f.read()
            f.close()
            response_header = [('Content-Type', str(response["mime"])), ('Content-Length', str(len(data)))]
            start_response('200 OK', response_header)
            return [data]
        except Exception as e:
            response = json.dumps({'message' : repr(e)})
            response_header = [('Content-Type','application/json'), ('Content-Length', str(len(response)))]
            start_response('500 Internal Server Error', response_header)
            return [response]

    elif env['REQUEST_METHOD'] == 'POST':
        (status, response) = router.post(env)
        response_header = [('Content-Type','application/json'), ('Content-Length', str(len(response)))]
        start_response('200 OK', response_header)
        return [response]

    elif env['REQUEST_METHOD'] == 'PUT':
        (status, response) = router.put(env)
        response_header = [('Content-Type','application/json'), ('Content-Length', str(len(response)))]
        start_response('200 OK', response_header)
        return [response]

    else:
        msg = json.dumps({'message' : 'Error: use either GET, POST'})
        response_header = [('Content-Type','application/json'), ('Content-Length', str(len(msg)))]
        start_response('405 Method Not Allowed', response_header)
        return [msg]
