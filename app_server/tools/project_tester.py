#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" TODO: Clean up startup code...
"""
from __future__ import unicode_literals, division, print_function #Py2

import random
import time
import requests
import sys
import json
import os
import tempfile
import logging
import codecs
from collections import OrderedDict
try:
    from sqlite3 import dbapi2 as sqlite
except ImportError:
    from pysqlite2 import dbapi2 as sqlite #for old Python versions

import numpy as np

################################################################################
BASEURL = "http://127.0.0.1:9999/wsgi/projects"
MAXSLEEP = 10.0 #seconds

class RequestFailed(Exception):
    pass

def post(service, data):
    headers = {"Content-Type" : "application/json"}
    servpath = os.path.join(BASEURL, service)
    LOG.debug(servpath)
    return requests.post(servpath, headers=headers, data=json.dumps(data))    
################################################################################

class Test:
    def __init__(self, testdata, projectdbfile, forever=False):
        self.__dict__ = testdata
        self.state = {"u_notloggedin": True,
                      "u_loggedin": False,
                      "u_hasprojects": False,
                      "p_loaded": False,
                      "p_hasaudio": False,
                      "p_saved": False,
                      "p_unlocked": False,
                      "p_locked": False,
                      "p_unassigned": False,
                      "p_assigned": False,
                      "p_updated": False}
        self.ops = OrderedDict([("logout2", {}),
                                ("logout", {"u_loggedin"}),
                                ("login", {"u_notloggedin"}),                       
                                ("createproject", {"u_loggedin"}),
                                ("deleteproject", {"u_loggedin", "u_hasprojects", "p_loaded"}),
                                ("changepassword", {"u_loggedin"}),
                                ("listprojects", {"u_loggedin"}),
                                ("loadproject", {"u_loggedin", "u_hasprojects", "p_unlocked"}),
                                ("uploadaudio", {"u_loggedin", "u_hasprojects", "p_loaded", "p_unlocked", "p_unassigned"}),
                                ("getaudio", {"u_loggedin", "u_hasprojects", "p_loaded", "p_hasaudio", "p_unlocked", "p_unassigned"}),
                                ("diarizeaudio", {"u_loggedin", "u_hasprojects", "p_loaded", "p_hasaudio", "p_unlocked", "p_unassigned"}),
                                ("diarizeaudio2", {"u_loggedin", "u_hasprojects", "p_loaded", "p_hasaudio", "p_unlocked", "p_unassigned"}),
                                ("unlockproject", {"u_loggedin", "u_hasprojects", "p_loaded", "p_locked"}),
                                ("saveproject", {"u_loggedin", "u_hasprojects", "p_loaded", "p_hasaudio", "p_unlocked", "p_unassigned"}),
                                ("assigntasks", {"u_loggedin", "u_hasprojects", "p_loaded", "p_hasaudio", "p_saved", "p_unlocked", "p_unassigned"}),
                                ("updateproject", {"u_loggedin", "u_hasprojects", "p_loaded", "p_hasaudio", "p_saved", "p_unlocked", "p_assigned"})])
        self.forever = forever
        self.stopstate = {"u_notloggedin": False,
                          "u_loggedin": True,
                          "u_hasprojects": True,
                          "p_loaded": True,
                          "p_hasaudio": True,
                          "p_saved": True,
                          "p_unlocked": True,
                          "p_locked": False,
                          "p_unassigned": False,
                          "p_assigned": True,
                          "p_updated": True}
        self.db = sqlite.connect(projectdbfile)
        self.db.row_factory = sqlite.Row

    def _possible(self):
        possible_ops = set()
        possible_ops = [op for op in self.ops if all(self.state[flag] for flag in self.ops[op])]
        return possible_ops

    def walkthrough(self):
        try:
            while True:
                possible = self._possible()
                LOG.info("POSSIBLE: {}".format(possible))
                idxs = np.arange(len(possible))
                probs = ((idxs + 1)) / sum((idxs + 1))
                choice = possible[np.random.choice(idxs, p=probs)]
                LOG.info("CHOICE: {}".format(choice))
                getattr(self, choice)()
                stime = random.random() * MAXSLEEP
                LOG.info("SLEEP: {}".format(stime))
                time.sleep(stime)
                if self.state == self.stopstate and not self.forever:
                    LOG.info("DONE!")
                    break
        finally:
            self.logout2()
            self.deluser()

### ADMIN
    def adminlin(self, username=None, password=None):
        LOG.debug("ENTER")
        data = {"username": username or self.auser,
                "password": password or self.apassw}
        result = post("admin/login", data)
        LOG.info("SERVSTAT: {}".format(result.status_code))
        LOG.info("SERVMESG: {}".format(result.text))
        if result.status_code != 200:
            raise RequestFailed
        pkg = result.json()
        self.atoken = pkg["token"]
            
    def adminlout(self, token=None):
        LOG.debug("ENTER")
        data = {"token": token or self.atoken}
        result = post("admin/logout", data)
        LOG.info("SERVSTAT: {}".format(result.status_code))
        LOG.info("SERVMESG: {}".format(result.text))
        if result.status_code != 200:
            raise RequestFailed
        self.atoken = None

    def adminlout2(self, username=None, password=None):
        LOG.debug("ENTER")
        data = {"username": username or self.auser,
                "password": password or self.apassw}
        result = post("admin/logout2", data)
        LOG.info("SERVSTAT: {}".format(result.status_code))
        LOG.info("SERVMESG: {}".format(result.text))
        if result.status_code != 200:
            raise RequestFailed
        self.atoken = None

    def adduser(self, token=None, username=None, password=None, name=None, surname=None, email=None):
        LOG.debug("ENTER")
        data = {"token": token or self.atoken,
                "username": username or self.user,
                "password": password or self.passw,
                "name": name or self.name,
                "surname": surname or self.surname,
                "email": email or self.email}
        result = post("admin/adduser", data)
        LOG.info("SERVSTAT: {}".format(result.status_code))
        LOG.info("SERVMESG: {}".format(result.text))
        if result.status_code != 200:
            raise RequestFailed

    def deluser(self, token=None, username=None):
        LOG.debug("ENTER")
        data = {"token": token or self.atoken,
                "username": username or self.user}
        result = post("admin/deluser", data)
        LOG.info("SERVSTAT: {}".format(result.status_code))
        LOG.info("SERVMESG: {}".format(result.text))
        if result.status_code != 200:
            raise RequestFailed

### NON-ADMIN
    def login(self, username=None, password=None):
        LOG.debug("ENTER")
        data = {"username": username or self.user,
                "password": password or self.passw}
        result = post("login", data)
        LOG.info("SERVSTAT: {}".format(result.status_code))
        LOG.info("SERVMESG: {}".format(result.text))
        if result.status_code != 200:
            raise RequestFailed
        pkg = result.json()
        self.token = pkg['token']
        self.state["u_notloggedin"] = False
        self.state["u_loggedin"] = True

    def logout(self, token=None):
        LOG.debug("ENTER")
        data = {"token": token or self.token}
        result = post("logout", data)
        LOG.info("SERVSTAT: {}".format(result.status_code))
        LOG.info("SERVMESG: {}".format(result.text))
        if result.status_code != 200:
            raise RequestFailed
        self.token = None
        self.state["u_notloggedin"] = True
        self.state["u_loggedin"] = False

    def logout2(self, username=None, password=None):
        LOG.debug("ENTER")
        data = {"username": username or self.user,
                "password": password or self.passw}
        result = post("logout2", data)
        LOG.info("SERVSTAT: {}".format(result.status_code))
        LOG.info("SERVMESG: {}".format(result.text))
        if result.status_code != 200:
            raise RequestFailed
        self.token = None
        self.state["u_notloggedin"] = True
        self.state["u_loggedin"] = False


    def changepassword(self, token=None, username=None, password=None):
        LOG.debug("ENTER")
        data = {"token": token or self.token,
                "password": password or self.passw_}
        result = post("changepassword", data)
        LOG.info("SERVSTAT: {}".format(result.status_code))
        LOG.info("SERVMESG: {}".format(result.text))
        if result.status_code != 200:
            raise RequestFailed
        self.passw_, self.passw = self.passw, data["password"]

    def listcategories(self, token=None):
        LOG.debug("ENTER")
        data = {"token": token or self.token}
        result = post("listcategories", data)
        LOG.info("SERVSTAT: {}".format(result.status_code))
        LOG.info("SERVMESG: {}".format(result.text))
        if result.status_code != 200:
            raise RequestFailed

    def createproject(self, token=None, projectname=None, category=None):
        LOG.debug("ENTER")
        data = {"token": token or self.token,
                "projectname": projectname or self.projectname,
                "category": category or self.projectcat}
        result = post("createproject", data)
        LOG.info("SERVSTAT: {}".format(result.status_code))
        LOG.info("SERVMESG: {}".format(result.text))
        if result.status_code != 200:
            raise RequestFailed
        pkg = result.json()
        self.pid = pkg['projectid']
        self.state["u_hasprojects"] = True
        self.state["p_loaded"] = True
        self.state["p_hasaudio"] = False
        self.state["p_saved"] = False
        self.state["p_unlocked"] = True
        self.state["p_locked"] = False
        self.state["p_unassigned"] = True
        self.state["p_assigned"] = False
        self.state["p_updated"] = False

    def listprojects(self, token=None):
        LOG.debug("ENTER")
        data = {"token": token or self.token}
        result = post("listprojects", data)
        LOG.info("SERVSTAT: {}".format(result.status_code))
        LOG.info("SERVMESG: {}".format(result.text))
        if result.status_code != 200:
            raise RequestFailed

    def loadproject(self, token=None, projectid=None):
        LOG.debug("ENTER")
        data = {"token": token or self.token,
                "projectid": projectid or self.pid}
        result = post("loadproject", data)
        LOG.info("SERVSTAT: {}".format(result.status_code))
        LOG.info("SERVMESG: {}".format(result.text))
        if result.status_code != 200:
            raise RequestFailed
        #DEMIT: set new project parms

    def deleteproject(self, token=None, projectid=None):
        LOG.debug("ENTER")
        data = {"token": token or self.token,
                "projectid": projectid or self.pid}
        result = post("deleteproject", data)
        LOG.info("SERVSTAT: {}".format(result.status_code))
        LOG.info("SERVMESG: {}".format(result.text))
        if result.status_code != 200:
            raise RequestFailed
        self.pid = None
        self.state["u_hasprojects"] = False
        self.state["p_loaded"] = False

    def uploadaudio(self, token=None, projectid=None, filename=None):
        LOG.debug("ENTER")
        data = {"token": token or self.token,
                "projectid": projectid or self.pid,
                "filename": filename or os.path.basename(self.audiofile),
                "file": open(filename or self.audiofile, "rb")}
        result = requests.post(os.path.join(BASEURL, "uploadaudio"), files=data)
        LOG.info("SERVSTAT: {}".format(result.status_code))
        LOG.info("SERVMESG: {}".format(result.text))
        if result.status_code != 200:
            raise RequestFailed
        self.state["p_hasaudio"] = True
        self.state["p_saved"] = False

    def getaudio(self, token=None, projectid=None):
        LOG.debug("ENTER")
        data = {"token": token or self.token,
                "projectid": projectid or self.pid}
        result = requests.get(os.path.join(BASEURL, "getaudio"), params=data)
        LOG.info("SERVSTAT: {}".format(result.status_code))
        LOG.info("SERVMESG: {}".format("BINARY"))
        if result.status_code != 200:
            raise RequestFailed
        #Write temp audiofile
        f, fname = tempfile.mkstemp()
        f = os.fdopen(f, "w")
        f.write(result.content)
        f.close()
        os.remove(fname)

    def diarizeaudio(self, token=None, projectid=None, ctm=None):
        LOG.debug("ENTER")
        data = {"token": token or self.token,
                "projectid": projectid or self.pid}
        putdata = {"CTM": ctm or self.diarizectm}

        result = post("diarizeaudio", data)
        LOG.info("SERVSTAT: {}".format(result.status_code))
        LOG.info("SERVMESG: {}".format(result.text))
        if result.status_code != 200:
            raise RequestFailed
        #SIMULATING SPEECHSERVER JOB
        with self.db:
            outurl, = self.db.execute("SELECT url "
                                      "FROM outgoing "
                                      "WHERE projectid=?", (data["projectid"],)).fetchone()
            inurl, = self.db.execute("SELECT url "
                                     "FROM incoming "
                                     "WHERE projectid=?", (data["projectid"],)).fetchone()
        ##GET
        result = requests.get(os.path.join(BASEURL, "projects", outurl), params={})
        LOG.info("SPEECHGETSTAT: {}".format(result.status_code))
        if result.status_code != 200:
            LOG.info("SPEECHGETMESG: {}".format(result.text))
            raise RequestFailed
        LOG.info("SPEECHGETMESG: {}".format("BINARY"))
        ###Write temp audiofile
        f, fname = tempfile.mkstemp()
        f = os.fdopen(f, "w")
        f.write(result.content)
        f.close()
        os.remove(fname)
        ##PUT
        result = requests.put(os.path.join(BASEURL, "projects", inurl), headers={"Content-Type" : "application/json"}, data=json.dumps(putdata))
        LOG.info("SPEECHPUTSTAT: {}".format(result.status_code))
        LOG.info("SPEECHPUTMESG: {}".format(result.text))
        self.state["p_saved"] = False
        

    def diarizeaudio2(self, token=None, projectid=None):
        LOG.debug("ENTER")
        data = {"token": token or self.token,
                "projectid": projectid or self.pid}
        result = post("diarizeaudio", data)
        LOG.info("SERVSTAT: {}".format(result.status_code))
        LOG.info("SERVMESG: {}".format(result.text))
        if result.status_code != 200:
            raise RequestFailed
        self.state["p_unlocked"] = False
        self.state["p_locked"] = True

    def saveproject(self, token=None, projectid=None, tasks=None, project=None):
        LOG.debug("ENTER")
        data = {"token": token or self.token,
                "projectid": projectid or self.pid,
                "tasks": tasks or self.savetasks,
                "project": project or self.saveproj}
        result = post("saveproject", data)
        LOG.info("SERVSTAT: {}".format(result.status_code))
        LOG.info("SERVMESG: {}".format(result.text))
        if result.status_code != 200:
            raise RequestFailed
        self.state["p_saved"] = True

    def assigntasks(self, token=None, projectid=None):
        LOG.debug("ENTER")
        data = {"token": token or self.token,
                "projectid": projectid or self.pid}
        result = post("assigntasks", data)
        LOG.info("SERVSTAT: {}".format(result.status_code))
        LOG.info("SERVMESG: {}".format(result.text))
        if result.status_code != 200:
            raise RequestFailed
        self.state["p_unassigned"] = False
        self.state["p_assigned"] = True

    def updateproject(self, token=None, projectid=None, tasks=None, project=None):
        LOG.debug("ENTER")
        data = {"token": token or self.token,
                "projectid": projectid or self.pid,
                "tasks": tasks or self.updatetasks,
                "project": project or self.updateproj}
        result = post("updateproject", data)
        LOG.info("SERVSTAT: {}".format(result.status_code))
        LOG.info("SERVMESG: {}".format(result.text))
        if result.status_code != 200:
            raise RequestFailed
        self.state["p_updated"] = True

    def unlockproject(self, token=None, projectid=None):
        LOG.debug("ENTER")
        data = {"token": token or self.token,
                "projectid": projectid or self.pid}
        result = post("unlockproject", data)
        LOG.info("SERVSTAT: {}".format(result.status_code))
        LOG.info("SERVMESG: {}".format(result.text))
        if result.status_code != 200:
            raise RequestFailed
        self.state["p_unlocked"] = True
        self.state["p_locked"] = False

def runtest(args):
    testdata, projectdbfile = args
    ################################################################################
    ### LOGGING SETUP
    global LOG
    LOGNAME = "PTESTER"
    try:
        fmt = "%(asctime)s [%(levelname)s] %(name)s on tid:{} in %(funcName)s(): %(message)s".format(testdata["testid"])
        LOG = logging.getLogger(LOGNAME)
        formatter = logging.Formatter(fmt)
        ofstream = logging.FileHandler(logfile, encoding="utf-8")
        ofstream.setFormatter(formatter)
        LOG.addHandler(ofstream)
        LOG.setLevel(int(loglevel))
        #If we want console output:
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        LOG.addHandler(console)
    except Exception as e:
        print("FATAL ERROR: Could not create logging instance: {}".format(e), file=sys.stderr)
        sys.exit(1)
    ################################################################################
    t = Test(testdata, projectdbfile)
    t.walkthrough()
    

if __name__ == "__main__":
    logfile, loglevel, testfile, nusers, nprocs, projectdbfile = sys.argv[1:]
    nusers = int(nusers)
    nprocs = int(nprocs)
    with codecs.open(testfile, encoding="utf-8") as testfh:
        testdata = json.load(testfh)

    try:
        import multiprocessing
        POOL = multiprocessing.Pool(processes=nprocs)
        def map(f, i):
            return POOL.map(f, i, chunksize=1)
    except ImportError:
        pass

    ################################################################################
    ### LOGGING SETUP
    LOGNAME = "PTESTER"
    try:
        fmt = "%(asctime)s [%(levelname)s] %(name)s on tid:{} in %(funcName)s(): %(message)s".format(testdata["testid"])
        LOG = logging.getLogger(LOGNAME)
        formatter = logging.Formatter(fmt)
        ofstream = logging.FileHandler(logfile, encoding="utf-8")
        ofstream.setFormatter(formatter)
        LOG.addHandler(ofstream)
        LOG.setLevel(int(loglevel))
        #If we want console output:
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        LOG.addHandler(console)
    except Exception as e:
        print("FATAL ERROR: Could not create logging instance: {}".format(e), file=sys.stderr)
        sys.exit(1)

    ################################################################################
    LOG.info("Accessing Docker app server via: {}".format(BASEURL))
    LOG.info("Creating {} tests/users".format(nusers))
    tests = []
    t = Test(testdata, projectdbfile)
    try:
        t.adminlin()
        for i in range(nusers):
            tdata = dict(testdata)
            tdata["user"] = "user{}".format(str(i).zfill(2))
            tdata["testid"] = i
            t.adduser(username=tdata["user"])
            tests.append(tdata)
        LOG.info("Walking through {} tests {} procs".format(nusers, nprocs))
        map(runtest, [(tdata, projectdbfile) for tdata in tests])
    finally:
        t.adminlout2()

    # proj = Project(projectdbfile=sys.argv[1])

    # if len(sys.argv) < 3:
    #     try:
    #         while True:
    #             cmd = raw_input("Enter command (type help for list)> ")
    #             cmd = cmd.lower()
    #             if cmd == "exit":
    #                 proj.logout()
    #                 proj.adminlout()
    #                 break
    #             elif cmd in ["help", "list"]:
    #                 print("ADMINLIN - Admin login")
    #                 print("ADMINLOUT - Admin logout")
    #                 print("ADDUSER - add new user\n")
    #                 print("LOGIN - user login")
    #                 print("LOGOUT - user logout")
    #                 print("CHANGEPASSWORD - change user user password")
    #                 print("CHANGEBACKPASSWORD - change user user password back")
    #                 print("LISTCATEGORIES - list project categories")
    #                 print("CREATEPROJECT - create a new project")
    #                 print("LISTPROJECTS - list projects")
    #                 print("LOADPROJECT - load projects")
    #                 print("UPLOADAUDIO - upload audio to project")
    #                 print("GETAUDIO - retrieve project audio")
    #                 print("SAVEPROJECT - save tasks to a project")
    #                 print("ASSIGNTASKS - assign tasks to editors")
    #                 print("DIARIZEAUDIO - save tasks to a project via diarize request (simulate speech server)\n")
    #                 print("DIARIZEAUDIO2 - like DIARIZEAUDIO but withouth speech server (project stays locked)\n")
    #                 print("UNLOCKPROJECT - unlock project (can test this against DIARIZEAUDIO2)")
    #                 print("EXIT - quit")

    #             else:
    #                 try:
    #                     meth = getattr(proj, cmd)
    #                     meth()
    #                 except Exception as e:
    #                     print('Error processing command:', e)

    #     except:
    #         proj.logout()
    #         proj.adminlout()
    #         print('')
    # else:
    #     if sys.argv[2].upper() == "ASSIGN":
    #         proj.login()
    #         proj.createproject()
    #         proj.uploadaudio()
    #         proj.saveproject()
    #         proj.assigntasks()
    #         proj.logout()
    #     elif sys.argv[2].upper() == "ASSIGN_NOTASKS":
    #         proj.login()
    #         proj.createproject()
    #         proj.uploadaudio()
    #         proj.assigntasks()
    #         proj.logout()
    #     elif sys.argv[2].upper() == "DIARIZE_ASSIGN":
    #         proj.login()
    #         proj.createproject()
    #         proj.uploadaudio()
    #         proj.diarizeaudio()
    #         proj.saveproject()
    #         proj.assigntasks()
    #         proj.logout()
    #     elif sys.argv[2].upper() == "DIARIZE_ASSIGN_UPDATE":
    #         proj.login()
    #         proj.createproject()
    #         proj.uploadaudio()
    #         proj.diarizeaudio()
    #         proj.saveproject()
    #         proj.assigntasks()
    #         proj.updateproject()
    #         proj.logout()
    #     elif sys.argv[2].upper() == "DIARIZE_ASSIGN_DELETE":
    #         proj.login()
    #         proj.createproject()
    #         proj.uploadaudio()
    #         proj.diarizeaudio()
    #         proj.saveproject()
    #         proj.assigntasks()
    #         proj.deleteproject()
    #         proj.logout()
    #     elif sys.argv[2].upper() == "DIARIZE_DELETE":
    #         proj.login()
    #         proj.createproject()
    #         proj.uploadaudio()
    #         proj.diarizeaudio()
    #         proj.saveproject()
    #         proj.deleteproject()
    #         proj.logout()
    #     else:
    #         print("UNKNOWN TASK: {}".format(sys.argv[2]))

