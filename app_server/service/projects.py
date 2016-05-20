#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function #Py2

import uuid
import json
import time
import datetime
import base64
import os

import auth
import admin

try:
    from sqlite3 import dbapi2 as sqlite
except ImportError:
    from pysqlite2 import dbapi2 as sqlite #for old Python versions

from httperrs import BadRequestError, NotFoundError

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
        username = auth.token_auth(request["token"], self._config["authdb"])
        return {'categories' : self._categories}

    def create_project(self, request):
        """
            Create a new project for a user
        """
        username = auth.token_auth(request["token"], self._config["authdb"])

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

        return {'projectid' : projectid}

    def list_projects(self, request):
        """
            List current projects owned by user
        """
        username = auth.token_auth(request["token"], self._config["authdb"])

        projects = []
        with sqlite.connect(self._config['projectdb']) as db_conn:
            # Fetch all projects
            db_curs = db_conn.cursor()
            db_curs.execute("SELECT * FROM projects where username='%s'" % username)
            projects = db_curs.fetchall()

        return {'projects' : projects}

    def delete_project(self, request):
        """
            Delete project and remove tasks
        """
        auth.token_auth(request["token"], self._config["authdb"])

        with sqlite.connect(self._config['projectdb']) as db_conn:
            db_curs = db_conn.cursor()
            db_curs.execute("SELECT * FROM projects WHERE projectid='%s'" % request["projectid"])
            project_info = db_curs.fetchall()
            db_curs.execute("DELETE FROM projects WHERE projectid='%s'" % request["projectid"])
            table_name = 'T%s' % project_info[0][-2]
            db_curs.execute("DELETE FROM %s WHERE projectid='%s'" % (table_name, request["projectid"]))
            db_conn.commit()
        return "Project deleted!"

    def load_project(self, request):
        """
            Load project tasks
        """
        auth.token_auth(request["token"], self._config["authdb"])

        with sqlite.connect(self._config['projectdb']) as db_conn:
            db_curs = db_conn.cursor()
            db_curs.execute("SELECT * FROM projects WHERE projectid='%s'" % request["projectid"])
            project_info = db_curs.fetchall()
            table_name = 'T%s' % project_info[0][-2]
            db_curs.execute("SELECT * FROM %s WHERE projectid='%s'" % (table_name, request["projectid"]))
            task_info = db_curs.fetchall()
            db_conn.commit()
        return {'project' : project_info, 'tasks' : task_info}

    def save_project(self, request):
        """
            Save the project tasks
        """
        auth.token_auth(request["token"], self._config["authdb"])

        with sqlite.connect(self._config['projectdb']) as db_conn:
            db_curs = db_conn.cursor()
            db_curs.execute("SELECT * FROM projects WHERE projectid='%s'" % request["projectid"])
            project_info = db_curs.fetchall()
            table_name = 'T%s' % project_info[0][-2]
            audiodir = os.path.dirname(project_info[0][-3])

            task = []
            for editor, collator, start, end in request["tasks"]:
                textfile = os.path.join(audiodir, base64.urlsafe_b64encode(str(uuid.uuid4())))
                open(textfile, 'wb').close()
                task.append((request["projectid"], editor, collator, float(start), float(end), textfile, time.time(), 'Y', 'N'))

            db_curs.execute("DELETE FROM %s WHERE projectid='%s'" % (table_name, request["projectid"]))
            db_curs.executemany("INSERT INTO %s (projectid, editor, collator, start, end, textfile, timestamp, editorrw, collatorrw) VALUES(?,?,?,?,?,?,?,?,?)" % table_name, (task))
            db_conn.commit()

        return 'Project saved!'

    def upload_audio(self, request):
        """
            Audio uploaded to project space
            TODO: convert audio to OGG Vorbis, mp3splt for editor
        """
        username = auth.token_auth(request["token"], self._config["authdb"])

        with sqlite.connect(self._config['projectdb']) as db_conn:
            db_curs = db_conn.cursor()
            db_curs.execute("SELECT audiofile FROM projects WHERE projectid='%s'" % request["projectid"])
            audiofile = db_curs.fetchone()
            if audiofile is not None and audiofile[0] != '':
                os.remove(audiofile[0])

        location = os.path.join(self._config["storage"], datetime.datetime.now().strftime('%Y-%m-%d'), username)
        if not os.path.exists(location):
            os.makedirs(location)

        new_filename = os.path.join(location, base64.urlsafe_b64encode(str(uuid.uuid4())))
        with open(new_filename, 'wb') as f:
            f.write(request['file'])

        with sqlite.connect(self._config['projectdb']) as db_conn:
            db_curs = db_conn.cursor()
            db_curs.execute("UPDATE projects SET audiofile = '%s' WHERE projectid='%s'" % (new_filename, request["projectid"]))
            db_conn.commit()

        return 'Audio Saved!'

    def project_audio(self, request):
        """
            Make audio avaliable for project user
        """
        auth.token_auth(request["token"], self._config["authdb"])

        with sqlite.connect(self._config['projectdb']) as db_conn:
            db_curs = db_conn.cursor()
            db_curs.execute("SELECT audiofile FROM projects WHERE projectid='%s'" % request["projectid"])
            audiofile = db_curs.fetchone()

        return {'filename' : audiofile[0]}

    def diarize_audio(self, request):
        auth.token_auth(request["token"], self._config["authdb"])
        
        #Attempt to "lock" project and create I/O access
        with sqlite.connect(self._config['projectdb']) as db_conn:
            db_curs = db_conn.cursor()
            db_curs.execute("BEGIN IMMEDIATE") #lock the db early...
            db_curs.execute("SELECT * FROM projects WHERE projectid=?", (request["projectid"],))
            entry = db_curs.fetchone()
            #Project exists?
            if entry is None:
                db_conn.commit()
                raise NotFoundError("Project not found")
            #Project clean? #DEMIT: Also check whether already split into tasks?
            projid, projname, projcat, username, audiofile, year, creation, jobid, errstatus = entry
            if jobid:
                db_conn.commit()
                raise ConflictError("A job with id '{}' is already pending on this project".format(jobid))
            
            #Setup I/O access
            inurl = auth.gen_token()
            outurl = auth.gen_token()
            db_curs.execute("UPDATE projects SET jobid=? WHERE projectid=?", ("pending",
                                                                              request["projectid"]))
            db_curs.execute("INSERT INTO incoming (projectid, url) VALUES (?,?)", (request["projectid"],
                                                                                   inurl))
            db_curs.execute("INSERT INTO outgoing (projectid, url, audiofile) VALUES (?,?,?)", (request["projectid"],
                                                                                                outurl,
                                                                                                audiofile))
            db_conn.commit()
        #Make job request
        jobreq = {"input": outurl, "output": inurl}
        reqstatus = {"jobid": auth.gen_token()} #DEMIT: dummy call!
        #Handle request status
        if "jobid" in reqstatus: #no error
            with sqlite.connect(self._config['projectdb']) as db_conn:
                db_curs = db_conn.cursor()
                db_curs.execute("UPDATE projects SET jobid=? WHERE projectid=?", (reqstatus["jobid"],
                                                                                  request["projectid"]))
                db_conn.commit()
            return "Request successful!"
        #Something went wrong: undo project setup
        with sqlite.connect(self._config['projectdb']) as db_conn:
            db_curs = db_conn.cursor()
            db_curs.execute("UPDATE projects SET jobid=? WHERE projectid=?", ("",
                                                                              request["projectid"]))
            db_curs.execute("DELETE FROM incoming WHERE projectid=?", (request["projectid"],))
            db_curs.execute("DELETE FROM outgoing WHERE projectid=?", (request["projectid"],))
            db_conn.commit()
        return reqstatus #DEMIT TODO: translate error from speech server!

    def outgoing(self, env):
        uri = os.path.basename(env['PATH_INFO'])
        with sqlite.connect(self._config['projectdb']) as db_conn:
            db_curs = db_conn.cursor()
            db_curs.execute("SELECT * FROM outgoing WHERE url=?", (uri,))
            entry = db_curs.fetchone()
            #URL exists?
            if entry is None:
                return None
            projectid, url, audiofile = entry
            db_curs.execute("DELETE FROM outgoing WHERE url=?", (uri,))
            db_conn.commit()
        return {"mime": "audio/ogg", "filename": audiofile}

    def incoming(self, env):
        uri = env['PATH_INFO']
        raise NotImplementedError
            

if __name__ == "__main__":
    pass

