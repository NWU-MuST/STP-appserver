#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import unicode_literals, division, print_function, with_statement #Py2

import sys
import os
import json
import requests
import logging

from httperrs import *

LOG = logging.getLogger("APP.SPEECH")
SPEECHSERVER = os.getenv("SPEECHSERVER"); assert SPEECHSERVER is not None

class Speech:

    def __init__(self, config_file):
        with open(config_file) as infh:
            self._config = json.loads(infh.read())

        self._username = self._config["speechserver"]["username"]
        self._password = self._config["speechserver"]["password"]
        self._loginurl = self._config["speechserver"]["login"]
        self._logouturl = self._config["speechserver"]["logout"]
        self._token = None

    def login(self):
        """
            Login to speech server
        """
        jobreq = {"username" : self._username, "password" : self._password}
        reqstatus = requests.post(os.path.join(SPEECHSERVER, self._loginurl), data=json.dumps(jobreq))
        LOG.debug("{}".format(reqstatus.text))
        reqstatus = reqstatus.json()
        if "token" not in reqstatus:
            LOG.debug("Could not log into speech server")
            raise BadRequestError("Cannot log into speech server")
        self._token = reqstatus["token"] 

    def logout(self):
        """
            Logout from speech server
        """
        if self._token is not None:
            jobreq = {"token" : self._token}
            reqstatus = requests.post(os.path.join(SPEECHSERVER, self._logouturl), data=json.dumps(jobreq))
            reqstatus = reqstatus.json()
        raise BadRequestError("Not logged into speech server")

    def token(self):
        if self._token is None:
            LOG.debug("No speech server token. Log in first!")
            raise NotAuthorizedError("No speech server login!")
        return self._token

