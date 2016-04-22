#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function #Py2

import json
import time
import uuid, base64

import bcrypt #Ubuntu/Debian: apt-get install python-bcrypt

from exceptions import BadRequestError, NotAuthorizedError, ConflictError

class Auth(object):
    def __init__(self, config_file):
        with open(config_file) as infh:
            self._config = json.loads(infh.read())

    def _gen_token(self):
        return base64.b64encode(str(uuid.uuid4()))

    def _token_auth(self, token):
        """Checks whether token is valid/existing and returns associated
           username or None
        """
        username = None
        with sqlite.connect(self._config["authdb_file"]) as db_conn:
            db_curs = db_conn.cursor()
            db_curs.execute("SELECT * FROM tokens WHERE token=?", token)
            entry = db_curs.fetchone()
            if entry is None:
                return None
            else:
                token, username, expiry = entry
                if time.time() > expiry:
                    db_curs.execute("DELETE FROM tokens WHERE token=?", token) #remove expired token
                    db_conn.commit()
                    return None
        return username

    def login(self, request):
        """Validate provided username and password and insert new token into
           tokens and return if successful.  We also use this
           opportunity to clear stale tokens.
        """
        if not set(request.keys()) >= {"username", "password"}:
            raise BadRequestError
        with sqlite.connect(self._config["authdb_file"]) as db_conn:
            #REMOVE STALE TOKENS
            db_curs = db_conn.cursor()
            db_curs.execute("DELETE FROM tokens WHERE ? > expiry", time.time())
            db_conn.commit()
            #PROCEED TO AUTHENTICATE USER
            db_curs.execute("SELECT * FROM users WHERE username=?", request["username"])
            entry = db_curs.fetchone()
            #User exists?
            if entry is None:
                raise NotAuthorizedError("User not registered")
            else:
                username, pwhash, salt, name, surname = entry
                #Password correct?
                if pwhash != bcrypt.hashpw(request["password"], salt):
                    raise NotAuthorizedError("Wrong password")
            #User already logged in?
            db_curs.execute("SELECT * FROM tokens WHERE username=?", username)
            entry = db_curs.fetchone()
            if not entry is None:
                raise ConflictError("User already logged in")
            #All good, create new token, insert and return
            token = self._gen_token()
            db_curs.execute("INSERT INTO tokens (token, username, expiry) VALUES(?,?,?)", (token,
                                                                                           username,
                                                                                           time.time() + self._config["token_lifetime"]))
            db_conn.commit()
        return token #DEMIT: should be JSON package?

    def logout(self, request):
        if not set(request.keys()) >= {"token"}:
            raise BadRequestError
        with sqlite.connect(self._config["authdb_file"]) as db_conn:
            db_curs = db_conn.cursor()
            db_curs.execute("DELETE FROM tokens WHERE token='?'", request["token"])
            db_conn.commit()
