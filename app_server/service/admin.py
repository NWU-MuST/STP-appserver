#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function #Py2

import json
import logging
import os

try:
    from sqlite3 import dbapi2 as sqlite
except ImportError:
    from pysqlite2 import dbapi2 as sqlite

import bcrypt #Ubuntu/Debian: apt-get install python-bcrypt

import auth
from httperrs import BadRequestError, ConflictError, NotFoundError

LOG = logging.getLogger("APP.ADMIN")

class Admin(auth.UserAuth):
    """Implements all functions related to updating user information in
       the auth database.
    """
    def add_user(self, request):
        self.authdb.authenticate(request["token"], self._config["role"])
        salt, pwhash = auth.hash_pw(request["password"])
        try:
            with sqlite.connect(self._config["target_authdb"]) as db_conn:
                db_curs = db_conn.cursor()
                db_curs.execute("INSERT INTO users (username, pwhash, salt, name, surname, email, role, tmppwhash) VALUES (?,?,?,?,?,?,?,?)", (request["username"],
                                                                                                                                       pwhash,
                                                                                                                                       salt,
                                                                                                                                       request["name"],
                                                                                                                                       request["surname"],
                                                                                                                                       request["email"],
                                                                                                                                       request["role"],
                                                                                                                                       None))
        except sqlite.IntegrityError as e:
            raise ConflictError(e)
        except KeyError as e:
            raise BadRequestError(e)
        LOG.info("Added new user: {}".format(request["username"]))
        return "User added"

    def del_user(self, request):
        self.authdb.authenticate(request["token"], self._config["role"])
        with sqlite.connect(self._config["target_authdb"]) as db_conn:
            db_curs = db_conn.cursor()
            db_curs.execute("DELETE FROM users WHERE username=?", (request["username"],))
        LOG.info("Deleted user: {}".format(request["username"]))
        return "User removed"

    def get_uinfo(self, request):
        self.authdb.authenticate(request["token"], self._config["role"])
        with sqlite.connect(self._config["target_authdb"]) as db_conn:
            db_curs = db_conn.cursor()
            db_curs.execute("SELECT * FROM users WHERE username=?", (request["username"],))
            entry = db_curs.fetchone()
            if entry is None:
                raise NotFoundError("User not registered")
            username, pwhash, salt, name, surname, email, role, tmppwhash = entry
        LOG.info("Returning info for user: {}".format(request["username"]))
        return {"name": name, "surname": surname, "email": email, "role": role}

    def update_user(self, request):
        self.authdb.authenticate(request["token"], self._config["role"])
        with sqlite.connect(self._config["target_authdb"]) as db_conn:
            db_curs = db_conn.cursor()
            #User exists?
            db_curs.execute("SELECT * FROM users WHERE username=?", (request["username"],))
            entry = db_curs.fetchone()
            if entry is None:
                raise NotFoundError("User not registered")
            #Proceed to update
            for field in ["name", "surname", "email", "role"]:
                if field in request:
                    db_curs.execute("UPDATE users SET {}=? WHERE username=?".format(field), (request[field], request["username"]))
            if "password" in request:
                salt, pwhash = auth.hash_pw(request["password"])
                db_curs.execute("UPDATE users SET pwhash=? WHERE username=?", (pwhash, request["username"]))
                db_curs.execute("UPDATE users SET salt=? WHERE username=?", (salt, request["username"]))
        LOG.info("Updated info for user: {}".format(request["username"]))
        return "User info updated"

    def get_users(self, request):
        self.authdb.authenticate(request["token"], self._config["role"])
        users = dict()
        with sqlite.connect(self._config["target_authdb"]) as db_conn:
            db_curs = db_conn.cursor()
            for entry in db_curs.execute("SELECT * FROM users WHERE role LIKE '%{}%'".format(request["role"])).fetchall():
                username, pwhash, salt, name, surname, email, role, tmppwhash = entry
                users[username] = {"name": name, "surname": surname, "email": email}
        LOG.info("Returning user list")
        return users

