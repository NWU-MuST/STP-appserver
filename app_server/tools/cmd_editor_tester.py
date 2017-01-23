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

BASEURL = "http://127.0.0.1:9999/wsgi/"
USERNO = 2
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

    def gen_users(self, user_number=USERNO):
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
            res = requests.post(BASEURL + "admin/login", headers=headers, data=json.dumps(data))
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
            res = requests.post(BASEURL + "admin/logout", headers=headers, data=json.dumps(data))
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
             "name": self.users[user]["name"], "surname": self.users[user]["surname"], "email": self.users[user]["email"],
             "role": self.users[user]["role"]}
            res = requests.post(BASEURL + "admin/adduser", headers=headers, data=json.dumps(data))
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
            data = {"token": self.user_token, "projectname" : gen_str(10), "category" : "NCOP", "projectmanager" : random.choice(self.users.keys()) }
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
            Requires tallship.ogg to be located in current location
        """
        if not os.path.exists('tallship.ogg'):
            print('Cannot run UPLOADAUDIO as "tallship.ogg" does not exist in current path')
            return

        if self.user_token is not None and self.projectid is not None:
            files = {'file' : open(self.test_audio, 'rb'), 'filename' : 'tallship.ogg', 'token' : self.user_token, 'projectid' : self.projectid}
            res = requests.post(BASEURL + "projects/uploadaudio", files=files)
            print('uploadaudio(): SERVER SAYS:', res.text)
            print(res.status_code)
        else:
            print("User not logged in!")
        print('')

    def createtasks(self):
        """
            Save tasks for a specific project
            tasks should be a list of dicts with these elements:
            tasks = [(editor<string:20>, start<float>, end<float>), (), ...]
        """
        if self.user_token is not None and self.projectid is not None:
            LOG.info("Saving project")
            headers = {"Content-Type" : "application/json"}

            task_no = int(math.floor(random.uniform(2,5)))
            segs = [0.0]
            for n in range(task_no):
                segs.append(random.uniform(1,8))
            segs.sort()
            segs = [self.test_audio_duration*x/segs[-1] for x in segs]
            tasks = []
            for n in range(task_no):
                tmp = {"editor" : "e{}".format(random.choice(self.users.keys())), "start" : segs[n], "end" : segs[n+1], "language" : gen_str(10), "speaker" : gen_str(10)}
                tasks.append(tmp)

            project = {"projectname": gen_str(10)}
            data = {"token": self.user_token, "projectid" : self.projectid, "tasks": tasks, "project": project}
            res = requests.post(BASEURL + "projects/createtasks", headers=headers, data=json.dumps(data))
            print('createtasks(): SERVER SAYS:', res.text)
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
            data = {"token": self.user_token, "projectid" : self.projectid, "collator" : "e{}".format(random.choice(self.users.keys()))}
            res = requests.post(BASEURL + "projects/assigntasks", headers=headers, data=json.dumps(data))
            print('assigntasks(): SERVER SAYS:', res.text)
            print(res.status_code)
        else:
            print("User not logged in!")
        print('')


class Editor:

    def __init__(self):
        self.user_token = None
        self.admin_token = None
        self.this_task = None
        self.users = {}
        self.username = None

    def gen_users(self, user_number=USERNO):
        LOG.info("Generating {} users".format(user_number))
        for i in range(user_number):
            usr = 'eusr{}'.format(str(i).zfill(3))
            self.users[usr] = {}
            self.users[usr]["username"] = usr
            self.users[usr]["password"] = usr
            self.users[usr]["name"] = gen_str()
            self.users[usr]["surname"] = gen_str(10)
            self.users[usr]["email"] = "{}@{}.org".format(gen_str(), gen_str())
            self.users[usr]["role"] = "editor"

        return self.users

    def login(self, user):
        """
            Login as user
            Place user 'token' in self.user_token
        """
        if user not in self.users:
            LOG.error("{} not in user list".format(user))
            return

        if self.user_token is None:
            LOG.info("username={}: {} logging in".format(self.users[user]["username"], user))
            headers = {"Content-Type" : "application/json"}
            data = {"username": self.users[user]["username"], "password": self.users[user]["password"], "role" : self.users[user]["role"]}
            res = requests.post(BASEURL + "editor/login", headers=headers, data=json.dumps(data))
            print('login(): SERVER SAYS:', res.text)
            LOG.info('username={}: login(): SERVER SAYS: {}'.format(self.users[user]["username"], res.text))
            pkg = res.json()
            self.user_token = pkg['token']
            self.username = self.users[user]["username"]
        else:
            print("User logged in already!")
            LOG.error("username={}: login(): User logged in already!")
        print('')

    def adminlin(self):
        """
            Login as admin
            Place admin 'token' in self.admin_token
        """
        if self.admin_token is None:
            headers = {"Content-Type" : "application/json"}
            data = {"username": "root", "password": "123456", "role" : "admin"}
            res = requests.post(BASEURL + "admin/login", headers=headers, data=json.dumps(data))
            print('SERVER SAYS:', res.text)
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
            headers = {"Content-Type" : "application/json"}
            data = {"token": self.admin_token}
            res = requests.post(BASEURL + "admin/logout", headers=headers, data=json.dumps(data))
            print('SERVER SAYS:', res.text)
            self.admin_token = None
        else:
            print("Admin not logged in!")
        print('')

    def logout(self):
        """
            Logout as user
        """
        LOG.info("username={}: logout(): Entering".format(self.username))
        if self.user_token is not None:
            headers = {"Content-Type" : "application/json"}
            data = {"token": self.user_token}
            res = requests.post(BASEURL + "editor/logout", headers=headers, data=json.dumps(data))
            print('SERVER SAYS:', res.text)
            LOG.info("username={}: logout(): SERVER SAYS: {}".format(self.username, res.text))
            self.user_token = None
        else:
            print("User not logged in!")
            LOG.error("username={}: logout(): User not logged in!".format(self.username))
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
                    "name": self.users[user]["name"], "surname": self.users[user]["surname"], "email": self.users[user]["email"],
                    "role" : self.users[user]["role"]}
            res = requests.post(BASEURL + "admin/adduser", headers=headers, data=json.dumps(data))
            print('adduser(): SERVER SAYS:', res.text)
            print(res.status_code)
        else:
            print("Admin not logged in!")
        print('')

    def loadtasks(self):
        """
            Load all tasks belonging to neil
        """
        LOG.info("username={}: loadtasks(): Entering".format(self.username))
        if self.user_token is not None:
            headers = {"Content-Type" : "application/json"}
            data = {"token": self.user_token}
            res = requests.post(BASEURL + "editor/loadtasks", headers=headers, data=json.dumps(data))
            print('SERVER SAYS:', res.text)
            print(res.status_code)
            pkg = res.json()
            if len(pkg['editor']) > 0:
                self.this_task = None
                for this_task in pkg['editor']:
                    if this_task["jobid"] is None and this_task["errstatus"] is None:
                        self.this_task = this_task
                        break
                if self.this_task is None:
                    raise RuntimeError("Cannot select a task!")

                self.taskid = self.this_task['taskid']
                self.projectid = self.this_task['projectid']
                print(self.taskid, self.projectid)
                LOG.info("username={}: loadtasks(): Taskid={} & Projectid={}".format(self.username, self.taskid, self.projectid))
            else:
                print('No tasks to select')
                LOG.info("username={}: loadtasks(): No tasks to select!".format(self.username))
        else:
            print("User not logged in!")
            LOG.error("username={}: loadtasks(): User not logged in!".format(self.username))
        print('')

    def getaudio(self):
        """
            Return a portion of audio for the task
        """
        LOG.info("username={}: getaudio(): Entering".format(self.username))
        if self.user_token is not None and self.projectid is not None:
            params = {'token' : self.user_token, 'projectid' : self.projectid, 'taskid' : self.taskid}
            res = requests.get(BASEURL + "editor/getaudio", params=params)
            print(res.status_code)
            if res.status_code == 200:
                with open('taskrange.ogg', 'wb') as f:
                    f.write(res.content)
                LOG.info("username={}: getaudio(): Save audio to taskrange.ogg".format(self.username))
            else:
                print('SERVER SAYS:', res.text)
                LOG.error("username={}: getaudio(): ".format(self.username), res.text)
        else:
            print("User not logged in!")
            LOG.error("username={}: getaudio(): User not logged in!".format(self.username))
        print('')

    def savetext(self):
        """
            Save text to task text file
        """
        LOG.info("username={}: savetext(): Entering".format(self.username))
        if self.user_token is not None and self.projectid is not None:
            headers = {"Content-Type" : "application/json"}
            data = {'token' : self.user_token, 'projectid' : self.projectid, 'taskid' : self.taskid, "text" : "Hello world!"}
            res = requests.post(BASEURL + "editor/savetext", headers=headers, data=json.dumps(data))
            print('SERVER SAYS:', res.text)
            LOG.info("username={}: savetext(): {}".format(self.username, res.text))
            print(res.status_code)
        else:
            print("User not logged in!")
            LOG.error("username={}: savetext(): User not logged in!".format(self.username))
        print('')

    def cleartext(self):
        """
            Remove text from file
        """
        LOG.info("username={}: cleartext(): Entering".format(self.username))
        if self.user_token is not None and self.projectid is not None:
            headers = {"Content-Type" : "application/json"}
            data = {'token' : self.user_token, 'projectid' : self.projectid, 'taskid' : self.taskid, "text" : ""}
            res = requests.post(BASEURL + "editor/savetext", headers=headers, data=json.dumps(data))
            print('SERVER SAYS:', res.text)
            LOG.info("username={}: cleartext(): {}".format(self.username, res.text))
            print(res.status_code)
        else:
            print("User not logged in!")
            LOG.error("username={}: cleartext(): User not logged in!".format(self.username))
        print('')

    def gettext(self):
        """
            Return the task's text
        """
        LOG.info("username={}: gettext(): Entering".format(self.username))
        if self.user_token is not None and self.projectid is not None:
            headers = {"Content-Type" : "application/json"}
            data = {'token' : self.user_token, 'projectid' : self.projectid, 'taskid' : self.taskid}
            res = requests.post(BASEURL + "editor/gettext", headers=headers, data=json.dumps(data))
            print('SERVER SAYS:', res.text)
            LOG.info("username={}: gettext(): {}".format(self.username, res.text))
            print(res.status_code)
            pkg = res.json()
            print('TEXT', pkg['text'])
        else:
            print("User not logged in!")
            LOG.error("username={}: gettext(): User not logged in!".format(self.username))
        print('')

    def loadusers(self):
        """
            Return the registered users
        """
        LOG.info("username={}: loadusers(): Entering".format(self.username))
        if self.user_token is not None and self.projectid is not None:
            headers = {"Content-Type" : "application/json"}
            data = {'token' : self.user_token, "role" : "editor"}
            res = requests.post(BASEURL + "editor/loadusers", headers=headers, data=json.dumps(data))
            print('SERVER SAYS:', res.text)
            LOG.info("username={}: loadusers: {}".format(self.username, res.text))
            print(res.status_code)
        else:
            print("User not logged in!")
            LOG.error("username={}: loadusers(): User not logged in!".format(self.username))
        print('')

    def taskdone(self):
        """
            Assign the task to collator
        """
        LOG.info("username={}: taskdone(): Entering".format(self.username))
        if self.user_token is not None and self.projectid is not None:
            headers = {"Content-Type" : "application/json"}
            data = {'token' : self.user_token, 'projectid' : self.projectid, 'taskid' : self.taskid}
            res = requests.post(BASEURL + "editor/taskdone", headers=headers, data=json.dumps(data))
            print('SERVER SAYS:', res.text)
            LOG.info("username={}: taskdone(): {}".format(self.username, res.text))
            print(res.status_code)
        else:
            print("User not logged in!")
            LOG.error("username={}: taskdone(): User not logged in!".format(self.username))
        print('')

    def reassigntask(self):
        """
            Re-assign task to editor
        """
        LOG.info("username={}: reassigntask(): Entering".format(self.username))
        if self.user_token is not None and self.projectid is not None:
            headers = {"Content-Type" : "application/json"}
            data = {'token' : self.user_token, 'projectid' : self.projectid, 'taskid' : self.taskid}
            res = requests.post(BASEURL + "editor/reassigntask", headers=headers, data=json.dumps(data))
            print('SERVER SAYS:', res.text)
            LOG.info("username={}: reassigntask(): {}".format(self.username, res.text))
            print(res.status_code)
        else:
            print("User not logged in!")
            LOG.error("username={}: reassigntask(): User not logged in!".format(self.username))
        print('')

    def buildmaster(self):
        """
            Build master docx MS-WORD
        """
        LOG.info("username={}: buildmaster(): Entering".format(self.username))
        if self.user_token is not None and self.projectid is not None:
            headers = {"Content-Type" : "application/json"}
            data = {'token' : self.user_token, 'projectid' : self.projectid}
            res = requests.post(BASEURL + "editor/buildmaster", headers=headers, data=json.dumps(data))
            print('SERVER SAYS:', res.text)
            LOG.info("username={}: buildmaster(): {}".format(self.username, res.text))
            print(res.status_code)
        else:
            print("User not logged in!")
            LOG.error("username={}: buildmaster(): User not logged in!".format(self.username))
        print('')

    def unlocktask(self):
        """
            Cancel a scheduled job
        """
        LOG.info("username={}: unlocktask(): Entering".format(self.username))
        if self.user_token is not None and self.projectid is not None:
            headers = {"Content-Type" : "application/json"}
            data = {'token' : self.user_token, 'projectid' : self.projectid, 'taskid' : self.taskid}
            res = requests.post(BASEURL + "editor/unlocktask", headers=headers, data=json.dumps(data))
            print('SERVER SAYS:', res.text)
            LOG.info("username={}: unlocktask(): {}".format(self.username, res.text))
            print(res.status_code)
        else:
            print("User not logged in!")
            LOG.error("username={}: unlocktask(): User not logged in!".format(self.username))
        print('')

    def diarize(self):
        """
            Submit a diarize speech job
        """
        LOG.info("username={}: diarize(): Entering".format(self.username))
        if self.user_token is not None and self.projectid is not None:
            headers = {"Content-Type" : "application/json"}
            data = {'token' : self.user_token, 'projectid' : self.projectid, 'taskid' : self.taskid}
            res = requests.post(BASEURL + "editor/diarize", headers=headers, data=json.dumps(data))
            print('SERVER SAYS:', res.text)
            LOG.info("username={}: diarize(): {}".format(self.username, res.text))
            print(res.status_code)
        else:
            print("User not logged in!")
            LOG.error("username={}: diarize(): User not logged in!".format(self.username))
        print('')

    def recognize(self):
        """
            Submit a recognize speech job
        """
        LOG.info("username={}: recognize(): Entering".format(self.username))
        if self.user_token is not None and self.projectid is not None:
            headers = {"Content-Type" : "application/json"}
            data = {'token' : self.user_token, 'projectid' : self.projectid, 'taskid' : self.taskid}
            res = requests.post(BASEURL + "editor/recognize", headers=headers, data=json.dumps(data))
            print('SERVER SAYS:', res.text)
            LOG.info("username={}: recognize(): {}".format(self.username, res.text))
            print(res.status_code)
        else:
            print("User not logged in!")
            LOG.error("username={}: recognize(): User not logged in!".format(self.username))
        print('')

    def align(self):
        """
            Submit a align speech job
        """
        LOG.info("username={}: align(): Entering".format(self.username))
        if self.user_token is not None and self.projectid is not None:
            headers = {"Content-Type" : "application/json"}
            data = {'token' : self.user_token, 'projectid' : self.projectid, 'taskid' : self.taskid}
            res = requests.post(BASEURL + "editor/align", headers=headers, data=json.dumps(data))
            print('SERVER SAYS:', res.text)
            LOG.info("username={}: align(): {}".format(self.username, res.text))
            print(res.status_code)
        else:
            print("User not logged in!")
            LOG.error("username={}: align(): User not logged in!".format(self.username))
        print('')


    def clearerror(self):
        """
            Clear error status
        """
        LOG.info("username={}: clearerror(): Entering".format(self.username))
        if self.user_token is not None and self.projectid is not None:
            headers = {"Content-Type" : "application/json"}
            data = {'token' : self.user_token, 'projectid' : self.projectid, 'taskid' : self.taskid}
            res = requests.post(BASEURL + "editor/clearerror", headers=headers, data=json.dumps(data))
            print('SERVER SAYS:', res.text)
            LOG.info("username={}: clearerror(): {}".format(self.username, res.text))
            print(res.status_code)
            pkg = res.json()
        else:
            print("User not logged in!")
            LOG.error("username={}: clearerror(): User not logged in!".format(self.username))
        print('')




if __name__ == "__main__":
    print('Accessing Docker app server via: {}'.format(BASEURL))

    proj = Project()
    edit = Editor()

    if len(sys.argv) < 2:
        print("HELP")
        print("Project specific - no user required")
        print("P_ADDUSERS - Add project users")
        print("ADDPROJECT - Add projects")
        print("E_ADDUSERS - Add editor users\n")

        print("Editor specific - (need to provide a user name)")
        print("GETAUDIO - return task audio")
        print("GETTEXT - return task text")
        print("SAVETEXT - save text to file")
        print("CLEARTEXT - remove text from file")
        print("TASKDONE - set the task is done")
        print("UNLOCKTASK - cancel a speech job")
        print("CLEARERROR - remove task error status")
        print("DIARIZE - submit diarize job")
        print("RECOGNIZE - submit recognize job")
        print("ALIGN - submit align job")


    elif len(sys.argv) == 2:
        if sys.argv[1].upper() == "P_ADDUSERS":
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

        elif sys.argv[1].upper() == "E_ADDUSERS":
            users = edit.gen_users()
            edit.adminlin()
            for usr in users:
                usr = edit.adduser(usr)
            edit.adminlout()

        else:
            print("UNKNOWN TASK: {}".format(sys.argv))

    elif len(sys.argv) == 3:
        users = edit.gen_users()
        if sys.argv[2] not in users:
            print("User {} not found".format(sys.argv[2]))
            sys.exit(1)

        if sys.argv[1].upper() == "LOADTASKS":
            edit.login(sys.argv[2])
            edit.loadtasks()
            edit.logout()

        elif sys.argv[1].upper() == "SAVETEXT":
            edit.login(sys.argv[2])
            edit.loadtasks()
            edit.savetext()
            edit.logout()

        elif sys.argv[1].upper() == "CLEARERROR":
            edit.login(sys.argv[2])
            edit.clearerror()
            edit.logout()

        elif sys.argv[1].upper() == "UNLOCKTASK":
            edit.login(sys.argv[2])
            edit.loadtasks()
            edit.unlocktask()
            edit.logout()

        elif sys.argv[1].upper() == "GETTEXT":
            edit.login(sys.argv[2])
            edit.loadtasks()
            edit.gettext()
            edit.logout()

        elif sys.argv[1].upper() == "GETAUDIO":
            edit.login(sys.argv[2])
            edit.loadtasks()
            edit.getaudio()
            edit.logout()

        elif sys.argv[1].upper() == "TASKDONE":
            edit.login(sys.argv[2])
            edit.loadtasks()
            edit.taskdone()
            edit.logout()

        elif sys.argv[1].upper() == "REASSIGNTASK":
            edit.login(sys.argv[2])
            edit.loadtasks()
            edit.reassigntask()
            edit.logout()

        elif sys.argv[1].upper() == "BUILDMASTER":
            edit.login(sys.argv[2])
            edit.loadtasks()
            edit.buildmaster()
            edit.logout()

        elif sys.argv[1].upper() == "DIARIZE":
            edit.login(sys.argv[2])
            edit.loadtasks()
            edit.diarize()
            edit.logout()

        elif sys.argv[1].upper() == "RECOGNIZE":
            edit.login(sys.argv[2])
            edit.loadtasks()
            edit.recognize()
            edit.logout()

        elif sys.argv[1].upper() == "ALIGN":
            edit.login(sys.argv[2])
            edit.loadtasks()
            edit.align()
            edit.logout()

    else:
            print("UNKNOWN TASK: {}".format(sys.argv))

