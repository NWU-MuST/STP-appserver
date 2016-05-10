#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function #Py2

import json
import time
import uuid, base64
try:
    from sqlite3 import dbapi2 as sqlite
except ImportError:
    from pysqlite2 import dbapi2 as sqlite #for old Python versions

import bcrypt #Ubuntu/Debian: apt-get install python-bcrypt

from httperrs import NotAuthorizedError, ConflictError

def gen_token():
    return base64.b64encode(str(uuid.uuid4()))

def token_auth(token, authdb):
    """Checks whether token is valid/existing in authdb and returns associated
       username or raises NotAuthorizedError
    """
    username = None
    with sqlite.connect(authdb) as db_conn:
        db_curs = db_conn.cursor()
        db_curs.execute("SELECT * FROM tokens WHERE token=?", (token,))
        entry = db_curs.fetchone()
        if entry is None:
            raise NotAuthorizedError
        else:
            token, username, expiry = entry
            if time.time() > expiry:
                db_curs.execute("DELETE FROM tokens WHERE token=?", (token,)) #remove expired token
                db_conn.commit()
                raise NotAuthorizedError
    return username

class UserAuth(object):
    def __init__(self, config_file=None):
        if config_file is not None:
            with open(config_file) as infh:
                self._config = json.loads(infh.read())

    def login(self, request):
        """Validate provided username and password and insert new token into
           tokens and return if successful.  We also use this
           opportunity to clear stale tokens.
             - The DB/service actually logged into is determined by
               the service as setup in the dispatcher
        """
        with sqlite.connect(self._config["authdb"]) as db_conn:
            #REMOVE STALE TOKENS
            db_curs = db_conn.cursor()
            db_curs.execute("DELETE FROM tokens WHERE ? > expiry", (time.time(),))
            db_conn.commit()
            #PROCEED TO AUTHENTICATE USER
            db_curs.execute("SELECT * FROM users WHERE username=?", (request["username"],))
            entry = db_curs.fetchone()
            #User exists?
            if entry is None:
                raise NotAuthorizedError("User not registered")
            else:
                username, pwhash, salt, name, surname, email = entry
                #Password correct?
                if pwhash != bcrypt.hashpw(request["password"], salt):
                    raise NotAuthorizedError("Wrong password")
            #User already logged in?
            db_curs.execute("SELECT * FROM tokens WHERE username=?", (username,))
            entry = db_curs.fetchone()
            if not entry is None:
                raise ConflictError("User already logged in")
            #All good, create new token, insert and return
            token = gen_token()
            db_curs.execute("INSERT INTO tokens (token, username, expiry) VALUES(?,?,?)", (token,
                                                                                           username,
                                                                                           time.time() + self._config["toklife"]))
            db_conn.commit()
        return {"token": token}

    def logout(self, request):
        """The DB/service actually logged out of is determined by the service
           as setup in the dispatcher
        """
        with sqlite.connect(self._config["authdb"]) as db_conn:
            db_curs = db_conn.cursor()
            db_curs.execute("DELETE FROM tokens WHERE token='%s'" % request["token"])
            db_conn.commit()
        return json.dumps({'message' : "User logged out"})

def test():
    """Informal tests...
    """
    import sys, os
    sys.path = [os.path.abspath("../tools")] + sys.path
    from authdb import create_new_db
    #testuser
    salt = bcrypt.gensalt()
    pwhash = bcrypt.hashpw("testpass", salt)
    #create test DB and add testuser
    db_conn = create_new_db("/tmp/test.db")
    db_curs = db_conn.cursor()
    db_curs.execute("INSERT INTO users ( username, pwhash, salt, name, surname, email ) VALUES (?,?,?,?,?,?)", ("testuser", pwhash, salt, "", "", ""))
    db_conn.commit()
    #test UserAuth
    a = UserAuth()
    a._config = {}
    a._config["authdb"] = "/tmp/test.db"
    a._config["toklife"] = 0
    ## 1
    try:
        print(a.login({"username": "testuser", "password": "wrongpass"}))
    except NotAuthorizedError:
        print("TEST_1 SUCCESS:", "Wrong password caught...")
    ## 2
    tokenpackage = a.login({"username": "testuser", "password": "testpass"})
    print("TEST_2 SUCCESS:", "User authenticated with token:", tokenpackage["token"])
    ## 3
    try:
        username = token_auth(tokenpackage["token"], a._config["authdb"])
        print("TEST_3 FAILED:", "Authenticated against expired token")
    except NotAuthorizedError:
        print("TEST_3 SUCCESS:", "Do not authenticate against expired token")
    ## 4
    a._config["toklife"] = 300
    tokenpackage = a.login({"username": "testuser", "password": "testpass"}) #should have been removed from tokens in previous test
    username = token_auth(tokenpackage["token"], a._config["authdb"])
    if username is not None:
        print("TEST_4 SUCCESS:", "Authenticated logged in username:", username)
    else:
        print("TEST_4 FAILED:", "Could not authenticated logged in username")
    ## 5
    try:
        print(a.login({"username": "testuser", "password": "testpass"}))
    except ConflictError:
        print("TEST_5 SUCCESS:", "Already logged in caught...")
    ## 6
    a.logout(tokenpackage)
    try:
        username = token_auth(tokenpackage["token"], a._config["authdb"])
        print("TEST_6 FAILED:", "Authenticated against logged out token")
    except NotAuthorizedError:
        print("TEST_6 SUCCESS:", "Do not authenticate against logged out token")

if __name__ == "__main__":
    test()
