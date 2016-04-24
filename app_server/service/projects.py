#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function #Py2

import auth
import admin

from httperrs import *

class Admin(admin.Admin):
    pass

class Projects(auth.UserAuth):

    def create_project(self, request):
        #AUTHORISE REQUEST
        auth.token_auth(request["token"], self._config["authdb"])
        #EXECUTE REQUEST
        raise NotImplementedError

    def load_project(self, request):
        #AUTHORISE REQUEST
        auth.token_auth(request["token"], self._config["authdb"])
        #EXECUTE REQUEST
        raise NotImplementedError

    def save_project(self, request):
        #AUTHORISE REQUEST
        auth.token_auth(request["token"], self._config["authdb"])
        #EXECUTE REQUEST
        raise NotImplementedError
