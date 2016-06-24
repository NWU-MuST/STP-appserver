#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function #Py2

import requests
import sys
import json
import os
import readline

BASEURL = "http://127.0.0.1:9999/wsgi/"

readline.parse_and_bind('tab: complete')
readline.parse_and_bind('set editing-mode vi')

class Editor:

    def __init__(self):
        self.user_token = None
        self.admin_token = None
        self.this_task = None

    def login(self):
        """
            Login as user
            Place user 'token' in self.user_token
        """
        if self.user_token is None:
            headers = {"Content-Type" : "application/json"}
            data = {"username": "neil", "password": "neil"}
            res = requests.post(BASEURL + "editor/login", headers=headers, data=json.dumps(data))
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
            res = requests.post(BASEURL + "editor/admin/login", headers=headers, data=json.dumps(data))
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
            res = requests.post(BASEURL + "editor/admin/logout", headers=headers, data=json.dumps(data))
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
            res = requests.post(BASEURL + "editor/logout", headers=headers, data=json.dumps(data))
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
            res = requests.post(BASEURL + "editor/admin/adduser", headers=headers, data=json.dumps(data))
            print('SERVER SAYS:', res.text)
            print(res.status_code)
        else:
            print("Admin not logged in!")
        print('')

    def loadtasks(self):
        """
            Load all tasks belonging to neil
        """
        if self.user_token is not None:
            headers = {"Content-Type" : "application/json"}
            data = {"token": self.user_token}
            res = requests.post(BASEURL + "editor/loadtasks", headers=headers, data=json.dumps(data))
            print('SERVER SAYS:', res.text)
            print(res.status_code)
            pkg = res.json()
            self.this_task = pkg['CANOPEN'][0]
            self.taskid = self.this_task['taskid']
            self.projectid = self.this_task['projectid']
            print(self.taskid, self.projectid)
        else:
            print("User not logged in!")
        print('')

    def getaudio(self):
        """
            Return a portion of audio for the task
        """
        if self.user_token is not None and self.projectid is not None:
            params = {'token' : self.user_token, 'projectid' : self.projectid, 'taskid' : self.taskid}
            res = requests.get(BASEURL + "editor/getaudio", params=params)
            print(res.status_code)
            if res.status_code == 200:
                with open('taskrange.ogg', 'wb') as f:
                    f.write(res.content)
            else:
                print('SERVER SAYS:', res.text)
        else:
            print("User not logged in!")
        print('')

    def savetext(self):
        """
            Save text to task text file
        """
        if self.user_token is not None and self.projectid is not None:
            headers = {"Content-Type" : "application/json"}
            data = {'token' : self.user_token, 'projectid' : self.projectid, 'taskid' : self.taskid, "text" : "Hello world!"}
            res = requests.post(BASEURL + "editor/savetext", headers=headers, data=json.dumps(data))
            print('SERVER SAYS:', res.text)
            print(res.status_code)
        else:
            print("User not logged in!")
        print('')

    def cleartext(self):
        """
            Remove text from file
        """
        if self.user_token is not None and self.projectid is not None:
            headers = {"Content-Type" : "application/json"}
            data = {'token' : self.user_token, 'projectid' : self.projectid, 'taskid' : self.taskid, "text" : ""}
            res = requests.post(BASEURL + "editor/savetext", headers=headers, data=json.dumps(data))
            print('SERVER SAYS:', res.text)
            print(res.status_code)
        else:
            print("User not logged in!")
        print('')

    def gettext(self):
        """
            Return the task's text
        """
        if self.user_token is not None and self.projectid is not None:
            headers = {"Content-Type" : "application/json"}
            data = {'token' : self.user_token, 'projectid' : self.projectid, 'taskid' : self.taskid}
            res = requests.post(BASEURL + "editor/gettext", headers=headers, data=json.dumps(data))
            print('SERVER SAYS:', res.text)
            print(res.status_code)
            pkg = res.json()
            print('TEXT', pkg['text'])
        else:
            print("User not logged in!")
        print('')

    def taskdone(self):
        """
            Assign the task to collator
        """
        if self.user_token is not None and self.projectid is not None:
            headers = {"Content-Type" : "application/json"}
            data = {'token' : self.user_token, 'projectid' : self.projectid, 'taskid' : self.taskid}
            res = requests.post(BASEURL + "editor/taskdone", headers=headers, data=json.dumps(data))
            print('SERVER SAYS:', res.text)
            print(res.status_code)
        else:
            print("User not logged in!")
        print('')

    def unlocktask(self):
        """
            Cancel a scheduled job
        """
        if self.user_token is not None and self.projectid is not None:
            headers = {"Content-Type" : "application/json"}
            data = {'token' : self.user_token, 'projectid' : self.projectid, 'taskid' : self.taskid}
            res = requests.post(BASEURL + "editor/unlocktask", headers=headers, data=json.dumps(data))
            print('SERVER SAYS:', res.text)
            print(res.status_code)
        else:
            print("User not logged in!")
        print('')

    def diarize(self):
        """
            Submit a diarize speech job
        """
        if self.user_token is not None and self.projectid is not None:
            headers = {"Content-Type" : "application/json"}
            data = {'token' : self.user_token, 'projectid' : self.projectid, 'taskid' : self.taskid}
            res = requests.post(BASEURL + "editor/diarize", headers=headers, data=json.dumps(data))
            print('SERVER SAYS:', res.text)
            print(res.status_code)
        else:
            print("User not logged in!")
        print('')

    def recognize(self):
        """
            Submit a recognize speech job
        """
        if self.user_token is not None and self.projectid is not None:
            headers = {"Content-Type" : "application/json"}
            data = {'token' : self.user_token, 'projectid' : self.projectid, 'taskid' : self.taskid}
            res = requests.post(BASEURL + "editor/recognize", headers=headers, data=json.dumps(data))
            print('SERVER SAYS:', res.text)
            print(res.status_code)
        else:
            print("User not logged in!")
        print('')

    def align(self):
        """
            Submit a align speech job
        """
        if self.user_token is not None and self.projectid is not None:
            headers = {"Content-Type" : "application/json"}
            data = {'token' : self.user_token, 'projectid' : self.projectid, 'taskid' : self.taskid}
            res = requests.post(BASEURL + "editor/align", headers=headers, data=json.dumps(data))
            print('SERVER SAYS:', res.text)
            print(res.status_code)
        else:
            print("User not logged in!")
        print('')

    def clearerror(self):
        """
            Clear error status
        """
        if self.user_token is not None and self.projectid is not None:
            headers = {"Content-Type" : "application/json"}
            data = {'token' : self.user_token, 'projectid' : self.projectid, 'taskid' : self.taskid}
            res = requests.post(BASEURL + "editor/clearerror", headers=headers, data=json.dumps(data))
            print('SERVER SAYS:', res.text)
            print(res.status_code)
            pkg = res.json()
        else:
            print("User not logged in!")
        print('')


if __name__ == "__main__":
    print('Accessing Docker app server via: http://127.0.0.1:9999/wsgi/')
    edit = Editor()

    if len(sys.argv) < 2:
        try:
            while True:
                cmd = raw_input("Enter command (type help for list)> ")
                cmd = cmd.lower()
                if cmd == "exit":
                    edit.logout()
                    edit.adminlout()
                    break
                elif cmd in ["help", "list"]:
                    print("ADMINLIN - Admin login")
                    print("ADMINLOUT - Admin logout")
                    print("ADDUSER - add new user\n")
                    print("LOGIN - user login")
                    print("LOGOUT - user logout\n")
                    print("LOADTASKS - load tasks belonging to user")
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
                    print("EXIT - quit")

                else:
                    try:
                        meth = getattr(edit, cmd)
                        meth()
                    except Exception as e:
                        print('Error processing command:', e)

        except:
            edit.logout()
            edit.adminlout()
            print('')
    else:
        if sys.argv[1].upper() == "ASSIGN":
            pass
        else:
            print("UNKNOWN TASK: {}".format(sys.argv[1]))

