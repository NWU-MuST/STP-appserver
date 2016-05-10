#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function #Py2

import requests
import sys
import json

BASEURL = "http://127.0.0.1:9999/wsgi/"


class Project:

    def __init__(self):
        self.user_token = None
        self.admin_token = None

    def login(self):
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
        if self.user_token is not None and self.projectid is not None:
            params = {'token' : self.user_token, 'projectid' : self.projectid}
            res = requests.get(BASEURL + "projects/projectaudio", params=params)
            print(res.status_code)
            if res.status_code == 200:
                with open('tmp.bin', 'wb') as f:
                    f.write(res.content)
            else:
                print('SERVER SAYS:', res.text)
        else:
            print("User not logged in!")
        print('')


    def uploadaudio(self):
        if self.user_token is not None and self.projectid is not None:
            files = {'file' : open('test.mp3', 'rb'), 'filename' : 'test.mp3', 'token' : self.user_token, 'projectid' : self.projectid}
            res = requests.post(BASEURL + "projects/uploadaudio", files=files)
            print('SERVER SAYS:', res.text)
            print(res.status_code)
        else:
            print("User not logged in!")
        print('')


if __name__ == "__main__":
    proj = Project()

    try:
        while True:
            cmd = raw_input("Enter command (type help for list)> ")
            cmd = cmd.lower()
            if cmd == "exit":
                proj.logout()
                proj.adminlout()
                break
            elif cmd in ["help", "list"]:
                print("LOGIN - user login")
                print("LOGOUT - user logout")
                print("ADMINLIN - Admin login")
                print("ADMINLOUT - Admin logout")
                print("ADDUSER - add new user")
                print("LISTCATEGORIES - list project categories")
                print("CREATEPROJECT - create a new project")
                print("LISTPROJECTS - list projects")
                print("LOADPROJECT - load projects")
                print("UPLOADAUDIO - upload audio to project")
                print("EXIT - quit")

            else:
                try:
                    meth = getattr(proj, cmd)
                    meth()
                except:
                    print('UNKWOWN COMMAND')

    except:
        proj.logout()
        proj.adminlout()
        print('')

