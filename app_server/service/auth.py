#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function #Py2

import string
import random
import json
import time
import uuid, base64
import logging
try:
    from sqlite3 import dbapi2 as sqlite
except ImportError:
    from pysqlite2 import dbapi2 as sqlite #for old Python versions

import bcrypt #Ubuntu/Debian: apt-get install python-bcrypt

from httperrs import NotAuthorizedError, ConflictError

LOG = logging.getLogger("APP.AUTH")

def gen_pword(length=7):
    alphabet = string.ascii_letters + string.digits + '!@#$%^&*()'
    return "".join(random.choice(alphabet) for i in range(length))

def gen_token():
    return base64.urlsafe_b64encode(str(uuid.uuid4()))

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
                username, pwhash, salt, name, surname, email, tmppwhash = entry
                #Password correct?
                templogin = False
                inpwhash = bcrypt.hashpw(request["password"], salt)
                if pwhash != inpwhash:
                    templogin = True
                    if tmppwhash:
                        if tmppwhash != inpwhash:
                            raise NotAuthorizedError("Wrong password")
                    else:
                        raise NotAuthorizedError("Wrong password")
            #User already logged in?
            db_curs.execute("SELECT * FROM tokens WHERE username=?", (username,))
            entry = db_curs.fetchone()
            if not entry is None:
                raise ConflictError("User already logged in")
            #All good, create new token, remove tmppwhash
            token = gen_token()
            db_curs.execute("INSERT INTO tokens (token, username, expiry) VALUES(?,?,?)", (token,
                                                                                           username,
                                                                                           time.time() + self._config["toklife"]))
            db_curs.execute("UPDATE users SET tmppwhash=? WHERE username=?", (None, username))
        LOG.info("User login: {}".format(request["username"]))
        return {"token": token, "templogin": templogin}

    def logout(self, request):
        """The DB/service actually logged out of is determined by the service
           as setup in the dispatcher
        """
        with sqlite.connect(self._config["authdb"]) as db_conn:
            db_curs = db_conn.cursor()
            db_curs.execute("SELECT * FROM tokens WHERE token=?", (request["token"],))
            entry = db_curs.fetchone()
            if entry is None:
                raise NotAuthorizedError("Token not valid")
            token, username, expiry = entry
            db_curs.execute("DELETE FROM tokens WHERE token=?",  (request["token"],))
        LOG.info("User logout: {}".format(username))
        return "User logged out"

    def logout2(self, request):
        """Validate provided username and password and remove token associated
           with this user if successful.  We also use this opportunity
           to clear stale tokens.
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
                username, pwhash, salt, name, surname, email, tmppwhash = entry
                #Password correct?
                inpwhash = bcrypt.hashpw(request["password"], salt)
                if pwhash != inpwhash:
                    if tmppwhash:
                        if tmppwhash != inpwhash:
                            raise NotAuthorizedError("Wrong password")
                    else:
                        raise NotAuthorizedError("Wrong password")
            #logout
            db_curs.execute("DELETE FROM tokens WHERE username=?", (username,))
        LOG.info("User logout: {}".format(username))
        return "User logged out"

    def change_password(self, request):
        """Allows a logged-in user (token) to change the password.
        """
        raise NotImplementedError
        # with sqlite.connect(self._config["authdb"]) as db_conn:
        #     db_curs = db_conn.cursor()
        #     db_curs.execute("SELECT * FROM tokens WHERE token=?", (request["token"],))
        #     entry = db_curs.fetchone()
        #     if entry is None:
        #         raise NotAuthorizedError("Token not valid")
        #     token, username, expiry = entry

    def reset_password(self, request):
        """Generates a random new temporary password for one-time use and
           sends this to the registered email address

           DEMIT: May also want to request using email -- but have to
           ensure unique email fields in Admin.add_user
        """
        with sqlite.connect(self._config["authdb"]) as db_conn:
            db_curs = db_conn.cursor()
            #Get user info
            db_curs.execute("SELECT * FROM users WHERE username=?", (request["username"],))
            entry = db_curs.fetchone()
            #User exists?
            if entry is None:
                raise NotAuthorizedError("User not registered")
            else:
                username, pwhash, salt, name, surname, email, tmppwhash = entry
            #Generate random password and insert
            tmppw = gen_pword()
            tmppwhash = bcrypt.hashpw(tmppw, salt)
            db_curs.execute("UPDATE users SET tmppwhash=? WHERE username=?", (tmppwhash, username))
        #DEMIT: NotImplementedError: At some point email this automatically to the user
        LOG.info("Temp password created: {}".format(username))
        return tmppw
        
            

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
    db_curs.execute("INSERT INTO users ( username, pwhash, salt, name, surname, email, tmppwhash ) VALUES (?,?,?,?,?,?,?)", ("testuser", pwhash, salt, None, None, None, None))
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
