#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function #Py2

try:
    from sqlite3 import dbapi2 as sqlite
except ImportError:
    from pysqlite2 import dbapi2 as sqlite

from auth import Auth
from exceptions import BadRequestError, ConflictError

class Admin(Auth):
    """Implements all functions related to updating user information in
       the auth database.
    """

    def adduser(self, request):
        if not set(request.keys()) >= {"username", "password", "name", "surname", "email"}:
            raise BadRequestError
        salt = bcrypt.gensalt()
        pwhash = bcrypt.hashpw(request["password"], salt)
        try:
            with sqlite.connect(self._config["authdb_file"]) as db_conn:
                db_curs = db_conn.cursor()
                db_curs.execute("INSERT INTO users (username, pwhash, salt, name, surname, email)", (request["username"],
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

    def deluser(self, request):
        if not set(request.keys()) >= {"username"}:
            raise BadRequestError
        with sqlite.connect(self._config["authdb_file"]) as db_conn:
            db_curs = db_conn.cursor()
            db_curs.execute("DELETE FROM users WHERE username='?'", request["username"])
            db_conn.commit()
        
