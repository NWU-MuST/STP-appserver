#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function #Py2

import json
import logging
import os
import base64
import uuid
import requests
import copy

try:
    from sqlite3 import dbapi2 as sqlite
except ImportError:
    from pysqlite2 import dbapi2 as sqlite

import bcrypt #Ubuntu/Debian: apt-get install python-bcrypt

import auth
from httperrs import *

LOG = logging.getLogger("APP.ADMIN")

SPEECHSERVER = os.getenv("SPEECHSERVER"); assert SPEECHSERVER is not None
APPSERVER = os.getenv("APPSERVER"); assert APPSERVER is not None

class Admin(auth.UserAuth):
    def __init__(self, config_file, speechserv):
        #Provides: self._config and self.authdb
        auth.UserAuth.__init__(self, config_file)
        self._speech = speechserv
        self._role = self._config["role"]
        #DB connection setup:
        self.db = sqlite.connect(self._config['projectdb'], factory=ProjectDB)
        self.db.row_factory = sqlite.Row
        self._custom_msg = {}

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
        """ Remover user
        """
        self.authdb.authenticate(request["token"], self._config["role"])
        with sqlite.connect(self._config["target_authdb"]) as db_conn:
            db_curs = db_conn.cursor()
            db_curs.execute("DELETE FROM users WHERE username=?", (request["username"],))
        LOG.info("Deleted user: {}".format(request["username"]))
        return "User removed"

    def get_uinfo(self, request):
        """ Get user information
        """
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
        """ Update a user's particulars
        """
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
        """ Return a list of all users
        """
        self.authdb.authenticate(request["token"], self._config["role"])
        users = dict()
        with sqlite.connect(self._config["target_authdb"]) as db_conn:
            db_curs = db_conn.cursor()
            for entry in db_curs.execute("SELECT * FROM users").fetchall():
                username, pwhash, salt, name, surname, email, role, tmppwhash = entry
                users[username] = {"name": name, "surname": surname, "email": email, "role" : role}
        LOG.info("Returning user list")
        return users

    def custom_lm(self, request):
        """ Add text to build a custom language model
        """
        self.authdb.authenticate(request["token"], self._config["role"])
        # Bogus projectid
        projectid = "clm-{}".format(str(uuid.uuid4()))
        # Write text data to temporary file
        textfile = os.path.join(self._config["tmpdir"], auth.gen_token()) 
        with open(textfile, 'wb') as f:
            f.write(request['file'])
        # Add entries in db
        inurl = auth.gen_token()
        outurl = auth.gen_token()
        with self.db as db:
            db.insert_incoming(projectid, url=inurl, servicetype="customlm")
            db.insert_outgoing(projectid, url=outurl, audiofile=textfile)
        # request speech job
        try:
            jobreq = {"token" : self._speech.token(), "gettext": os.path.join(APPSERVER, "admin", outurl),
                    "putresult": os.path.join(APPSERVER, "admin", inurl), "service" : "customlm", "subsystem" : request["subsystem"], "system_name" : request["name"]}
            LOG.debug(os.path.join(SPEECHSERVER, self._config["speechservices"]["customlm"]))
            reqstatus = requests.post(os.path.join(SPEECHSERVER, self._config["speechservices"]["customlm"]), data=json.dumps(jobreq))
            reqstatus = reqstatus.json()
            LOG.debug("CustomLM: reqstatus={}".format(reqstatus))
            #Check reqstatus from SpeechServ OK?
            if not "jobid" in reqstatus:
                raise Exception("CustomLM request failed, SpeechServ says: {}".format(reqstatus["message"]))
            return {"projectid" : projectid}
        except:
            # Cleanup ... things went wrong
            with self.db as db: 
                db.delete_incoming(projectid)
                db.delete_outgoing(projectid)

            if os.path.exists(textfile):
                os.remove(textfile)
            raise

    def custom_lm_query(self, request):
        """ Return custom lm data and clear it
        """
        self.authdb.authenticate(request["token"], self._config["role"])
        LOG.info(request["projectid"])
        with self.db as db:
            row = db.get_message(request["projectid"])
        if bool(row) == False:
            row = "No record found for key!"
        return row

    def clear_message(self, request):
        """ Clear the entire message table
        """
        self.authdb.authenticate(request["token"], self._config["role"])
        with self.db as db:
            row = db.clear_message()
        return "Message records cleared!"

    def outgoing(self, uri):
        """ Return the text document
        """
        try:
            LOG.info("ENTER: url={}".format(uri))
            with self.db as db: 
                row = db.get_outgoing(uri)
                if not row:
                    raise MethodNotAllowedError(uri)
            LOG.info("OK: (url={} projectid={}) Returning text file".format(uri, row["projectid"]))
            return {"mime": "text/plain", "filename": row["audiofile"], "savename" : "customlm.txt"}
        except Exception as e:
            LOG.info("FAIL: {}".format(e))
            raise

    def incoming(self, uri, data):
        """ Save data for retrievel
        """
        LOG.debug("ENTER: url={} data={}".format(uri, data))
        try:
            LOG.info("ENTER: url={}".format(uri))
            with self.db as db: 
                row = db.get_incoming(uri)
            if not row: #url exists?
                raise MethodNotAllowedError(uri)
            #Switch to handler for "servicetype"
            if not row["servicetype"] in self._config["speechservices"]:
                raise Exception("Service type '{}' not defined in AppServer".format(row["servicetype"]))
            LOG.info(row["projectid"])
            with self.db as db:
                db.set_message(row["projectid"], str(data["message"]))

            LOG.info("OK: (url={} projectid={}) Incoming data processed".format(uri, row["projectid"]))
            return "Request successful!"
        except Exception as e:
            LOG.info("FAIL: {}".format(e))
            raise

class ProjectDB(sqlite.Connection):
    def lock(self):
        self.execute("BEGIN IMMEDIATE")

    def insert_incoming(self, projectid, url, servicetype):
        self.execute("INSERT INTO incoming "
                     "(projectid, url, servicetype) "
                     "VALUES (?,?,?)", (projectid, url, servicetype))

    def insert_outgoing(self, projectid, url, audiofile):
        self.execute("INSERT INTO outgoing "
                     "(projectid, url, audiofile) "
                     "VALUES (?,?,?)", (projectid, url, audiofile))

    def delete_incoming(self, projectid):
        self.execute("DELETE FROM incoming "
                     "WHERE projectid=?", (projectid,))

    def delete_outgoing(self, projectid):
        self.execute("DELETE FROM outgoing "
                     "WHERE projectid=?", (projectid,))

    def get_outgoing(self, url):
        row = self.execute("SELECT projectid, audiofile "
                           "FROM outgoing WHERE url=?", (url,)).fetchone()
        if row is not None:
            self.execute("DELETE FROM outgoing WHERE url=?", (url,))
            row = dict(row)
        else:
            row = {}
        return row

    def get_incoming(self, url):
        row = self.execute("SELECT projectid, servicetype "
                           "FROM incoming WHERE url=?", (url,)).fetchone()
        if row is not None:
            self.execute("DELETE FROM incoming WHERE url=?", (url,))
            row = dict(row)
        else:
            row = {}
        return row

    def set_message(self, key, message):
        self.execute("INSERT INTO message (key, message) VALUES(?,?)", (key, message))

    def get_message(self, key):
        row = self.execute("SELECT message FROM message WHERE key=?", (key,)).fetchone()
        if row is not None:
            self.execute("DELETE FROM message WHERE key=?", (key,))
            row = dict(row)
        else:
            row = {}
        return row

    def clear_message(self):
        self.lock()
        self.execute("DELETE FROM message")
        self.execute("VACUUM")

if __name__ == "__main__":
    pass

