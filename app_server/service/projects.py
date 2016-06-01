#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function #Py2


#standard library
import uuid
import json
import time
import datetime
import base64
import os
import logging
try:
    from sqlite3 import dbapi2 as sqlite
except ImportError:
    from pysqlite2 import dbapi2 as sqlite #for old Python versions

#3rd party
import requests #Ubuntu/Debian: apt-get install python-requests

#local
import auth
import admin
import repo
from httperrs import *

LOG = logging.getLogger("APP.PROJECTS")

SPEECHSERVER = os.getenv("SPEECHSERVER"); assert SPEECHSERVER is not None
APPSERVER = os.getenv("APPSERVER"); assert APPSERVER is not None

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
        LOG.info("Returning list of project categories")
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

            year = datetime.datetime.now().year

            # Insert new project into project master table
            db_curs.execute("INSERT INTO projects (projectid, projectname, category, username, audiofile, year, creation, assigned) VALUES(?,?,?,?,?,?,?,?)",
                            (projectid, request["projectname"], request["category"], username, "", year, time.time(), "N"))

            # Create project table
            table_name = "T{}".format(year)
            query = ( "CREATE TABLE IF NOT EXISTS {} ".format(table_name) +\
                      "( taskid INTEGER, projectid VARCHAR(36), editor VARCHAR(20), collator VARCHAR(20), "
                      "start REAL, end REAL, language VARCHAR(20), "
                      "textfile VARCHAR(64), creation REAL, modified REAL, commitid VARCHAR(40), "
                      "ownership INTEGER, jobid VARCHAR(36), errstatus VARCHAR(128) )" )
            db_curs.execute(query)
            db_conn.commit()
        LOG.info("Created new project with ID: {}".format(projectid))
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
            db_curs.execute("SELECT * FROM projects where username=?", (username,))
            projects = db_curs.fetchall()
        LOG.info("Returning list of projects")
        return {'projects' : projects}

    def delete_project(self, request):
        """
            Delete project and remove tasks
        """
        auth.token_auth(request["token"], self._config["authdb"])

        with sqlite.connect(self._config['projectdb']) as db_conn:
            db_curs = db_conn.cursor()
            db_curs.execute("SELECT year "
                            "FROM projects "
                            "WHERE projectid=?", (request["projectid"],))
            year, = db_curs.fetchone()
            db_curs.execute("DELETE FROM projects "
                            "WHERE projectid=?", (request["projectid"],))
            table_name = "T{}".format(year)
            db_curs.execute("DELETE FROM {} ".format(table_name) +\
                            "WHERE projectid=?", (request["projectid"],))
            db_conn.commit()
        LOG.info("Deleted project with ID: {}".format(request["projectid"]))
        return "Project deleted!"

    def load_project(self, request):
        """
            Load project tasks
        """
        auth.token_auth(request["token"], self._config["authdb"])

        with sqlite.connect(self._config['projectdb']) as db_conn:
            db_conn.row_factory = sqlite.Row
            db_curs = db_conn.cursor()
            db_curs.execute("SELECT projectname, category, year "
                            "FROM projects "
                            "WHERE projectid=?", (request["projectid"],))
            project = dict(db_curs.fetchone())
            tasktable = "T{}".format(project["year"])
            db_curs.execute("SELECT editor, collator, start, end, language "
                            "FROM {} ".format(tasktable) +\
                            "WHERE projectid=?", (request["projectid"],))
            tasks = db_curs.fetchall()
            db_conn.commit()
        LOG.info("Returning loaded project with ID: {}".format(request["projectid"]))
        return {'project' : dict(project), 'tasks' : map(dict, tasks)}

    def save_project(self, request):
        """Save the project state (assignments and task partitioning) in the
           interim. This can only be run BEFORE `assign_tasks` and
           usually after partitioning (e.g. via speech diarize or the
           UI or both). To update assignees or toggle permissions
           after assignment use `update_project`
        """
        auth.token_auth(request["token"], self._config["authdb"])
        #DEMIT: Does the user also need to save other project meta-info (maybe in `update_project`)?
        #DEMIT: Need to check whether tasks have already been assigned
        #DEMIT: Check no jobid pending
        with sqlite.connect(self._config['projectdb']) as db_conn:
            db_curs = db_conn.cursor()
            db_curs.execute("SELECT year "
                            "FROM projects "
                            "WHERE projectid=?", (request["projectid"],))
            year, = db_curs.fetchone()
            tasktable = "T{}".format(year)

            tasks_in = request["tasks"] #A list of dicts
            #DEMIT: Where are we checking for contiguous non-overlapping exhaustive segments (maybe enforce in UI)?
            tasks_in.sort(key=lambda x:x["start"])
            tasks_out = []
            for taskid, task in enumerate(tasks_in):
                tasks_out.append((taskid, request["projectid"], task["editor"], task["collator"], float(task["start"]), float(task["end"]), task["language"]))

            db_curs.execute("DELETE FROM {} ".format(tasktable) +\
                            "WHERE projectid=?", (request["projectid"],))
            db_curs.executemany("INSERT INTO {} ".format(tasktable) +\
                                "(taskid, projectid, editor, collator, start, end, language)"
                                "VALUES(?,?,?,?,?,?,?)", tasks_out)
            db_conn.commit()

        LOG.info("Saved project with ID: {}".format(request["projectid"]))
        return 'Project saved!'

    def assign_tasks(self, request):
        """Assign tasks to editors:
            - Create documents associated with speech segments
            - Ensure that tasks table is fully completed (i.a. editors assigned)
            - Sets permissions appropriately
            - Sets project state to `assigned` disallowing revision of task segments
        """
        auth.token_auth(request["token"], self._config["authdb"])

        #DEMIT: Need to check whether tasks have already been assigned
        #DEMIT: Check no jobid/errstatus
        with sqlite.connect(self._config['projectdb']) as db_conn:
            db_conn.row_factory = sqlite.Row
            db_curs = db_conn.cursor()
            db_curs.execute("SELECT audiofile, year "
                            "FROM projects "
                            "WHERE projectid=?", (request["projectid"],))
            audiofile, year = db_curs.fetchone()
            audiodir = os.path.dirname(audiofile)
            tasktable = "T{}".format(year)
            db_curs.execute("SELECT * "
                            "FROM {} ".format(tasktable) +\
                            "WHERE projectid=?", (request["projectid"],))
            tasks = map(dict, db_curs.fetchall())
            
            #CREATE FILES AND UPDATE FIELDS
            #DEMIT: Todo - cleanup `audiodir` if necessary
            textname = "text"
            for task in tasks:
                textdir = os.path.join(audiodir, str(task["taskid"]).zfill(3))
                os.makedirs(textdir)
                repo.init(textdir)
                task["textfile"] = os.path.join(textdir, textname)
                open(task["textfile"], "wb").close()
                task["creation"] = time.time()
                task["commitid"], task["modified"] = repo.commit(textdir, textname, "task assigned")
                task["ownership"] = 0 #Actually need an ownership ENUM: {0: "editor", 1: "collator"}
                #Make sure all required fields are set and update table row
                undefined = (None, "")
                assert all(v not in undefined for k, v in task.iteritems() if k not in ["jobid", "errstatus"])
                updatefields = ("editor", "collator", "textfile", "creation", "modified", "commitid", "ownership")
                LOG.debug(tuple([task[k] for k in updatefields] + [task["projectid"], task["taskid"]]))
                db_curs.execute("UPDATE {} ".format(tasktable) +\
                                "SET {} ".format(", ".join(field +"=?" for field in updatefields)) +\
                                "WHERE projectid=? AND taskid=?", tuple([task[k] for k in updatefields] + [task["projectid"], task["taskid"]]))
            db_conn.commit()
        LOG.info("Assigned tasks for project with ID: {}".format(request["projectid"]))
        return 'Project tasks assigned!'

    def update_project(self, request):
        """Update assignees and/or permissions on tasks and/or other project
           meta information
        """
        raise NotImplementedError


    def upload_audio(self, request):
        """
            Audio uploaded to project space
            TODO: convert audio to OGG Vorbis, mp3splt for editor
        """
        username = auth.token_auth(request["token"], self._config["authdb"])

        with sqlite.connect(self._config['projectdb']) as db_conn:
            db_curs = db_conn.cursor()
            db_curs.execute("SELECT audiofile FROM projects WHERE projectid=?", (request["projectid"],))
            audiofile = db_curs.fetchone()
            if audiofile is not None and audiofile[0] != '':
                os.remove(audiofile[0])

        date_now = datetime.datetime.now()
        location = os.path.join(self._config["storage"], username, str(date_now.year), str(date_now.month).zfill(2), str(date_now.day).zfill(2), request["projectid"])
        if not os.path.exists(location):
            os.makedirs(location)

        new_filename = os.path.join(location, base64.urlsafe_b64encode(str(uuid.uuid4())))
        with open(new_filename, 'wb') as f:
            f.write(request['file'])

        with sqlite.connect(self._config['projectdb']) as db_conn:
            db_curs = db_conn.cursor()
            db_curs.execute("UPDATE projects SET audiofile=? WHERE projectid=?", (new_filename, request["projectid"]))
            db_conn.commit()
        LOG.info("Audio uploaded for project ID: {}".format(request["projectid"]))
        return 'Audio Saved!'

    def project_audio(self, request):
        """
            Make audio available for project user
        """
        auth.token_auth(request["token"], self._config["authdb"])

        with sqlite.connect(self._config['projectdb']) as db_conn:
            db_curs = db_conn.cursor()
            db_curs.execute("SELECT audiofile FROM projects WHERE projectid=?", (request["projectid"],))
            audiofile = db_curs.fetchone()
        LOG.info("Returning audio for project ID: {}".format(request["projectid"]))
        return {'filename' : audiofile[0]}

    def diarize_audio(self, request):
        auth.token_auth(request["token"], self._config["authdb"])
        
        #Attempt to "lock" project and create I/O access
        with sqlite.connect(self._config['projectdb']) as db_conn:
            db_curs = db_conn.cursor()
            db_curs.execute("BEGIN IMMEDIATE") #lock the db early...
            db_curs.execute("SELECT audiofile, jobid "
                            "FROM projects "
                            "WHERE projectid=?", (request["projectid"],))
            entry = db_curs.fetchone()
            #Project exists?
            if entry is None:
                db_conn.commit()
                raise NotFoundError("Project not found")
            audiofile, jobid = entry
            #Project clean? #DEMIT: Also check whether already split into tasks?
            if jobid:
                db_conn.commit()
                raise ConflictError("A job with id '{}' is already pending on this project".format(jobid))
            #Setup I/O access
            inurl = auth.gen_token()
            outurl = auth.gen_token()
            db_curs.execute("UPDATE projects "
                            "SET jobid=? "
                            "WHERE projectid=?", ("pending",
                                                  request["projectid"]))
            db_curs.execute("INSERT INTO incoming "
                            "(projectid, url, servicetype) VALUES (?,?,?)", (request["projectid"],
                                                                          inurl,
                                                                          "diarize"))
            db_curs.execute("INSERT INTO outgoing "
                            "(projectid, url, audiofile) VALUES (?,?,?)", (request["projectid"],
                                                                           outurl,
                                                                           audiofile))
            db_conn.commit()
        #Make job request
        # TEMPORARILY COMMENTED OUT FOR TESTING WITHOUT SPEECHSERVER:
        # jobreq = {"token" : request["token"], "getaudio": os.path.join(APPSERVER, outurl),
        #           "putresult": os.path.join(APPSERVER, inurl), "service" : "diarize", "subsystem" : "default"}
        # LOG.debug(os.path.join(SPEECHSERVER, self._config["speechservices"]["diarize"]))
        # reqstatus = requests.post(os.path.join(SPEECHSERVER, self._config["speechservices"]["diarize"]), data=json.dumps(jobreq))
        # reqstatus = reqstatus.json()
        reqstatus = {"jobid": auth.gen_token()} #DEMIT: dummy call for testing!
        #TODO: handle return status
        LOG.debug("{}".format(reqstatus))
        #Handle request status
        if "jobid" in reqstatus: #no error
            with sqlite.connect(self._config['projectdb']) as db_conn:
                db_curs = db_conn.cursor()
                db_curs.execute("UPDATE projects "
                                "SET jobid=? "
                                "WHERE projectid=?", (reqstatus["jobid"],
                                                      request["projectid"]))
                db_conn.commit()
            LOG.info("Diarize audio request sent for project ID: {}, job ID: {}".format(request["projectid"], reqstatus["jobid"]))
            return "Request successful!"
        #Something went wrong: undo project setup
        with sqlite.connect(self._config['projectdb']) as db_conn:
            db_curs = db_conn.cursor()
            db_curs.execute("UPDATE projects "
                            "SET jobid=? "
                            "WHERE projectid=?", (None,
                                                  request["projectid"]))
            db_curs.execute("DELETE FROM incoming "
                            "WHERE projectid=?", (request["projectid"],))
            db_curs.execute("DELETE FROM outgoing "
                            "WHERE projectid=?", (request["projectid"],))
            db_conn.commit()
        LOG.info("Diarize audio request failed for project ID: {}".format(request["projectid"]))
        return reqstatus #DEMIT TODO: translate error from speech server!

    def outgoing(self, uri):
        with sqlite.connect(self._config['projectdb']) as db_conn:
            db_curs = db_conn.cursor()
            db_curs.execute("SELECT projectid, audiofile "
                            "FROM outgoing WHERE url=?", (uri,))
            entry = db_curs.fetchone()
            #URL exists?
            if entry is None:
                raise MethodNotAllowedError(uri)
            projectid, audiofile = entry
            db_curs.execute("DELETE FROM outgoing WHERE url=?", (uri,))
            db_conn.commit()
        LOG.info("Returning audio for project ID: {}".format(projectid))
        return {"mime": "audio/ogg", "filename": audiofile}


    def incoming(self, uri, data):
        LOG.debug("incoming_data: {}".format(data))
        with sqlite.connect(self._config['projectdb']) as db_conn:
            db_curs = db_conn.cursor()
            db_curs.execute("SELECT projectid, servicetype "
                            "FROM incoming "
                            "WHERE url=?", (uri,))
            entry = db_curs.fetchone()
        #URL exists?
        if entry is None:
            raise MethodNotAllowedError(uri)
        projectid, servicetype = entry
        #Switch to handler for "servicetype"
        assert servicetype in self._config["speechservices"], "servicetype '{}' not supported...".format(servicetype)
        #assert data["projectid"] == projectid, "Unexpected Project ID..."
        handler = getattr(self, "_incoming_{}".format(servicetype))
        handler(data, projectid) #will throw exception if not successful
        #Cleanup DB
        with sqlite.connect(self._config['projectdb']) as db_conn:
            db_curs = db_conn.cursor()
            db_curs.execute("DELETE FROM incoming "
                            "WHERE url=?", (uri,))
            db_conn.commit()
        LOG.info("Incoming data processed for project ID: {}".format(projectid))
        return "Request successful!"


    def _incoming_diarize(self, data, projectid):
        LOG.debug("_i_d")
        #projectid = data["projectid"]
        with sqlite.connect(self._config['projectdb']) as db_conn:
            db_curs = db_conn.cursor()
            db_curs.execute("SELECT year, jobid "
                            "FROM projects "
                            "WHERE projectid=?", (projectid,))
            entry = db_curs.fetchone()
            #Need to check whether project exists?
            year, jobid = entry
            tasktable = "T{}".format(year)
            if "CTM" in data: #all went well
                LOG.info("Diarisation success (Project ID: {}, Job ID: {})".format(projectid, jobid))
                #Parse CTM file
                segments = [map(float, line.split()) for line in data["CTM"].splitlines()]
                segments.sort(key=lambda x:x[0]) #by starttime
                LOG.info("CTM parsing successful..")
                tasktable = "T{}".format(year)
                db_curs.execute("DELETE FROM {} ".format(tasktable) +\
                                "WHERE projectid=?", (projectid,)) #assume already OK'ed
                for taskid, (starttime, endtime) in enumerate(segments):
                    db_curs.execute("INSERT INTO {} (taskid, projectid, start, end) VALUES(?,?,?,?)".format(tasktable),
                                    (taskid, projectid, starttime, endtime))
                db_curs.execute("UPDATE projects SET jobid=?, errstatus=? WHERE projectid=?", (None, None, projectid))
            else: #"unlock" and recover error status
                LOG.info("Diarisation failure (Project ID: {}, Job ID: {})".format(projectid, jobid))
                db_curs.execute("UPDATE projects SET jobid=?, errstatus=? WHERE projectid=?", (None, data["errstatus"], projectid))
            db_conn.commit()
        LOG.info("Diarization result received successfully for project ID: {}".format(projectid))

if __name__ == "__main__":
    pass

