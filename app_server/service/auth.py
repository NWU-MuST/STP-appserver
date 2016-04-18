#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import unicode_literals, division, print_function, with_statement #Py2

import json
import uuid

class Auth:

 	def __init__(self, config_file):
		self._config_file = config_file
		self.token = {}

	def addtoken(self, request):
		_tok = str(uuid.uuid4())
		self.token[request['name']] = _tok
		print(_tok, request['name'])
		return _tok

	def checktoken(self, request):
		print(request)
		print(self.token[request['name'][0]])
		return self.token[request['name'][0]]

