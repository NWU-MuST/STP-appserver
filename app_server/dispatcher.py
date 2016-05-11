#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import unicode_literals, division, print_function, with_statement #Py2

import json
import os
import codecs
import cgi
import cStringIO
from logger import Logger


class Dispatch:

    def __init__(self, config_file):
        self._config_file = config_file
        self._config = {}
        self._modules = {}
        self._module_config = {}
        self._routing = {}
        self._logger = None

    def load(self):
        """
            High-level services load
        """
        self.init_logger()
        self.load_config()
        self.clear_routing()
        self.load_handlers()

    def init_logger(self):
        """
            Create logger
        """
        if self._logger is None:
            self.__base_logger = Logger(self._config_file)
            self.__base_logger.new_logger('App')
            self._logger = self.__base_logger.get_logger('base')

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

        print(self._modules)
        print(self._module_config)
        print(self._routing)

    def get(self, env):
        """
            Process GET resquest.
            Valid requests are: results, status, options
        """
        uri = env['PATH_INFO']
        if uri not in self._routing['GET']:
            return '405 Method Not Allowed', json.dumps({'message' : 'GET does not support: %s' % uri})

        try:
            data = {}
            if len(env['QUERY_STRING']) != 0:
                data = cgi.parse_qs(env['QUERY_STRING'])

            for key in data:
                data[key] = data[key][0]

            for parameter in self._routing['GET'][uri]['parameters']:
                if parameter not in data:
                    return '400 Bad Request', json.dumps({'message' : 'missing parameter in request body: %s' % parameter})

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
                raise Exception("Internal Server Error: Bad result type from service method")
            return '200 OK', json.dumps(dispatch_result)

        except Exception as e:
            return '500 Internal Server Error', json.dumps({'message' : str(e)})

    def post(self, env):
        uri = env['PATH_INFO']
        if uri not in self._routing['POST']:
            return '405 Method Not Allowed', json.dumps({'message' : 'POST does not support: %s' % uri})
            
        try:
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
                print(data.keys())
            for parameter in self._routing['POST'][uri]['parameters']:
                if parameter not in data:
                    return '400 Bad Request', json.dumps({'message' : 'missing parameter in request body: %s' % parameter})

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
                raise Exception("Internal Server Error: Bad result type from service method")
            return '200 OK', json.dumps(dispatch_result)

        except Exception as e:
            return '400 Bad Request', json.dumps({'message' : str(e)})

    def shutdown(self):
        """
            Shutdown the router and message queue
        """
        pass

