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
import threading
import time

BASEURL = "http://127.0.0.1:9999/wsgi/"

readline.parse_and_bind('tab: complete')
readline.parse_and_bind('set editing-mode vi')

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
#TODO: source from project_tester.py
class Project:

    def __init__(self):
        self.user_token = None
        self.admin_token = None
        self.projectid = None
        self.users = {}
        self.test_audio = 'tallship.ogg'
        self.test_audio_duration = 5.154830

    def gen_users(self, user_number=20):
        LOG.info("Generating {} users".format(user_number))
        for i in range(user_number):
            usr = 'usr{}'.format(str(i).zfill(3))
            self.users[usr] = {}
            self.users[usr]["username"] = usr
            self.users[usr]["password"] = usr
            self.users[usr]["name"] = gen_str()
            self.users[usr]["surname"] = gen_str(10)
            self.users[usr]["email"] = "{}@{}.org".format(gen_str(), gen_str())
            self.users[usr]["role"] = "project"
        return self.users

    def adminlin(self):
        """
            Login as admin
            Place admin 'token' in self.admin_token
        """
        if self.admin_token is None:
            LOG.info("Admin logging in")
            headers = {"Content-Type" : "application/json"}
            data = {"username": "root", "password": "123456", "role" : "admin"}
            res = requests.post(BASEURL + "projects/admin/login", headers=headers, data=json.dumps(data))
            print('adminlin(): SERVER SAYS:', res.text)
            print(res.status_code)
            pkg = res.json()
            self.admin_token = pkg['token']
        else:
            print("Admin logged in already!")
        print('')

    def adminlout(self):
        """
            Logout as admin
        """
        if self.admin_token is not None:
            LOG.info("Admin logging out")
            headers = {"Content-Type" : "application/json"}
            data = {"token": self.admin_token}
            res = requests.post(BASEURL + "projects/admin/logout", headers=headers, data=json.dumps(data))
            print('adminlout(): SERVER SAYS:', res.text)
            self.admin_token = None
        else:
            print("Admin not logged in!")
        print('')

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
            data = {"token": self.admin_token, "username": self.users[user]["username"], "password": self.users[user]["password"],
             "name": self.users[user]["name"], "surname": self.users[user]["surname"], "email": self.users[user]["email"]
             "role" : self.users[user]["role"]}
            res = requests.post(BASEURL + "projects/admin/adduser", headers=headers, data=json.dumps(data))
            print('adduser(): SERVER SAYS:', res.text)
            print(res.status_code)
        else:
            print("Admin not logged in!")
        print('')

    def login(self, user):
        """
            Login as user
            Place user 'token' in self.user_token
        """
        if user not in self.users:
            LOG.error("{} not in user list".format(user))
            return

        if self.user_token is None:
            LOG.info("{} logging in".format(user))
            headers = {"Content-Type" : "application/json"}
            data = {"username": self.users[user]["username"], "password": self.users[user]["password"], "role" : self.users[user]["role"]}
            res = requests.post(BASEURL + "projects/login", headers=headers, data=json.dumps(data))
            print('login(): SERVER SAYS:', res.text)
            pkg = res.json()
            self.user_token = pkg['token']
        else:
            print("User logged in already!")
        print('')

    def logout(self):
        """
            Logout as user
        """
        if self.user_token is not None:
            headers = {"Content-Type" : "application/json"}
            data = {"token": self.user_token}
            res = requests.post(BASEURL + "projects/logout", headers=headers, data=json.dumps(data))
            print('logout(): SERVER SAYS:', res.text)
            self.user_token = None
        else:
            print("User not logged in!")
        print('')

    def createproject(self):
        """
            Create a new project
            Save returned projectid in self.projectid
        """
        if self.user_token is not None:
            LOG.info("Creating project")
            headers = {"Content-Type" : "application/json"}
            data = {"token": self.user_token, "projectname" : gen_str(10), "category" : "NCOP" }
            res = requests.post(BASEURL + "projects/createproject", headers=headers, data=json.dumps(data))
            print('createproject(): SERVER SAYS:', res.text)
            print(res.status_code)
            pkg = res.json()
            self.projectid = pkg['projectid']
        else:
            print("User not logged in!")
        print('')

    def uploadaudio(self):
        """
            Upload audio to project
            Requires 'tallship.ogg' to be located in current location
        """
        if not os.path.exists(self.test_audio):
            print('Cannot run UPLOADAUDIO as "tallship.ogg" does not exist in current path')
            return

        if self.user_token is not None and self.projectid is not None:
            files = {'file' : open(self.test_audio, 'rb'), 'filename' : self.test_audio, 'token' : self.user_token, 'projectid' : self.projectid}
            res = requests.post(BASEURL + "projects/uploadaudio", files=files)
            print('uploadaudio(): SERVER SAYS:', res.text)
            print(res.status_code)
        else:
            print("User not logged in!")
        print('')

    def saveproject(self):
        """
            Save tasks for a specific project
            tasks should be a list of dicts with these elements:
            tasks = [(editor<string:20>, collater<string:20>, start<float>, end<float>), (), ...]
        """
        if self.user_token is not None and self.projectid is not None:
            LOG.info("Saving project")
            headers = {"Content-Type" : "application/json"}

            task_no = int(math.floor(random.uniform(2,10)))
            segs = [0.0]
            for n in range(task_no):
                segs.append(random.uniform(1,100))
            segs.sort()
            segs = [self.test_audio_duration*x/segs[-1] for x in segs]
            tasks = []
            for n in range(task_no):
                tmp = {"editor" : random.choice(self.users.keys()), "speaker" : random.choice(self.users.keys()), "start" : segs[n], "end" : segs[n+1], "language" : gen_str(10)}
                tasks.append(tmp)

            project = {"projectname": gen_str(10)}
            data = {"token": self.user_token, "projectid" : self.projectid, "tasks": tasks, "project": project}
            res = requests.post(BASEURL + "projects/saveproject", headers=headers, data=json.dumps(data))
            print('saveproject(): SERVER SAYS:', res.text)
            print(res.status_code)
        else:
            print("User not logged in!")
        print('')

    def assigntasks(self):
        """
            Assign tasks to editors
        """
        if self.user_token is not None and self.projectid is not None:
            LOG.info("Assigning tasks")
            headers = {"Content-Type" : "application/json"}
            data = {"token": self.user_token, "projectid" : self.projectid, "collator" : "random"}
            res = requests.post(BASEURL + "projects/assigntasks", headers=headers, data=json.dumps(data))
            print('assigntasks(): SERVER SAYS:', res.text)
            print(res.status_code)
        else:
            print("User not logged in!")
        print('')


class Editor:

    def __init__(self, user):
        self.this_task = None
        self.user = user
        self.users = {}
        self.username = None
        self.user_token = None
        self.admin_token = None
        self.taskid = None
        self.projectid = None

    def gen_users(self, user_number=10):
        LOG.info("Generating {} users".format(user_number))
        for i in range(user_number):
            usr = 'usr{}'.format(str(i).zfill(3))
            self.users[usr] = {}
            self.users[usr]["username"] = usr
            self.users[usr]["password"] = usr
            self.users[usr]["name"] = gen_str()
            self.users[usr]["surname"] = gen_str(10)
            self.users[usr]["email"] = "{}@{}.org".format(gen_str(), gen_str())
            self.users[usr]["role"] = "editor"
        return self.users

    def login(self):
        """
            Login as user
            Place user 'token' in self.user_token
        """
        user = self.user
        try:
            LOG.info("username={}: {} logging in".format(self.users[user]["username"], user))
            headers = {"Content-Type" : "application/json"}
            data = {"username": self.users[user]["username"], "password": self.users[user]["password"], "role" : self.users[user]["role"]}
            res = requests.post(BASEURL + "editor/login", headers=headers, data=json.dumps(data))
            LOG.info('username={}: login(): SERVER SAYS: {}'.format(self.users[user]["username"], res.text))
            pkg = res.json()
            self.user_token = pkg["token"]
            self.username = user
            return res.status_code, pkg['token']
        except Exception as e:
            LOG.error("username={}: login(): {}!".format(user, str(e)))
            return 500, None

    def adminlin(self):
        """
            Login as admin
            Place admin 'token' in self.admin_token
        """
        try:
            headers = {"Content-Type" : "application/json"}
            data = {"username": "root", "password": "123456", "role" : "admin"}
            print('ADMINLIN:', data)
            res = requests.post(BASEURL + "editor/admin/login", headers=headers, data=json.dumps(data))
            print('SERVER SAYS:', res.text)
            pkg = res.json()
            self.admin_token = pkg['token']
            return res.status_code, pkg["token"]
        except Exception as e:
            LOG.error("username={}: adminlin(): {}!".format("root", str(e)))
            return 500, None

    def adminlout(self):
        """
            Logout as admin
        """
        try:
            headers = {"Content-Type" : "application/json"}
            data = {"token": self.admin_token}
            print('ADMINLOUT:', data)
            res = requests.post(BASEURL + "editor/admin/logout", headers=headers, data=json.dumps(data))
            print('SERVER SAYS:', res.text)
            self.admin_token = None
            return res.status_code, None
        except Exception as e:
            LOG.error("username={}: adminlout(): {}!".format("root", str(e)))
            return 500, None

    def logout(self):
        """
            Logout as user
        """
        try:
            headers = {"Content-Type" : "application/json"}
            data = {"token": self.user_token}
            res = requests.post(BASEURL + "editor/logout", headers=headers, data=json.dumps(data))
            LOG.info("username={}: logout(): SERVER SAYS:".format(self.username, res.text))
            return res.status_code, None
        except Exception as e:
            LOG.error("username={}: logout(): {}!".format(user, str(e)))
            return 500, None

    def adduser(self, user):
        """
            Add automatically generated users to database
        """
        try:
            if user not in self.users.keys():
                LOG.error("{} not in user list".format(user))
                return 500, None

            if self.admin_token is not None:
                LOG.info("Adding user {}".format(user))
                headers = {"Content-Type" : "application/json"}
                data = {"token": self.admin_token, "username": self.users[user]["username"], "password": self.users[user]["password"],
                 "name": self.users[user]["name"], "surname": self.users[user]["surname"], "email": self.users[user]["email"]
                 "role" : self.users[user]["role"]}
                print('ADDUSER:', data)
                res = requests.post(BASEURL + "editor/admin/adduser", headers=headers, data=json.dumps(data))
                print('SERVER SAYS:', res.text)
                LOG.info("username={}: adduser(): SERVER SAYS:".format("root", res.text))
                return res.status_code, res.text
        except Exception as e:
            LOG.error("username={}: adduser(): {}!".format("root", str(e)))
            return 500, None

    def loadtasks(self):
        """
            Load all tasks belonging to neil
        """
        try:
            headers = {"Content-Type" : "application/json"}
            data = {"token": self.user_token}
            res = requests.post(BASEURL + "editor/loadtasks", headers=headers, data=json.dumps(data))
            pkg = res.json()
            print(res.text)
            if len(pkg['CANOPEN']) > 0:
                self.this_task = random.choice(pkg['CANOPEN'])
                self.taskid = self.this_task['taskid']
                self.projectid = self.this_task['projectid']
                LOG.info("username={}: loadtasks(): Taskid={} & Projectid={}".format(self.username, self.taskid, self.projectid))
                return res.status_code, "{} {}".format(self.taskid, self.projectid)
            else:
                print('No tasks to select')
                LOG.info("username={}: loadtasks(): No tasks to select!".format(self.username))
                return 500, None
        except Exception as e:
            LOG.error("username={}: loadtasks(): {}!".format(self.username, str(e)))
            return 500, None

    def getaudio(self):
        """
            Return a portion of audio for the task
        """
        try:
            params = {'token' : self.user_token, 'projectid' : self.projectid, 'taskid' : self.taskid}
            print(params)
            res = requests.get(BASEURL + "editor/getaudio", params=params)
            if res.status_code == 200:
                with open('taskrange.ogg', 'wb') as f:
                    f.write(res.content)
                LOG.info("username={}: getaudio(): Save audio to taskrange.ogg".format(self.username))
                return res.status_code, "Saved audio"
            else:
                LOG.error("username={}: getaudio(): {}".format(self.username, res.text))
                return res.status_code, res.text
        except Exception as e:
            LOG.error("username={}: getaudio(): {}!".format(self.username, str(e)))
            return 500, None

    def savetext(self):
        """
            Save text to task text file
        """
        try:
            headers = {"Content-Type" : "application/json"}
            data = {'token' : self.user_token, 'projectid' : self.projectid, 'taskid' : self.taskid, "text" : "Hello world!"}
            print(data)
            res = requests.post(BASEURL + "editor/savetext", headers=headers, data=json.dumps(data))
            LOG.info("username={}: savetext(): {}".format(self.username, res.text))
            return res.status_code, res.text
        except Exception as e:
            LOG.error("username={}: savetext(): {}!".format(self.username, str(e)))
            return 500, None

    def cleartext(self):
        """
            Remove text from file
        """
        try:
            headers = {"Content-Type" : "application/json"}
            data = {'token' : self.user_token, 'projectid' : self.projectid, 'taskid' : self.taskid, "text" : ""}
            print(data)
            res = requests.post(BASEURL + "editor/savetext", headers=headers, data=json.dumps(data))
            LOG.info("username={}: cleartext(): {}".format(self.username, res.text))
            return res.status_code, res.text
        except Exception as e:
            LOG.error("username={}: cleartext(): {}!".format(self.username, str(e)))
            return 500, None

    def gettext(self):
        """
            Return the task's text
        """
        try:
            headers = {"Content-Type" : "application/json"}
            data = {'token' : self.user_token, 'projectid' : self.projectid, 'taskid' : self.taskid}
            print(data)
            res = requests.post(BASEURL + "editor/gettext", headers=headers, data=json.dumps(data))
            LOG.info("username={}: gettext(): {}".format(self.username, res.text))
            return res.status_code, res.text
        except Exception as e:
            LOG.error("username={}: gettext(): {}!".format(self.username, str(e)))
            return 500, None

    def loadusers(self):
        """
            Return the registered users
        """
        try:
            headers = {"Content-Type" : "application/json"}
            data = {'token' : self.user_token, "role" : "editor"}
            res = requests.post(BASEURL + "editor/loadusers", headers=headers, data=json.dumps(data))
            LOG.info("username={}: loadusers(): {}".format(self.username, res.text))
            return res.status_code, res.text
        except Exception as e:
            LOG.error("username={}: loadusers(): {}!".format(self.username, str(e)))
            return 500, None

    def taskdone(self):
        """
            Assign the task to collator
        """
        try:
            headers = {"Content-Type" : "application/json"}
            data = {'token' : self.user_token, 'projectid' : self.projectid, 'taskid' : self.taskid}
            res = requests.post(BASEURL + "editor/taskdone", headers=headers, data=json.dumps(data))
            LOG.info("username={}: taskdone(): {}".format(self.username, res.text))
            return res.status_code, res.text
        except Exception as e:
            LOG.error("username={}: taskdone(): {}!".format(self.username, str(e)))
            return 500, None

    def unlocktask(self):
        """
            Cancel a scheduled job
        """
        try:
            headers = {"Content-Type" : "application/json"}
            data = {'token' : self.user_token, 'projectid' : self.projectid, 'taskid' : self.taskid}
            res = requests.post(BASEURL + "editor/unlocktask", headers=headers, data=json.dumps(data))
            LOG.info("username={}: unlocktask(): {}".format(self.username, res.text))
            return res.status_code, res.text
        except Exception as e:
            LOG.error("username={}: unlocktask(): {}!".format(self.username, str(e)))
            return 500, None

    def diarize(self):
        """
            Submit a diarize speech job
        """
        try:
            headers = {"Content-Type" : "application/json"}
            data = {'token' : self.user_token, 'projectid' : self.projectid, 'taskid' : self.taskid}
            res = requests.post(BASEURL + "editor/diarize", headers=headers, data=json.dumps(data))
            LOG.info("username={}: diarize(): {}".format(self.username, res.text))
            return res.status_code, res.text
        except Exception as e:
            LOG.error("username={}: diarize(): {}!".format(self.username, str(e)))
            return 500, None

    def recognize(self):
        """
            Submit a recognize speech job
        """
        try:
            headers = {"Content-Type" : "application/json"}
            data = {'token' : self.user_token, 'projectid' : self.projectid, 'taskid' : self.taskid}
            res = requests.post(BASEURL + "editor/recognize", headers=headers, data=json.dumps(data))
            LOG.info("username={}: recognize(): {}".format(self.username, res.text))
            return res.status_code, res.text
        except Exception as e:
            LOG.error("username={}: recognize(): {}!".format(self.username, str(e)))
            return 500, None

    def align(self):
        """
            Submit a align speech job
        """
        try:
            headers = {"Content-Type" : "application/json"}
            data = {'token' : self.user_token, 'projectid' : self.projectid, 'taskid' : self.taskid}
            res = requests.post(BASEURL + "editor/align", headers=headers, data=json.dumps(data))
            LOG.info("username={}: align(): {}".format(self.username, res.text))
            return res.status_code, res.text
        except Exception as e:
            LOG.error("username={}: align(): {}!".format(self.username, str(e)))
            return 500, None

    def clearerror(self):
        """
            Clear error status
        """
        try:
            headers = {"Content-Type" : "application/json"}
            data = {'token' : self.user_token, 'projectid' : self.projectid, 'taskid' : self.taskid}
            res = requests.post(BASEURL + "editor/clearerror", headers=headers, data=json.dumps(data))
            LOG.info("username={}: clearerror(): {}".format(self.username, res.text))
            return res.status_code, res.text
        except Exception as e:
            LOG.error("username={}: clearerror(): {}!".format(self.username, str(e)))
            return 500, None

    def error(self):
        return 200, None


class Worker(threading.Thread):

    def __init__(self, paths, user, number):
        threading.Thread.__init__(self)
        self.paths = paths
        self.user = user
        self.running = True
        self.editor = Editor(user)
        self.editor.gen_users()
        self.thread_number = number

    def run(self):
        state = "login"
        while self.running:
            LOG.info("user={} thread#={} state={}".format(self.user, self.thread_number, state))

            meth = getattr(self.editor, state)
            res, text = meth()
            LOG.info("user={} thread#={} state={} res={} text={}".format(self.user, self.thread_number, state, res, text))
            if res == 200:
                state = random.choice(self.paths[state])
            else:
                state = "error"

            rand_sleep = random.uniform(0.2,0.25)
            LOG.info("user={} thread#={} state={} waiting {}".format(self.user, self.thread_number, state, rand_sleep))
            time.sleep(rand_sleep)

        self.editor.logout()

    def stop(self):
        self.running = False


if __name__ == "__main__":
    print('Accessing Docker app server via: {}'.format(BASEURL))

    proj = Project()
    edit = Editor(None)

    # Not including taskdone as this will reduce the number of tasks one by one
    Paths = {"login" : ["loadtasks" ],
             "loadtasks" : ["gettext", "getaudio", "savetext", "cleartext"],
             "savetext" : ["recognize", "align", "savetext"],
            "gettext" : ["gettext", "getaudio", "savetext", "cleartext"],
            "getaudio" : ["gettext", "getaudio", "savetext", "cleartext"],
            "loadusers" : ["gettext", "getaudio", "savetext", "cleartext"],
            "unlocktask" : ["loadtasks"],
            "clearerror" : ["unlocktask", "logout"],
            "cleartext" : ["diarize"],
            "diarize" : ["unlocktask", "align", "recognize", "savetext", "cleartext"],
            "recognize" : ["unlocktask", "align", "recognize", "savetext", "cleartext"],
            "align" : ["unlocktask", "recognize", "savetext", "cleartext"],
            "logout" : ["login"],
            "error" : ["clearerror"]
    }

    if len(sys.argv) == 2:
        if sys.argv[1].upper() == "P_ADDUSERS":
            users = proj.gen_users()
            proj.adminlin()
            for usr in users:
                usr = proj.adduser(usr)
            proj.adminlout()

        elif sys.argv[1].upper() == "ADDPROJECT":
            users = proj.gen_users()
            for usr in users.keys():
                print(usr)
                proj.login(usr)
                proj.createproject()
                proj.uploadaudio()
                proj.saveproject()
                proj.assigntasks()
                proj.logout()

        elif sys.argv[1].upper() == "E_ADDUSERS":
            users = edit.gen_users()
            edit.adminlin()
            for usr in users:
                usr = edit.adduser(usr)
            edit.adminlout()

        elif sys.argv[1].upper() == "SIMULATE":
            Pool = []
            users = edit.gen_users(5)
            for n, usr in enumerate(users.keys()):
                work = Worker(Paths, usr, n)
                work.start()
                Pool.append(work)

            try:
                while True:
                    time.sleep(1)
            except:
                pass

            print("{}".format(Pool))
            for worker in Pool:
                print("{}".format(worker))
                worker.stop()
                print("JOIN")
                worker.join()

    else:
        print("{} (P_ADDUSERS|ADDPROJECT|E_ADDUSERS|SIMULATE)".format(sys.argv[0]))

