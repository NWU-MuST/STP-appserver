#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function #Py2

import requests
import sys
import json
import os
try:
    from sqlite3 import dbapi2 as sqlite
except ImportError:
    from pysqlite2 import dbapi2 as sqlite #for old Python versions

BASEURL = "http://127.0.0.1:9999/wsgi/"


class Project:

    def __init__(self, projectdbfile=None):
        self.user_token = None
        self.admin_token = None
        self.projectid = None
        if projectdbfile:
            self.db = sqlite.connect(projectdbfile)
            self.db.row_factory = sqlite.Row


    def login(self):
        """
            Login as user
            Place user 'token' in self.user_token
        """
        if self.user_token is None:
            headers = {"Content-Type" : "application/json"}
            data = {"username": "neil", "password": "neil"}
            res = requests.post(BASEURL + "projects/login", headers=headers, data=json.dumps(data))
            print('SERVER SAYS:', res.text)
            pkg = res.json()
            self.user_token = pkg['token']
        else:
            print("User logged in already!")
        print('')

    def adminlin(self):
        """
            Login as admin
            Place admin 'token' in self.admin_token
        """
        if self.admin_token is None:
            headers = {"Content-Type" : "application/json"}
            data = {"username": "root", "password": "123456"}
            res = requests.post(BASEURL + "projects/admin/login", headers=headers, data=json.dumps(data))
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
            res = requests.post(BASEURL + "projects/admin/logout", headers=headers, data=json.dumps(data))
            print('SERVER SAYS:', res.text)
            self.admin_token = None
        else:
            print("Admin not logged in!")
        print('')

    def logout(self):
        """
            Logout as user
        """
        if self.user_token is not None:
            headers = {"Content-Type" : "application/json"}
            data = {"token": self.user_token}
            res = requests.post(BASEURL + "projects/logout", headers=headers, data=json.dumps(data))
            print('SERVER SAYS:', res.text)
            self.user_token = None
        else:
            print("Admin not logged in!")
        print('')

    def adduser(self):
        """
            Add user project database
            User details: "username": "neil", "password": "neil", "name": "neil", "surname": "kleynhans", "email": "neil@organisation.org"
        """
        if self.admin_token is not None:
            headers = {"Content-Type" : "application/json"}
            data = {"token": self.admin_token, "username": "neil", "password": "neil", "name": "neil", "surname": "kleynhans", "email": "neil@organisation.org"}
            res = requests.post(BASEURL + "projects/admin/adduser", headers=headers, data=json.dumps(data))
            print('SERVER SAYS:', res.text)
            print(res.status_code)
        else:
            print("Admin not logged in!")
        print('')

    def listcategories(self):
        """
            List the project categories defined in project JSON config
        """
        if self.user_token is not None:
            headers = {"Content-Type" : "application/json"}
            data = {"token": self.user_token}
            res = requests.post(BASEURL + "projects/listcategories", headers=headers, data=json.dumps(data))
            print('SERVER SAYS:', res.text)
            print(res.status_code)
        else:
            print("User not logged in!")
        print('')

    def createproject(self):
        """
            Create a new project
            Save returned projectid in self.projectid
        """
        if self.user_token is not None:
            headers = {"Content-Type" : "application/json"}
            data = {"token": self.user_token, "projectname" : "new_project", "category" : "NCOP" }
            res = requests.post(BASEURL + "projects/createproject", headers=headers, data=json.dumps(data))
            print('SERVER SAYS:', res.text)
            print(res.status_code)
            pkg = res.json()
            self.projectid = pkg['projectid']
        else:
            print("User not logged in!")
        print('')

    def listprojects(self):
        """
            List all projects belonging to user
        """
        if self.user_token is not None:
            headers = {"Content-Type" : "application/json"}
            data = {"token": self.user_token}
            res = requests.post(BASEURL + "projects/listprojects", headers=headers, data=json.dumps(data))
            print('SERVER SAYS:', res.text)
            print(res.status_code)
        else:
            print("User not logged in!")
        print('')

    def loadproject(self):
        """
            Load a specific projects details
        """
        if self.user_token is not None and self.projectid is not None:
            headers = {"Content-Type" : "application/json"}
            data = {"token": self.user_token, "projectid" : self.projectid}
            res = requests.post(BASEURL + "projects/loadproject", headers=headers, data=json.dumps(data))
            print('SERVER SAYS:', res.text)
            print(res.status_code)
        else:
            print("User not logged in!")
        print('')

    def projectaudio(self):
        """
            Return uploaded project audio
            Will save the uploaded audio to 'tmp.ogg' in current location
        """
        if self.user_token is not None and self.projectid is not None:
            params = {'token' : self.user_token, 'projectid' : self.projectid}
            res = requests.get(BASEURL + "projects/projectaudio", params=params)
            print(res.status_code)
            if res.status_code == 200:
                with open('tmp.ogg', 'wb') as f:
                    f.write(res.content)
            else:
                print('SERVER SAYS:', res.text)
        else:
            print("User not logged in!")
        print('')


    def uploadaudio(self):
        """
            Upload audio to project
            Requires test.ogg to be located in current location
        """
        if not os.path.exists('test.ogg'):
            print('Cannot run UPLOADAUDIO as "test.ogg" does not exist in current path')
            return

        if self.user_token is not None and self.projectid is not None:
            files = {'file' : open('test.ogg', 'rb'), 'filename' : 'test.ogg', 'token' : self.user_token, 'projectid' : self.projectid}
            res = requests.post(BASEURL + "projects/uploadaudio", files=files)
            print('SERVER SAYS:', res.text)
            print(res.status_code)
        else:
            print("User not logged in!")
        print('')


    def saveproject(self):
        """
            Save tasks for a specific project
            tasks should be a list with these elements:
            tasks = [(editor<string:20>, collater<string:20>, start<float>, end<float>), (), ...]
        """
        if self.user_token is not None and self.projectid is not None:
            headers = {"Content-Type" : "application/json"}
            tasks = [{"editor" : "neil", "collator" : "neil", "start" : 0.0, "end" : 20.0, "language" : "English"},
                    {"editor" : "daniel", "collator" : "daniel", "start" : 20.0, "end" : 40.0, "language" : "Afrikaans"},
                    {"editor" : "gamer", "collator" : "gamer", "start" : 40.0, "end" : 60.0, "language" : "Zulu"}]
            data = {"token": self.user_token, "projectid" : self.projectid, "tasks": tasks}
            res = requests.post(BASEURL + "projects/saveproject", headers=headers, data=json.dumps(data))
            print('SERVER SAYS:', res.text)
            print(res.status_code)
        else:
            print("User not logged in!")
        print('')

    def assigntasks(self):
        """
            Assign tasks to editors
        """
        if self.user_token is not None and self.projectid is not None:
            headers = {"Content-Type" : "application/json"}
            data = {"token": self.user_token, "projectid" : self.projectid}
            res = requests.post(BASEURL + "projects/assigntasks", headers=headers, data=json.dumps(data))
            print('SERVER SAYS:', res.text)
            print(res.status_code)
        else:
            print("User not logged in!")
        print('')


    def diarizeaudio(self):
        """
            Make diarize request to split project into tasks
        """
        if self.user_token is not None and self.projectid is not None:
            headers = {"Content-Type" : "application/json"}
            data = {"token": self.user_token, "projectid" : self.projectid}
            res = requests.post(BASEURL + "projects/diarizeaudio", headers=headers, data=json.dumps(data))
            print('SERVER SAYS:', res.text)
            print(res.status_code)
            print("SIMULATING SPEECH SERVER JOB:")
            #GET URLs:
            with self.db:
                outurl, = self.db.execute("SELECT url "
                                          "FROM outgoing "
                                          "WHERE projectid=?", (self.projectid,)).fetchone()
                inurl, = self.db.execute("SELECT url "
                                         "FROM incoming "
                                         "WHERE projectid=?", (self.projectid,)).fetchone()
            print("\tSPEECHSERVER GET: ", end="")
            res = requests.get(BASEURL + outurl, params={})
            print(res.status_code)
            if res.status_code == 200:
                with open('diarize_tmp.ogg', 'wb') as f:
                    f.write(res.content)
            else:
                print('SERVER SAYS:', res.text)
            print("\tSPEECHSERVER PUT: ", end="")
            data = {"CTM": "0.0 5.0\n5.0 10.0\n10.0 15.0"}
            res = requests.put(BASEURL + inurl, headers=headers, data=json.dumps(data))
            print(res.status_code)
            if res.status_code != 200:
                print('SERVER SAYS:', res.text)                
        else:
            print("User not logged in!")
        print('')


if __name__ == "__main__":
    print('Accessing Docker app server via: http://127.0.0.1:9999/wsgi/')
    proj = Project(projectdbfile=sys.argv[1])

    if len(sys.argv) < 3:
        try:
            while True:
                cmd = raw_input("Enter command (type help for list)> ")
                cmd = cmd.lower()
                if cmd == "exit":
                    proj.logout()
                    proj.adminlout()
                    break
                elif cmd in ["help", "list"]:
                    print("ADMINLIN - Admin login")
                    print("ADMINLOUT - Admin logout")
                    print("ADDUSER - add new user\n")
                    print("LOGIN - user login")
                    print("LOGOUT - user logout")
                    print("LISTCATEGORIES - list project categories")
                    print("CREATEPROJECT - create a new project")
                    print("LISTPROJECTS - list projects")
                    print("LOADPROJECT - load projects")
                    print("UPLOADAUDIO - upload audio to project")
                    print("PROJECTAUDIO - retrieve project audio")
                    print("SAVEPROJECT - save tasks to a project\n")
                    print("ASSIGNTASKS - assign tasks to editors\n")
                    print("DIARIZEAUDIO - save tasks to a project\n")
                    print("EXIT - quit")

                else:
                    try:
                        meth = getattr(proj, cmd)
                        meth()
                    except Exception as e:
                        print('Error processing command:', e)

        except:
            proj.logout()
            proj.adminlout()
            print('')
    else:
        if sys.argv[2].upper() == "ASSIGN":
            proj.login()
            proj.createproject()
            proj.uploadaudio()
            proj.saveproject()
            proj.assigntasks()
            proj.logout()
        if sys.argv[2].upper() == "DIARIZE_ASSIGN":
            proj.login()
            proj.createproject()
            proj.uploadaudio()
            proj.diarizeaudio()
            proj.saveproject()
            proj.assigntasks()
            proj.logout()
        else:
            print("UNKNOWN TASK: {}".format(sys.argv[1]))


