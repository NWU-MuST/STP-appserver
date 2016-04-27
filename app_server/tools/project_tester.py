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

    def addcategories(self):
        if self.admin_token is not None:
            headers = {"Content-Type" : "application/json"}
            cats = [("House",), ("NCOP",), ("Comms",)]
            data = {"token": self.admin_token, "categories" : cats}
            res = requests.post(BASEURL + "projects/admin/addcategories", headers=headers, data=json.dumps(data))
            print('SERVER SAYS:', res.text)
            print(res.status_code)
        else:
            print("Admin not logged in!")
        print('')


if __name__ == "__main__":
    proj = Project()

    try:
        while True:
            cmd = raw_input("Enter command (type help for list)> ")
            cmd = cmd.lower()
            if cmd == "exit":
                break
            elif cmd in ["help", "list"]:
                print("LOGIN - user login")
                print("LOGOUT - user logout")
                print("ADMINLIN - Admin login")
                print("ADMINLOUT - Admin logout")
                print("ADDUSER - add new user")
                print("ADDCATEGORIES - add project categories")
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

