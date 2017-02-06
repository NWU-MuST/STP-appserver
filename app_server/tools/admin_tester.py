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
LOGNAME = "EDITORTEST"
LOGFNAME = "editor_tester.log"
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
class Project:

    def __init__(self):
        self.user_token = None
        self.admin_token = None
        self.username = "john"
        self.password = "doe"

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
            LOG.info('adminlin(): SERVER SAYS:', res.text)
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
            LOG.info('adminlout(): SERVER SAYS:', res.text)
            self.admin_token = None
        else:
            LOG.info("Admin not logged in!")

    def adduser(self, user):
        """
            Add automatically generated users to database
        """
        if user not in self.users.keys():
            LOG.error("{} not in user list".format(user))
            return

        if self.admin_token is not None:
            LOG.info("Adding user {}".format(user))
            headers = {"Content-Type" : "application/json"}
            data = {"token": self.admin_token, "username": self.username, "password": self.password,
             "name": "John", "surname": "Doe", "email": "john@doe.com", "role": "admin"}
            res = requests.post(BASEURL + "admin/adduser", headers=headers, data=json.dumps(data))
            LOG.info('adduser(): SERVER SAYS:', res.text)
            LOG.info(res.status_code)
        else:
            LOG.info("Admin not logged in!")

    def login(self):
        """
            Login as admin user
        """
        if self.admin_token is None:
            LOG.info("Admin logging in")
            headers = {"Content-Type" : "application/json"}
            data = {"username": self.username, "password": self.password, "role" : "admin"}
            res = requests.post(BASEURL + "admin/login", headers=headers, data=json.dumps(data))
            LOG.info('login(): SERVER SAYS:', res.text)
            LOG.info(res.status_code)
            pkg = res.json()
            self.user_token = pkg['token']
        else:
            LOG.info("User logged in already!")

    def logout(self):
        """
            Logout as admin user
        """
        if self.admin_token is not None:
            LOG.info("Admin logging out")
            headers = {"Content-Type" : "application/json"}
            data = {"token": self.admin_token}
            res = requests.post(BASEURL + "admin/logout", headers=headers, data=json.dumps(data))
            LOG.info('logout(): SERVER SAYS:', res.text)
            self.admin_token = None
        else:
            LOG.info("User not logged in!")

    def customlm(self):
        """
            Upload audio to project
            Requires tallship.ogg to be located in current location
        """
        if not os.path.exists('tallship.ogg'):
            LOG.error('Cannot run UPLOADAUDIO as "tallship.ogg" does not exist in current path')
            return

        if self.user_token is not None and self.projectid is not None:
            files = {'file' : open(self.test_audio, 'rb'), 'filename' : 'tallship.ogg', 'token' : self.user_token, 'projectid' : self.projectid}
            res = requests.post(BASEURL + "projects/uploadaudio", files=files)
            LOG.info('uploadaudio(): SERVER SAYS:', res.text)
            LOG.info(res.status_code)
        else:
            LOG.info("User not logged in!")

    def customlmquery(self):
        """
            Assign tasks to editors
        """
        if self.user_token is not None and self.projectid is not None:
            LOG.info("Assigning tasks")
            headers = {"Content-Type" : "application/json"}
            data = {"token": self.user_token, "projectid" : self.projectid, "collator" : "e{}".format(random.choice(self.users.keys()))}
            res = requests.post(BASEURL + "projects/assigntasks", headers=headers, data=json.dumps(data))
            LOG.info('assigntasks(): SERVER SAYS:', res.text)
            LOG.info(res.status_code)
        else:
            LOG.info("User not logged in!")


if __name__ == "__main__":
    print('Accessing Docker app server via: {}'.format(BASEURL))

    proj = Admin()

    if len(sys.argv) < 2:
        print("HELP")
        print("Project specific - no user required")
        print("ADDUSER - Add project users")
        print("CUSTOMLM - custom lm")
        print("CUSTOMLMQUERY - query custom lm")

    elif len(sys.argv) == 2:
        if sys.argv[1].upper() == "ADDUSERS":
            users = proj.gen_users()
            proj.adminlin()
            for usr in users:
                usr = proj.adduser(usr)
            proj.adminlout()

        elif sys.argv[1].upper() == "ADDPROJECT":
            users = proj.gen_users()
            usr = random.choice(users.keys())
            proj.login(usr)
            proj.createproject()
            proj.uploadaudio()
            proj.createtasks()
            proj.assigntasks()
            proj.logout()

        elif sys.argv[1].upper() == "CUSTOMLM":
            users = proj.gen_users()
            usr = random.choice(users.keys())
            proj.login(usr)
            proj.customlm()
            proj.logout()

        elif sys.argv[1].upper() == "CUSTOMLMQUERY":
            users = proj.gen_users()
            usr = random.choice(users.keys())
            proj.login(usr)
            proj.customlmquery()
            proj.logout()

        else:
            print("UNKNOWN TASK: {}".format(sys.argv))

