#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function #Py2

try:
    from sqlite3 import dbapi2 as sqlite
except ImportError:
    from pysqlite2 import dbapi2 as sqlite

import bcrypt #Ubuntu/Debian: apt-get install python-bcrypt

import json
import auth
from httperrs import BadRequestError, ConflictError, NotFoundError

class Admin(auth.UserAuth):
    """Implements all functions related to updating user information in
       the auth database.
    """
    def add_user(self, request):
        auth.token_auth(request["token"], self._config["authdb"])
        salt = bcrypt.gensalt()
        pwhash = bcrypt.hashpw(request["password"], salt)
        try:
            with sqlite.connect(self._config["target_authdb"]) as db_conn:
                db_curs = db_conn.cursor()
                db_curs.execute("INSERT INTO users (username, pwhash, salt, name, surname, email) VALUES (?,?,?,?,?,?)", (request["username"],
                                                                                                                          pwhash,
                                                                                                                          salt,
                                                                                                                          request["name"],
                                                                                                                          request["surname"],
                                                                                                                          request["email"]))
                db_conn.commit()
        except sqlite.IntegrityError as e:
            raise ConflictError(e)
        except KeyError as e:
            raise BadRequestError(e)
        return "User added"

    def del_user(self, request):
        auth.token_auth(request["token"], self._config["authdb"])
        with sqlite.connect(self._config["target_authdb"]) as db_conn:
            db_curs = db_conn.cursor()
            db_curs.execute("DELETE FROM users WHERE username='%s'" % request["username"])
            db_conn.commit()
        return "User removed"

    def get_uinfo(self, request):
        auth.token_auth(request["token"], self._config["authdb"])
        with sqlite.connect(self._config["target_authdb"]) as db_conn:
            db_curs = db_conn.cursor()
            db_curs.execute("SELECT * FROM users WHERE username=?", (request["username"],))
            entry = db_curs.fetchone()
            if entry is None:
                raise NotFoundError("User not registered")
            else:
                username, pwhash, salt, name, surname, email = entry
                return {"name": name, "surname": surname, "email": email}
