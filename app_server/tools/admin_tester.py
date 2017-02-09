#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function #Py2

import requests
import sys
import json
import os
import readline
import string
import random
import math
import logging
import logging.handlers
import shutil
import codecs
import threading
import time

# Some constants
BASEURL = "http://127.0.0.1:9999/wsgi/"
USERNO = 2
RANDOM_WAIT_LOW = 0.2
RANDOM_WAIT_HIGH = 0.3

# Readline modes
readline.parse_and_bind('tab: complete')
readline.parse_and_bind('set editing-mode vi')

# Format the logger output
class CustomFormatter(logging.Formatter):
    """Custom formatter, overrides funcName with value of funcname if it
       exists
    """
    def format(self, record):
        if hasattr(record, 'funcname'):
            record.funcName = record.funcname
        return super(CustomFormatter, self).format(record)

# Editor testing logging
LOGNAME = "ADMINTEST"
LOGFNAME = "admin_tester.log"
LOGLEVEL = logging.DEBUG
try:
    fmt = "%(asctime)s [%(levelname)s] %(name)s in %(funcName)s(): %(message)s"
    LOG = logging.getLogger(LOGNAME)
    formatter = CustomFormatter(fmt)
    ofstream = logging.handlers.TimedRotatingFileHandler(LOGFNAME, when="D", interval=1, encoding="utf-8")
    ofstream.setFormatter(formatter)
    LOG.addHandler(ofstream)
    LOG.setLevel(LOGLEVEL)
except Exception as e:
    print("FATAL ERROR: Could not create logging instance: {}".format(e), file=sys.stderr)
    sys.exit(1)

# authdb.py generate password
def gen_pw(length=7):
    alphabet = string.ascii_letters + string.digits + '!@#$%^&*()'
    return "".join(random.choice(alphabet) for i in range(length))

def gen_str(length=5):
    alphabet = string.ascii_letters
    return "".join(random.choice(alphabet) for i in range(length))

# Thin project implementation
class Admin:

    def __init__(self):
        self.user_token = None
        self.admin_token = None
        self.username = "john"
        self.password = "doe"
        self.custom_text_file = "customlm.txt"
        self.projectid = None

    def adminlin(self):
        """
            Login as admin
            Place admin 'token' in self.admin_token
        """
        if self.admin_token is None:
            LOG.info("Admin logging in")
            headers = {"Content-Type" : "application/json"}
            data = {"username": "root", "password": "123456", "role" : "admin"}
            res = requests.post(BASEURL + "admin/login", headers=headers, data=json.dumps(data))
            LOG.info('adminlin(): SERVER SAYS:{}'.format(res.text))
            print('adminlin(): SERVER SAYS:{}'.format(res.text))
            LOG.info(res.status_code)
            pkg = res.json()
            self.admin_token = pkg['token']
        else:
            LOG.info("Admin logged in already!")

    def adminlout(self):
        """
            Logout as admin
        """
        if self.admin_token is not None:
            LOG.info("Admin logging out")
            headers = {"Content-Type" : "application/json"}
            data = {"token": self.admin_token}
            res = requests.post(BASEURL + "admin/logout", headers=headers, data=json.dumps(data))
            LOG.info('adminlout(): SERVER SAYS:{}'.format(res.text))
            print('adminlout(): SERVER SAYS:{}'.format(res.text))
            self.admin_token = None
        else:
            LOG.info("Admin not logged in!")

    def adduser(self):
        """
            Add automatically generated users to database
        """
        if self.admin_token is not None:
            LOG.info("Adding user {}".format(self.username))
            headers = {"Content-Type" : "application/json"}
            data = {"token": self.admin_token, "username": self.username, "password": self.password,
             "name": "John", "surname": "Doe", "email": "john@doe.com", "role": "admin"}
            res = requests.post(BASEURL + "admin/adduser", headers=headers, data=json.dumps(data))
            LOG.info('adduser(): SERVER SAYS:{}'.format(res.text))
            print('adduser(): SERVER SAYS:{}'.format(res.text))
            LOG.info(res.status_code)
        else:
            LOG.info("Admin not logged in!")

    def login(self):
        """
            Login as admin user
        """
        if self.user_token is None:
            LOG.info("Admin logging in")
            headers = {"Content-Type" : "application/json"}
            data = {"username": self.username, "password": self.password, "role" : "admin"}
            res = requests.post(BASEURL + "admin/login", headers=headers, data=json.dumps(data))
            LOG.info('login(): SERVER SAYS:{}'.format(res.text))
            print('login(): SERVER SAYS:{}'.format(res.text))
            LOG.info(res.status_code)
            pkg = res.json()
            self.user_token = pkg['token']
        else:
            LOG.info("User logged in already!")

    def logout(self):
        """
            Logout as admin user
        """
        if self.user_token is not None:
            LOG.info("Admin logging out")
            headers = {"Content-Type" : "application/json"}
            data = {"token": self.admin_token}
            res = requests.post(BASEURL + "admin/logout", headers=headers, data=json.dumps(data))
            LOG.info('logout(): SERVER SAYS:{}'.format(res.text))
            print('logout(): SERVER SAYS:{}'.format(res.text))
            self.admin_token = None
        else:
            LOG.info("User not logged in!")

    def logout2(self):
        """
            Use logout2 to remove token
        """
        LOG.info("Admin logout2")
        headers = {"Content-Type" : "application/json"}
        data = {"username": self.username, "password": self.password, "role" : "admin"}
        res = requests.post(BASEURL + "admin/logout2", headers=headers, data=json.dumps(data))
        LOG.info('logout2(): SERVER SAYS: {}'.format(res.text))
        print('logout2(): SERVER SAYS:', res.text)
        LOG.info(res.status_code)
        self.user_token = None

    def customlm(self):
        """
            Upload text to create a custom LM
            Requires customlm.txt to be located in current location
        """
        if not os.path.exists(self.custom_text_file):
            LOG.error('Cannot run CUSTOMLM as "{}" does not exist in current path'.format(self.custom_text_file))
            return

        if self.admin_token is not None:
            files = {'file' : open(self.custom_text_file, 'rb'), 'filename' : self.custom_text_file, 'token' : self.admin_token, 'name' : gen_str(), "subsystem" : "en_ZA_16000"}
            res = requests.post(BASEURL + "admin/customlm", files=files)
            LOG.info('customlm(): SERVER SAYS:{}'.format(res.text))
            print('customlm(): SERVER SAYS:{}'.format(res.text))
            LOG.info(res.status_code)
            pkg = res.json()
            self.projectid = pkg['projectid']
            LOG.info('customlm(): SERVER SAYS:{}'.format(self.projectid))
            print('customlm(): SERVER SAYS:{}'.format(self.projectid))
        else:
            LOG.info("User not logged in!")

    def customlmquery(self, projectid):
        """
            Query Custom LM status
        """
        if self.admin_token is not None:
            LOG.info("Custom LM Query")
            headers = {"Content-Type" : "application/json"}
            data = {"token": self.admin_token, "projectid" : projectid} 
            res = requests.post(BASEURL + "admin/customlmquery", headers=headers, data=json.dumps(data))
            LOG.info('customlmquery(): SERVER SAYS:{}'.format(res.text))
            print('customlmquery(): SERVER SAYS:{}'.format(res.text))
            LOG.info(res.status_code)
            self.projectid = None
        else:
            LOG.info("User not logged in!")

    def clearmessage(self):
        """
            Clear message records
        """
        if self.admin_token is not None:
            LOG.info("Clearing message records")
            headers = {"Content-Type" : "application/json"}
            data = {"token": self.admin_token } 
            res = requests.post(BASEURL + "admin/clearmessage", headers=headers, data=json.dumps(data))
            LOG.info('clearmessage(): SERVER SAYS:{}'.format(res.text))
            print('clearmessage(): SERVER SAYS:{}'.format(res.text))
            LOG.info(res.status_code)
        else:
            LOG.info("User not logged in!")


if __name__ == "__main__":
    print('Accessing Docker app server via: {}'.format(BASEURL))

    admin = Admin()

    if len(sys.argv) < 2:
        print("HELP")
        print("Project specific - no user required")
        print("ADDUSER - Add project users")
        print("CUSTOMLM - custom lm")
        print("CUSTOMLMQUERY - query custom lm")
        print("CLEARMESSAGE - clear message records")

    elif len(sys.argv) > 1:
        if sys.argv[1].upper() == "ADDUSER":
            admin.adminlin()
            admin.adduser()
            admin.adminlout()

        elif sys.argv[1].upper() == "CUSTOMLM":
            admin.adminlin()
            admin.customlm()
            admin.adminlout()

        elif sys.argv[1].upper() == "CUSTOMLMQUERY":
            admin.adminlin()
            admin.customlmquery(sys.argv[2])
            admin.adminlout()

        elif sys.argv[1].upper() == "LOGOUT2":
            admin.adminlout2()

        elif sys.argv[1].upper() == "CLEARMESSAGE":
            admin.adminlin()
            admin.clearmessage()
            admin.adminlout()

        else:
            print("UNKNOWN TASK: {}".format(sys.argv))

