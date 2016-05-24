#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import unicode_literals, division, print_function, with_statement #Py2

import json
import os
import codecs
import cgi
import cStringIO
import logging

from service.httperrs import *

LOG = logging.getLogger("APP.DISPATCHER")

class Dispatch:

    def __init__(self, config_file):
        self._config_file = config_file
        self._config = {}
        self._modules = {}
        self._module_config = {}
        self._routing = {}

    def load(self):
        """
            High-level services load
        """
        LOG.info("Loading router...")
        self.load_config()
        self.clear_routing()
        self.load_handlers()

    def _parse_module_name(self, module_handle):
        """
            Parse class name -> path, python file, class name
            path.file.Class -> path, file, Class
        """
        items = module_handle.split('.')
        class_name = items.pop()
        module_path = '.'.join(items)
        return module_path, class_name

    def load_config(self):
        """
            Load config containing dispatch details
        """
        self._config = {}
        with codecs.open(self._config_file, 'r', 'utf-8') as f:
            self._config = json.load(f)

    def clear_routing(self):
        """
            Clear the routing table i.e. services redirecting
        """
        if not self._routing:
            for handler in self._routing:
                del self._routing[handler]
        self._routing = {}

    def load_handlers(self):
        """
            Load hooks to handlers
        """
        for modu in self._config['MODULES']:
            path, name = self._parse_module_name(modu)
            _temp = __import__(path, fromlist=[name])
            self._modules[modu] = getattr(_temp, name)
            self._module_config[modu] = self._config['MODULES'][modu]

        for http_method in self._config['HANDLERS']:
            self._routing[http_method] = {}
            for uri in self._config['HANDLERS'][http_method]:
                modu, method = self._parse_module_name(self._config['HANDLERS'][http_method][uri]['method'])
                _data = {'module' : modu, 'method' : method, 'parameters' : self._config['HANDLERS'][http_method][uri]['parameters']}
                self._routing[http_method][uri] = _data

        LOG.debug("Router modules: {}".format(self._modules))
        LOG.debug("Router module config: {}".format(self._module_config))
        LOG.debug("Router table: {}".format(self._routing))

    def get(self, env):
        """
            Process GET request.
            Valid requests are: results, status, options
        """
        data = {}
        if len(env['QUERY_STRING']) != 0:
            data = cgi.parse_qs(env['QUERY_STRING'])
        for key in data:
            data[key] = data[key][0]

        uri = env['PATH_INFO']
        if uri not in self._routing['GET']:
            uri = os.path.basename(uri)
            #Check whether this is a GET on a temporary "outgoing"
            #URL.
            #DEMIT: Ideally want base URL to determine module
            #instead of this for-loop, but will have to fix such a
            #convention on URL somewhere -- in config JSON?
            for modu in self._config["TEMPIO_MODULES"]:
                module_hook = self._modules[modu]
                module_config = self._module_config[modu]
                module = module_hook(module_config)
                try:
                    return module.outgoing(uri)
                except MethodNotAllowedError:
                    pass #raise below if all modules fail...
            raise MethodNotAllowedError("GET does not support: {}".format(uri))
        else:
            for parameter in self._routing['GET'][uri]['parameters']:
                if parameter not in data:
                    raise BadRequestError('missing parameter in request body: %s' % parameter)

            module_name = self._routing['GET'][uri]['module']
            module_config = self._module_config[module_name]
            module_hook = self._modules[module_name]

            module = module_hook(module_config)
            method = getattr(module, self._routing['GET'][uri]['method'])

            dispatch_result = dict()
            result = method(data)
            if type(result) in [str, unicode]:
                dispatch_result["message"] = result
            elif type(result) is dict:
                dispatch_result.update(result)
            else:
                raise Exception("Bad result type from service method")
            return dispatch_result

    def post(self, env):
        uri = env['PATH_INFO']
        if uri not in self._routing['POST']:
            raise MethodNotAllowedError('POST does not support: %s' % uri)
            
        data = {}
        if 'multipart/form-data' not in env['CONTENT_TYPE']:
            data = json.loads(env['wsgi.input'].read(int(env['CONTENT_LENGTH'])))
        else:
            (header, bound) = env['CONTENT_TYPE'].split('boundary=')
            request_body_size = int(env.get('CONTENT_LENGTH', 0))
            request_body = env['wsgi.input'].read(request_body_size)
            form_raw = cgi.parse_multipart(cStringIO.StringIO(request_body), {'boundary': bound})
            for key in form_raw.keys():
                data[key] = form_raw[key][0]
            LOG.debug("Data keys: {}".format(data.keys()))
        for parameter in self._routing['POST'][uri]['parameters']:
            if parameter not in data:
                raise BadRequestError('missing parameter in request body: %s' % parameter)

        module_name = self._routing['POST'][uri]['module']
        module_config = self._module_config[module_name]
        module_hook = self._modules[module_name]

        module = module_hook(module_config)
        method = getattr(module, self._routing['POST'][uri]['method'])

        dispatch_result = dict()
        result = method(data)
        if type(result) in [str, unicode]:
            dispatch_result["message"] = result
        elif type(result) is dict:
            dispatch_result.update(result)
        else:
            raise Exception("Bad result type from service method")
        return dispatch_result

    def put(self, env):
        """ Process PUT resquest.
        """
        #DEMIT: Refactor the following block? Almost exact copy of "post" method.
        data = {}
        if 'multipart/form-data' not in env['CONTENT_TYPE']:
            data = json.loads(env['wsgi.input'].read(int(env['CONTENT_LENGTH'])))
        else:
            (header, bound) = env['CONTENT_TYPE'].split('boundary=')
            request_body_size = int(env.get('CONTENT_LENGTH', 0))
            request_body = env['wsgi.input'].read(request_body_size)
            form_raw = cgi.parse_multipart(cStringIO.StringIO(request_body), {'boundary': bound})
            for key in form_raw.keys():
                data[key] = form_raw[key][0]
            LOG.debug("Data keys: {}".format(data.keys()))

        uri = env['PATH_INFO']
        if uri not in self._routing['PUT']:
            uri = os.path.basename(uri)
            #Check whether this is a PUT on a temporary "outgoing"
            #URL. Ideally want base URL to determine module
            #instead of this for-loop, but will have to fix such a
            #convention on URL somewhere -- in config JSON?
            for modu in self._config["TEMPIO_MODULES"]:
                module_hook = self._modules[modu]
                module_config = self._module_config[modu]
                module = module_hook(module_config)
                try:
                    return module.incoming(uri, data)
                except MethodNotAllowedError:
                    pass #raise below if all modules fail...
            raise MethodNotAllowedError('PUT does not support: %s' % uri)

        else:
            #DEMIT: Refactor the following blocks? Almost exact copy of "post" method.
            for parameter in self._routing['PUT'][uri]['parameters']:
                if parameter not in data:
                    raise BadRequestError('missing parameter in request body: %s' % parameter)

            module_name = self._routing['PUT'][uri]['module']
            module_config = self._module_config[module_name]
            module_hook = self._modules[module_name]

            module = module_hook(module_config)
            method = getattr(module, self._routing['PUT'][uri]['method'])

            dispatch_result = dict()
            result = method(data)
            if type(result) in [str, unicode]:
                dispatch_result["message"] = result
            elif type(result) is dict:
                dispatch_result.update(result)
            else:
                raise Exception("Bad result type from service method")
            return dispatch_result
