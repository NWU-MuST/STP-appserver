#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function #Py2

import uuid
import json
import time
import datetime
import base64
import auth
import admin

try:
    from sqlite3 import dbapi2 as sqlite
except ImportError:
    from pysqlite2 import dbapi2 as sqlite #for old Python versions

from httperrs import *

class Admin(admin.Admin):
    pass

class Projects(auth.UserAuth):

    def __init__(self, config_file):
        with open(config_file) as infh:
            self._config = json.loads(infh.read())
        self._categories = self._config["categories"]        

    def list_categories(self, request):
        """
            List Admin created project categories
        """
        #AUTHORISE REQUEST
        username = auth.token_auth(request["token"], self._config["authdb"])
        return json.dumps({'categories' : self._categories})

    def create_project(self, request):
        """
            Create a new project for a user
        """
        #AUTHORISE REQUEST
        username = auth.token_auth(request["token"], self._config["authdb"])
        #EXECUTE REQUEST
        projectid = None
        with sqlite.connect(self._config['projectdb']) as db_conn:
            db_curs = db_conn.cursor()

            # Fetch project categories and check user supplied category
            if request["category"] not in self._categories:
                raise BadRequestError('Project category: %s - NOT FOUND' % request["category"])

            # Fetch all projects
            db_curs.execute("SELECT projectid FROM projects")
            projects = db_curs.fetchall()
            if projects is not None:
                projects = set([x[0] for x in projects])
            else:
                projects = set()

            # Find unique project name
            projectid = str(uuid.uuid4())
            while projectid in projects:
                projectid = str(uuid.uuid4())
            projectid = 'p%s' % projectid.replace('-', '')

            table_name = datetime.datetime.now().year

            # Insert new project into project master table
            db_curs.execute("INSERT INTO projects (projectid, projectname, category, username, audiofile, year, creation) VALUES(?,?,?,?,?,?,?)",
                 (projectid, request["projectname"], request["category"], username, "", table_name, time.time()))

            # Create project table
            query = ( "CREATE TABLE IF NOT EXISTS T%s "
            "( projectid VARCHAR(36), editor VARCHAR(20), collator VARCHAR(20), start REAL, end REAL, textfile VARCHAR(64),"
            " timestamp REAL, editorrw VARCHAR(1), collatorrw VARCHAR(1) )" % table_name)
            db_curs.execute(query)
            db_conn.commit()

        return json.dumps({'projectid' : projectid})

    def list_projects(self, request):
        """
            List current projects owned by user
        """
        #AUTHORISE REQUEST
        username = auth.token_auth(request["token"], self._config["authdb"])
        #EXECUTE REQUEST
        projects = []
        with sqlite.connect(self._config['projectdb']) as db_conn:
            # Fetch all projects
            db_curs = db_conn.cursor()
            db_curs.execute("SELECT * FROM projects where username='%s'" % username)
            projects = db_curs.fetchall()

        return json.dumps({'projects' : projects})

    def delete_project(self, request):
        """
            Delete project and remove tasks
        """
        #AUTHORISE REQUEST
        auth.token_auth(request["token"], self._config["authdb"])
        #EXECUTE REQUEST
        with sqlite.connect(self._config['projectdb']) as db_conn:
            db_curs = db_conn.cursor()
            db_curs.execute("SELECT * FROM projects WHERE projectid='%s'" % request["projectid"])
            project_info = db_curs.fetchall()
            db_curs.execute("DELETE FROM projects WHERE projectid='%s'" % request["projectid"])
            table_name = 'T%s' % project_info[0][-2]
            db_curs.execute("DELETE FROM %s WHERE projectid='%s'" % (table_name, request["projectid"]))
            db_conn.commit()
        return json.dumps({'message' : "Project deleted!"})

    def load_project(self, request):
        """
            Load project tasks
        """
        #AUTHORISE REQUEST
        auth.token_auth(request["token"], self._config["authdb"])
        #EXECUTE REQUEST
        with sqlite.connect(self._config['projectdb']) as db_conn:
            db_curs = db_conn.cursor()
            db_curs.execute("SELECT * FROM projects WHERE projectid='%s'" % request["projectid"])
            project_info = db_curs.fetchall()
            table_name = 'T%s' % project_info[0][-2]
            db_curs.execute("SELECT * FROM %s WHERE projectid='%s'" % (table_name, request["projectid"]))
            task_info = db_curs.fetchall()
            db_conn.commit()
        return json.dumps({'tasks' : task_info})

    def save_project(self, request):
        """
            Save the project tasks
        """
        #AUTHORISE REQUEST
        auth.token_auth(request["token"], self._config["authdb"])
        #EXECUTE REQUEST
        with sqlite.connect(self._config['projectdb']) as db_conn:
            db_curs = db_conn.cursor()
            db_curs.execute("SELECT * FROM projects WHERE projectid='%s'" % request["projectid"])
            project_info = db_curs.fetchall()
            table_name = 'T%s' % project_info[0][-2]
            db_curs.execute("DELETE FROM %s WHERE projectid='%s'" % (table_name, request["projectid"]))
            db_curs.executemany("INSERT INTO %s (projectid, editor, collator, start, end, textfile, timestamp, editorrw, collatorrw) VALUES(?,?,?,?,?,?,?,?,?)" % table_name, (request["task"]))
            db_conn.commit()

        return json.dumps({'message' : 'Projects saved!'})

    def upload_audio(self, request):
        """
            Audio uploaded to project space
        """
        #AUTHORISE REQUEST
        username = auth.token_auth(request["token"], self._config["authdb"])
        #EXECUTE REQUEST
        with sqlite.connect(self._config['projectdb']) as db_conn:
            db_curs = db_conn.cursor()
            db_curs.execute("SELECT audiofile FROM projects WHERE projectid='%s'" % request["projectid"])
            audiofile = db_curs.fetchone()
            if audiofile is not None or audiofile[0] != '':
                os.remove(audiofile[0])

        location = os.path.join(self._config["storage"], datetime.datetime.now().strftime('%Y-%M-%d'))
        if not os.path.exists(location):
            os.mkdir(location)

        new_filename = os.path.join(location, base64.urlsafe_b64encode(str(uuid.uuid4())))
        with open(new_filename, 'wb') as f:
            f.write(request['file'])

        with sqlite.connect(self._config['projectdb']) as db_conn:
            db_curs = db_conn.cursor()
            db_curs.execute("UPDATE projects SET audiofile = '%s' WHERE projectid='%s'" % (new_filename, request["projectid"]))
            db_conn.commit()

        return json.dumps({'message' : 'Audio Saved!'})

    def project_audio(self, request):
        """
            Make audio avaliable for project user
        """
        #AUTHORISE REQUEST
        auth.token_auth(request["token"], self._config["authdb"])
        #EXECUTE REQUEST
        with sqlite.connect(self._config['projectdb']) as db_conn:
            db_curs = db_conn.cursor()
            db_curs.execute("SELECT audiofile FROM projects WHERE projectid='%s'" % request["projectid"])
            audiofile = db_curs.fetchone()

        return json.dumps({'filename' : audiofile[0]})

    def diarize_audio(self, request):
        #AUTHORISE REQUEST
        auth.token_auth(request["token"], self._config["authdb"])
        #EXECUTE REQUEST
        raise NotImplementedError


if __name__ == "__main__":
    pass

