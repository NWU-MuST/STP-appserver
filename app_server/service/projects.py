#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function #Py2

import uuid
import json
import auth
import admin
from timestamp import timestamp_now

try:
    from sqlite3 import dbapi2 as sqlite
except ImportError:
    from pysqlite2 import dbapi2 as sqlite #for old Python versions

from httperrs import *

class Admin(admin.Admin):

    def add_categories(self, request):
        #AUTHORISE REQUEST
        username = auth.token_auth(request["token"], self._config["authdb"])
        with sqlite.connect(self._config['projectdb']) as db_conn:
            db_curs = db_conn.cursor()
            db_curs.execute("DROP TABLE IF EXISTS projectcategories")
            db_curs.execute("CREATE TABLE projectcategories ( category VARCHAR(36) PRIMARY KEY )")
            db_curs.executemany("INSERT INTO projectcategories (category) VALUES(?)", request['categories'])
            db_conn.commit()
        return json.dumps({"message" : "New categories added"})

class Projects(auth.UserAuth):

    def __init__(self, config_file):
        with open(config_file) as infh:
            self._config = json.loads(infh.read())

    def list_categories(self, request):
        #AUTHORISE REQUEST
        username = auth.token_auth(request["token"], self._config["authdb"])
        categories = [()]
        with sqlite.connect(self._config['projectdb']) as db_conn:
            # Fetch all projects
            db_curs = db_conn.cursor()
            db_curs.execute("SELECT category FROM projectcategories")
            categories = db_curs.fetchall()
        return json.dumps({'categories' : categories})


    def create_project(self, request):
        #AUTHORISE REQUEST
        username = auth.token_auth(request["token"], self._config["authdb"])
        #EXECUTE REQUEST
        projectid = None
        with sqlite.connect(self._config['projectdb']) as db_conn:
            # Fetch all projects
            db_curs = db_conn.cursor()
            db_curs.execute("SELECT projectname FROM projects")
            projects = db_curs.fetchall()

            if projects is not None:
                projects = set([x[0] for x in projects])
            else:
                projects = set()
            # Find unique project name
            projectid = str(uuid.uuid4())
            while projectid in projects:
                projectid = str(uuid.uuid4())

            db_curs.execute("INSERT INTO projects (projectid, projectname, category, username, creation) VALUES(?,?,?,?,?)",
                 (projectid, request["projectname"], request["category"], username, timestamp_now()))

            # Create this table
            query = ( "CREATE TABLE %s ( id PRIMARY KEY, editor VARCHAR(20), collator VARCHAR(20), "
                 " start INTEGER, end INTEGER, audiofile VARCHAR(64), textfile VARCHAR(64), "
                 " timestamp TIMESTAMP, editorrw VARCHAR(1), collatorrw VARCHAR(1))" % projectid)
            db_curs.execute(query)
            db_conn.commit()

        return projectname

    def list_projects(self, request):
        #AUTHORISE REQUEST
        username = auth.token_auth(request["token"], self._config["authdb"])
        #EXECUTE REQUEST
        projects = [()]
        with sqlite.connect(self._config['projectdb']) as db_conn:
            # Fetch all projects
            db_curs = db_conn.cursor()
            db_curs.execute("SELECT * FROM projects where username='%s'" % username)
            projects = db_curs.fetchall()

        return projects


    def load_project(self, request):
        #AUTHORISE REQUEST
        auth.token_auth(request["token"], self._config["authdb"])
        #EXECUTE REQUEST
        raise NotImplementedError

    def save_project(self, request):
        #AUTHORISE REQUEST
        auth.token_auth(request["token"], self._config["authdb"])
        #EXECUTE REQUEST
        raise NotImplementedError

    def delete_project(self, request):
        #AUTHORISE REQUEST
        auth.token_auth(request["token"], self._config["authdb"])
        #EXECUTE REQUEST
        raise NotImplementedError

    def upload_audio(self, request):
        #AUTHORISE REQUEST
        auth.token_auth(request["token"], self._config["authdb"])
        #EXECUTE REQUEST
        raise NotImplementedError

    def project_audio(self, request):
        #AUTHORISE REQUEST
        auth.token_auth(request["token"], self._config["authdb"])
        #EXECUTE REQUEST
        raise NotImplementedError

if __name__ == "__main__":
    pass

