#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""This allows easy testing of the `projects` service of the
   application server. It can be run interactively or in 'simulation'
   mode.
"""
from __future__ import unicode_literals, division, print_function #Py2

import argparse
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


DEF_BASEURL = "http://127.0.0.1:9999/wsgi/projects"
DEF_LOGFILE = "project_tester.log"
DEF_LOGLEVEL = 20 #INFO
DEF_TESTFILE = "ptest01.json"
DEF_DBFILE = "projects.db"
DEF_NUSERS = 40
DEF_NPROCS = 40
DEF_MINDELAY = 20.0 #seconds
DEF_MAXDELAY = 60.0 #seconds

################################################################################
def setuplog(logname, logfile, loglevel, tid):
    try:
        fmt = "%(asctime)s [%(levelname)s] %(name)s on tid:{} in %(funcName)s(): %(message)s".format(tid)
        log = logging.getLogger(logname)
        formatter = logging.Formatter(fmt)
        ofstream = logging.FileHandler(logfile, encoding="utf-8")
        ofstream.setFormatter(formatter)
        log.addHandler(ofstream)
        log.setLevel(loglevel)
        #If we want console output:
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        log.addHandler(console)
        return log
    except Exception as e:
        print("FATAL ERROR: Could not create logging instance: {}".format(e), file=sys.stderr)
        sys.exit(1)

class RequestFailed(Exception):
    pass

def post(service, data, baseurl=DEF_BASEURL):
    headers = {"Content-Type" : "application/json"}
    servpath = os.path.join(baseurl, service)
    LOG.debug(servpath)
    return requests.post(servpath, headers=headers, data=json.dumps(data))    

################################################################################

class Test:
    def __init__(self, testdata, projectdbfile, baseurl=DEF_BASEURL, forever=False, seed=None):
        self.__dict__ = testdata
        self.baseurl = baseurl
        self.seed = seed
        LOG.info("SEED: {}".format(self.seed))
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

    def walkthrough(self, mindelay, maxdelay):
        random.seed(self.seed)
        np.random.seed(self.seed)
        try:
            while True:
                possible = self._possible()
                LOG.info("POSSIBLE: {}".format(possible))
                idxs = np.arange(len(possible))
                probs = ((idxs + 1) ** 2) / sum((idxs + 1) ** 2)
                choice = possible[np.random.choice(idxs, p=probs)]
                LOG.info("CHOICE: {}".format(choice))
                getattr(self, choice)()
                stime = random.uniform(mindelay, maxdelay)
                LOG.info("SLEEP: {}".format(stime))
                time.sleep(stime)
                if self.state == self.stopstate and not self.forever:
                    LOG.info("DONE!")
                    return (True, None, self)
        except Exception as e:
            return (False, e, self)

### ADMIN
    def adminlin(self, username=None, password=None):
        LOG.debug("ENTER")
        data = {"username": username or self.auser,
                "password": password or self.apassw}
        result = post("admin/login", data)
        LOG.info("SERVSTAT: {}".format(result.status_code))
        LOG.info("SERVMESG: {}".format(result.text))
        if result.status_code != 200:
            raise RequestFailed(result.text)
        pkg = result.json()
        self.atoken = pkg["token"]
            
    def adminlout(self, token=None):
        LOG.debug("ENTER")
        data = {"token": token or self.atoken}
        result = post("admin/logout", data)
        LOG.info("SERVSTAT: {}".format(result.status_code))
        LOG.info("SERVMESG: {}".format(result.text))
        if result.status_code != 200:
            raise RequestFailed(result.text)
        self.atoken = None

    def adminlout2(self, username=None, password=None):
        LOG.debug("ENTER")
        data = {"username": username or self.auser,
                "password": password or self.apassw}
        result = post("admin/logout2", data)
        LOG.info("SERVSTAT: {}".format(result.status_code))
        LOG.info("SERVMESG: {}".format(result.text))
        if result.status_code != 200:
            raise RequestFailed(result.text)
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
            raise RequestFailed(result.text)

    def deluser(self, token=None, username=None):
        LOG.debug("ENTER")
        data = {"token": token or self.atoken,
                "username": username or self.user}
        result = post("admin/deluser", data)
        LOG.info("SERVSTAT: {}".format(result.status_code))
        LOG.info("SERVMESG: {}".format(result.text))
        if result.status_code != 200:
            raise RequestFailed(result.text)

### NON-ADMIN
    def login(self, username=None, password=None):
        LOG.debug("ENTER")
        data = {"username": username or self.user,
                "password": password or self.passw}
        result = post("login", data)
        LOG.info("SERVSTAT: {}".format(result.status_code))
        LOG.info("SERVMESG: {}".format(result.text))
        if result.status_code != 200:
            raise RequestFailed(result.text)
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
            raise RequestFailed(result.text)
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
            raise RequestFailed(result.text)
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
            raise RequestFailed(result.text)
        self.passw_, self.passw = self.passw, data["password"]

    def listcategories(self, token=None):
        LOG.debug("ENTER")
        data = {"token": token or self.token}
        result = post("listcategories", data)
        LOG.info("SERVSTAT: {}".format(result.status_code))
        LOG.info("SERVMESG: {}".format(result.text))
        if result.status_code != 200:
            raise RequestFailed(result.text)

    def createproject(self, token=None, projectname=None, category=None):
        LOG.debug("ENTER")
        data = {"token": token or self.token,
                "projectname": projectname or self.projectname,
                "category": category or self.projectcat}
        result = post("createproject", data)
        LOG.info("SERVSTAT: {}".format(result.status_code))
        LOG.info("SERVMESG: {}".format(result.text))
        if result.status_code != 200:
            raise RequestFailed(result.text)
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
            raise RequestFailed(result.text)

    def loadproject(self, token=None, projectid=None):
        LOG.debug("ENTER")
        data = {"token": token or self.token,
                "projectid": projectid or self.pid}
        result = post("loadproject", data)
        LOG.info("SERVSTAT: {}".format(result.status_code))
        LOG.info("SERVMESG: {}".format(result.text))
        if result.status_code != 200:
            raise RequestFailed(result.text)
        #DEMIT: set new project parms

    def deleteproject(self, token=None, projectid=None):
        LOG.debug("ENTER")
        data = {"token": token or self.token,
                "projectid": projectid or self.pid}
        result = post("deleteproject", data)
        LOG.info("SERVSTAT: {}".format(result.status_code))
        LOG.info("SERVMESG: {}".format(result.text))
        if result.status_code != 200:
            raise RequestFailed(result.text)
        self.pid = None
        self.state["u_hasprojects"] = False
        self.state["p_loaded"] = False

    def uploadaudio(self, token=None, projectid=None, filename=None):
        LOG.debug("ENTER")
        data = {"token": token or self.token,
                "projectid": projectid or self.pid,
                "filename": filename or os.path.basename(self.audiofile),
                "file": open(filename or self.audiofile, "rb")}
        result = requests.post(os.path.join(self.baseurl, "uploadaudio"), files=data)
        LOG.info("SERVSTAT: {}".format(result.status_code))
        LOG.info("SERVMESG: {}".format(result.text))
        if result.status_code != 200:
            raise RequestFailed(result.text)
        self.state["p_hasaudio"] = True
        self.state["p_saved"] = False

    def getaudio(self, token=None, projectid=None):
        LOG.debug("ENTER")
        data = {"token": token or self.token,
                "projectid": projectid or self.pid}
        result = requests.get(os.path.join(self.baseurl, "getaudio"), params=data)
        LOG.info("SERVSTAT: {}".format(result.status_code))
        LOG.info("SERVMESG: {}".format("BINARY"))
        if result.status_code != 200:
            raise RequestFailed(result.text)
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
            raise RequestFailed(result.text)
        #SIMULATING SPEECHSERVER JOB
        with self.db:
            outurl, = self.db.execute("SELECT url "
                                      "FROM outgoing "
                                      "WHERE projectid=?", (data["projectid"],)).fetchone()
            inurl, = self.db.execute("SELECT url "
                                     "FROM incoming "
                                     "WHERE projectid=?", (data["projectid"],)).fetchone()
        ##GET
        result = requests.get(os.path.join(self.baseurl, "projects", outurl), params={})
        LOG.info("SPEECHGETSTAT: {}".format(result.status_code))
        if result.status_code != 200:
            LOG.info("SPEECHGETMESG: {}".format(result.text))
            raise RequestFailed(result.text)
        LOG.info("SPEECHGETMESG: {}".format("BINARY"))
        ###Write temp audiofile
        f, fname = tempfile.mkstemp()
        f = os.fdopen(f, "w")
        f.write(result.content)
        f.close()
        os.remove(fname)
        ##PUT
        result = requests.put(os.path.join(self.baseurl, "projects", inurl), headers={"Content-Type" : "application/json"}, data=json.dumps(putdata))
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
            raise RequestFailed(result.text)
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
            raise RequestFailed(result.text)
        self.state["p_saved"] = True

    def assigntasks(self, token=None, projectid=None):
        LOG.debug("ENTER")
        data = {"token": token or self.token,
                "projectid": projectid or self.pid}
        result = post("assigntasks", data)
        LOG.info("SERVSTAT: {}".format(result.status_code))
        LOG.info("SERVMESG: {}".format(result.text))
        if result.status_code != 200:
            raise RequestFailed(result.text)
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
            raise RequestFailed(result.text)
        self.state["p_updated"] = True

    def unlockproject(self, token=None, projectid=None):
        LOG.debug("ENTER")
        data = {"token": token or self.token,
                "projectid": projectid or self.pid}
        result = post("unlockproject", data)
        LOG.info("SERVSTAT: {}".format(result.status_code))
        LOG.info("SERVMESG: {}".format(result.text))
        if result.status_code != 200:
            raise RequestFailed(result.text)
        self.state["p_unlocked"] = True
        self.state["p_locked"] = False

def runtest(args):
    baseurl, testdata, projectdbfile, mindelay, maxdelay, logfile, loglevel = args
    ################################################################################
    ### LOGGING SETUP
    global LOG
    LOG = setuplog("PTESTER", logfile, loglevel, testdata["testid"])
    ################################################################################
    t = Test(testdata, projectdbfile, baseurl=baseurl, seed=testdata["testid"])
    return t.walkthrough(mindelay, maxdelay)
    

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('mode', metavar='MODE', type=str, help="Mode of operation (interactive|simulate)")
    parser.add_argument('--baseurl', metavar='BASEURL', type=str, dest="baseurl", default=DEF_BASEURL, help="Base URL for requests")
    parser.add_argument('--logfile', metavar='LOGFILE', type=str, dest="logfile", default=DEF_LOGFILE, help="Log file path")
    parser.add_argument('--loglevel', metavar='LOGLEVEL', type=int, dest="loglevel", default=DEF_LOGLEVEL, help="Log verbosity level")
    parser.add_argument('--testfile', metavar='TESTFILE', type=str, dest="testfile", default=DEF_TESTFILE, help="Test data description file")
    parser.add_argument('--dbfile', metavar='DBFILE', type=str, dest="dbfile", default=DEF_DBFILE, help="Projects DB file path")
    parser.add_argument('--nusers', metavar='NUSERS', type=int, dest="nusers", default=DEF_NUSERS, help="Number of concurrent users (simulation mode)")
    parser.add_argument('--nprocs', metavar='NPROCS', type=int, dest="nprocs", default=DEF_NPROCS, help="Number of concurrent processes (simulation mode)")
    parser.add_argument('--mindelay', metavar='MINDELAY', type=float, dest="mindelay", default=DEF_MINDELAY, help="Minimum delay between user requests (simulation mode)")
    parser.add_argument('--maxdelay', metavar='DURATION', type=float, dest="maxdelay", default=DEF_MAXDELAY, help="Maximum delay between user requests (simulation mode)")
    args = parser.parse_args()

    try:
        import multiprocessing
        POOL = multiprocessing.Pool(processes=args.nprocs)
        def map(f, i):
            return POOL.map(f, i, chunksize=1)
    except ImportError:
        pass

    LOG = setuplog("PTESTER", args.logfile, args.loglevel, "admin")
    with codecs.open(args.testfile, encoding="utf-8") as testfh:
        testdata = json.load(testfh)

    if args.mode.startswith("sim"):
        LOG.info("Accessing Docker app server via: {}".format(args.baseurl))
        LOG.info("Creating {} tests/users".format(args.nusers))
        tests = []
        t = Test(testdata, args.dbfile, baseurl=args.baseurl)
        t.adminlin()
        for i in range(args.nusers):
            tdata = dict(testdata)
            tdata["user"] = "user{}".format(str(i).zfill(2))
            tdata["testid"] = i
            t.adduser(username=tdata["user"])
            tests.append(tdata)
        LOG.info("Walking through {} tests {} procs".format(args.nusers, args.nprocs))
        testresults = map(runtest, [(args.baseurl, tdata, args.dbfile, args.mindelay, args.maxdelay, args.logfile, args.loglevel) for tdata in tests])
        LOG.info("Walkthrough results: {} of {} successful".format(len([flag for flag, _, __ in testresults if flag == True]), len(tests)))
        LOG.info("Walkthrough failed for TIDs: {}".format(", ".join([str(teststate.testid) for flag, _, teststate in testresults if flag == False])))
        #force logout all and delete
        for flag, e, teststate in testresults:
            LOG.info("tid:{} Logging out and deleting user: {}".format(teststate.testid, teststate.user))
            LOG.info("tid:{} E-state: {}".format(teststate.testid, e))
            try:
                t.logout2(username=teststate.user, password=teststate.passw)
            except RequestFailed:
                t.logout2(username=teststate.user, password=teststate.passw_)
            t.deluser(username=teststate.user)
        #logout admin
        t.adminlout2()
    elif args.mode.startswith("int"):
        t = Test(testdata, args.dbfile, baseurl=args.baseurl)
        try:
            while True:
                cmd = raw_input("Enter command (type help for list)> ")
                cmd = cmd.lower()
                if cmd == "exit":
                    t.logout2()
                    t.adminlout2()
                    break
                elif cmd in ["help", "list"]:
                    print("ADMINLIN - Admin login")
                    print("ADMINLOUT - Admin logout")
                    print("ADMINLOUT2 - Admin logout (with username & password)")
                    print("ADDUSER - add new user\n")
                    print("DELUSER - delete new user\n")
                    print("LOGIN - user login")
                    print("LOGOUT - user logout")
                    print("LOGOUT2 - user logout (with username & password)")
                    print("CHANGEPASSWORD - change user user password")
                    print("CHANGEBACKPASSWORD - change user user password back")
                    print("LISTCATEGORIES - list project categories")
                    print("CREATEPROJECT - create a new project")
                    print("LISTPROJECTS - list projects")
                    print("LOADPROJECT - load projects")
                    print("UPLOADAUDIO - upload audio to project")
                    print("GETAUDIO - retrieve project audio")
                    print("SAVEPROJECT - save tasks to a project")
                    print("ASSIGNTASKS - assign tasks to editors")
                    print("DIARIZEAUDIO - save tasks to a project via diarize request (simulate speech server)\n")
                    print("DIARIZEAUDIO2 - like DIARIZEAUDIO but withouth speech server (project stays locked)\n")
                    print("UNLOCKPROJECT - unlock project (can test this against DIARIZEAUDIO2)")
                    print("EXIT - quit")
                else:
                    try:
                        meth = getattr(t, cmd)
                        meth()
                    except Exception as e:
                        print('Error processing command:', e)
        except:
            t.logout2()
            t.adminlout2()
            print('')
    else:
        parser.print_help()
