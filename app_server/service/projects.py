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
import shutil
import subprocess
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
DEBUG = 10 
INFO = 20

SPEECHSERVER = os.getenv("SPEECHSERVER"); assert SPEECHSERVER is not None
APPSERVER = os.getenv("APPSERVER"); assert APPSERVER is not None
SOXI_BIN = "/usr/bin/soxi"; assert os.stat(SOXI_BIN)

class Admin(admin.Admin):
    pass

class Projects(auth.UserAuth):

    def __init__(self, config_file):
        with open(config_file) as infh:
            self._config = json.loads(infh.read())
        self._categories = self._config["categories"]
        #DB connection setup:
        self.db = sqlite.connect(self._config['projectdb'], factory=ProjectDB)
        self.db.row_factory = sqlite.Row

    def list_categories(self, request):
        """List Admin-created project categories
        """
        username = auth.token_auth(request["token"], self._config["authdb"])
        LOG.info("Returning list of project categories")
        return {'categories' : self._categories}

    def create_project(self, request):
        """Create a new project for a user
        """
        username = auth.token_auth(request["token"], self._config["authdb"])

        # Fetch project categories and check user supplied category
        if request["category"] not in self._categories:
            raise BadRequestError('Project category: %s - NOT FOUND' % request["category"])

        with self.db as db:
            db.lock()
            # Fetch all projects
            projects = set(row["projectid"] for row in db.get_projects(["projectid"]))

            # Find unique project name (the reason we need to lock the DB)
            projectid = str(uuid.uuid4())
            while projectid in projects:
                projectid = str(uuid.uuid4())
            projectid = 'p%s' % projectid.replace('-', '')
            year = datetime.datetime.now().year

            # Insert new project into project master table and create relevant tasks table (if needed)
            db.insert_project({"projectid": projectid,
                               "projectname": request["projectname"],
                               "category": request["category"],
                               "username": username,
                               "year": year,
                               "creation": time.time(),
                               "assigned": "N"})
            db.create_tasktable(year)
        ##########
        LOG.info("ProjID:{} Created new project".format(projectid))
        return {'projectid' : projectid}

    def list_projects(self, request):
        """List current projects owned by user
        """
        username = auth.token_auth(request["token"], self._config["authdb"])

        with self.db as db:
            projects = db.get_projects(where={"username": username})
        ##########
        LOG.info("User:{} Returning list of projects".format(username))
        return {'projects' : projects}

    def delete_project(self, request):
        """Delete project and remove tasks, including all associated files.
        """
        auth.token_auth(request["token"], self._config["authdb"])

        #Clear project from DB
        with self.db as db:
            row = db.get_project(request["projectid"], ["audiofile"])
            db.delete_project(request["projectid"])
        #Remove any files associated with project
        if row:
            projectpath = os.path.dirname(row["audiofile"])
        shutil.rmtree(projectpath, ignore_errors=True)
        ##########
        LOG.info("ProjID:{} Deleted project".format(request["projectid"]))
        return "Project deleted!"

    def load_project(self, request):
        """Load project tasks
        """
        auth.token_auth(request["token"], self._config["authdb"])

        with self.db as db:
            #This will lock the DB:
            db.check_project(projectid, check_err=True) #later "try" to recover from certain issues
            project = db.get_project(request["projectid"],
                                     fields=["projectname", "category", "year"])
            tasks = db.get_tasks(request["projectid"],
                                 fields=["editor", "collator", "start", "end", "language"])
        ##########
        LOG.info("ProjID: {} Returning loaded project".format(request["projectid"]))
        return {'project' : project, 'tasks' : tasks}

    def save_project(self, request):
        """Save the project state (assignments and task partitioning) in the
           interim. This can only be run BEFORE `assign_tasks` and
           usually after partitioning (e.g. via speech diarize or the
           UI or both). To update assignees or toggle permissions
           after assignment use `update_project`

           DEMIT: The user also needs to save other project meta-info
        """
        auth.token_auth(request["token"], self._config["authdb"])

        #Check whether all necessary fields are defined for each task
        fields = ("taskid", "projectid", "editor", "collator", "start", "end", "language")
        tasks = list(request["tasks"])
        for task in tasks:
            if not all(k in task for k in fields):
                log_raise("ProjID:{} Tasks do not contain all the required fields".format(required["projectid"]),
                          BadRequestError)

        #Check received tasks are: contiguous, non-overlapping,
        #completely spanning audiofile (implicitly: audio uploaded)
        tasks.sort(key=lambda x:x["start"])
        prevtask_end = 0.0
        for task in tasks:
            if not approx_eq(prevtask_end, task["start"]):
                log_raise("ProjID:{} Tasks times not contiguous and non-overlapping".format(request["projectid"]),
                          BadRequestError)
            prevtask_end = task["end"]

        with self.db as db:
            #This will lock the DB:
            db.check_project(projectid, check_err=True) #later "try" to recover from certain issues
            row = db.get_project(request["projectid"], fields=["audiodur"])
            #Check audio has been uploaded
            if row["audiodur"] is None:
                log_raise("ProjID:{} No audio has been uploaded".format(request["projectid"]),
                          ConflictError)
            #Check tasks span audio
            if not approx_eq(row["audiodur"], prevtask_end):
                log_raise("ProjID:{} Tasks do not span entire audio file".format(request["projectid"]),
                          BadRequestError)
            #Check whether tasks already assigned
            if db.project_assigned(request["projectid"]):
                log_raise("ProjID:{} Cannot be re-saved because tasks are already assigned (use: update_project())".format(request["projectid"]),
                          ConflictError)
            #Delete current list of tasks and re-insert from input
            self.delete_tasks(projectid)
            self.insert_tasks(projectid, tasks, fields)
            #DEMIT: Also want to update other project meta-info
        ##########
        LOG.info("ProjID:{} Saved project".format(request["projectid"]))
        return 'Project saved!'

    def assign_tasks(self, request):
        """Assign tasks to editors:
            - Create documents associated with speech segments
            - Ensure that tasks table is fully completed (i.a. editors assigned)
            - Sets permissions appropriately
            - Sets project state to `assigned` disallowing revision of task segments

           DEMIT: Check tasks present.
        """
        auth.token_auth(request["token"], self._config["authdb"])

        with self.db as db:
            #This will lock the DB:
            db.check_project(projectid, check_err=True) #later "try" to recover from certain issues
            if db.project_assigned(request["projectid"]):
                log_raise("ProjID:{} Tasks have already been assigned".format(request["projectid"]),
                          ConflictError)
            #Fetch tasks and project info
            row = db.get_project(request["projectid"], fields=["audiofile"])
            tasks = db.get_tasks(request["projectid"])
            #Lock the project
            db.lock_project(request["projectid"], jobid="assign_tasks")
        try:
            #Create files and update fields
            textname = "text"
            updatefields = ("editor", "collator", "textfile", "creation", "modified", "commitid", "ownership")
            audiodir = os.path.dirname(row["audiofile"])
            for task in tasks:
                textdir = os.path.join(audiodir, str(task["taskid"]).zfill(3))
                os.makedirs(textdir) #should succeed...
                repo.init(textdir)
                task["textfile"] = os.path.join(textdir, textname)
                open(task["textfile"], "wb").close()
                task["commitid"], task["creation"] = repo.commit(textdir, textname, "task assigned")
                task["modified"] = task["creation"]
                task["ownership"] = 0 #Actually need an ownership ENUM: {0: "editor", 1: "collator"}
            #Update fields and unlock project
            with self.db as db:
                db.update_tasks(request["projectid"], tasks, fields=updatefields)
                db.update_project(request["projectid"], fields={"assigned": "Y", "jobid": None})
            LOG.info("ProjID:{} Assigned tasks".format(request["projectid"]))
            return 'Project tasks assigned!'
        except:
            #UNLOCK THE PROJECT AND SET ERRSTATUS
            with self.db as db:
                db.unlock_project(request["projectid"], errstatus="assign_tasks")
            raise


    def update_project(self, request):
        """Update assignees and/or permissions on tasks and/or other project
           meta information. Can only be run after task assignment.

           DEMIT: Task ID valid?
        """
        raise NotImplementedError

    def unlock_project(self, request):
        raise NotImplementedError


    def upload_audio(self, request):
        """Audio uploaded to project space
           TODO: convert audio to OGG Vorbis, mp3splt for editor

           DEMIT: Must clear task table.
        """
        username = auth.token_auth(request["token"], self._config["authdb"])

        #If audiofile already exists remove it
        with self.db as db:
            row = db.get_project(request["projectid"], ["audiofile"])
            if row and row["audiofile"]:
                os.remove(audiofile)

        date_now = datetime.datetime.now()
        location = os.path.join(self._config["storage"], username, str(date_now.year), str(date_now.month).zfill(2), str(date_now.day).zfill(2), request["projectid"])
        if not os.path.exists(location):
            os.makedirs(location)

        new_filename = os.path.join(location, base64.urlsafe_b64encode(str(uuid.uuid4())))
        with open(new_filename, 'wb') as f:
            f.write(request['file'])
        audiodur = float(subprocess.check_output([SOXI_BIN, "-D", new_filename]))

        with sqlite.connect(self._config['projectdb']) as db_conn:
            db_curs = db_conn.cursor()
            db_curs.execute("UPDATE projects SET audiofile=?, audiodur=? WHERE projectid=?", (new_filename, audiodur, request["projectid"]))
            db_conn.commit()
        LOG.info("ProjID:{} Audio uploaded".format(request["projectid"]))
        return 'Audio Saved!'

    def project_audio(self, request):
        """
            Make audio available for project user
        
            DEMIT: Rename to get_audio
            DEMIT: Check audio exists
        """
        auth.token_auth(request["token"], self._config["authdb"])

        with sqlite.connect(self._config['projectdb']) as db_conn:
            db_curs = db_conn.cursor()
            db_curs.execute("SELECT audiofile FROM projects WHERE projectid=?", (request["projectid"],))
            audiofile = db_curs.fetchone()
        LOG.info("ProjID:{} Returning audio for project".format(request["projectid"]))
        return {'filename' : audiofile[0]}

    def diarize_audio(self, request):
        """ DEMIT: Check for audio...
        """
        auth.token_auth(request["token"], self._config["authdb"])
        db = sqlite.connect(self._config['projectdb'])
        db.row_factory = sqlite.Row
        
        #CHECK PROJECTS DB IS UNLOCKED AND SANE + CREATE IO ACCESS
        with db:
            db.execute("BEGIN IMMEDIATE") #lock the db early...
            row = db.execute("SELECT audiofile, assigned, jobid, errstatus "
                             "FROM projects "
                             "WHERE projectid=?", (request["projectid"],)).fetchone()
            if row is None: #project exists?
                raise NotFoundError("Project not found")
            row = dict(row)
            if row["jobid"]: #project clean?
                raise ConflictError("A job with id '{}' is already pending on this project".format(jobid))
            elif row["errstatus"]:
                raise ConflictError("A previous job resulted in error: '{}'".format(row["errstatus"]))
            elif row["assigned"].upper() == "Y":
                raise ConflictError("Tasks have already been assigned")
            #Lock the project and setup I/O access
            inurl = auth.gen_token()
            outurl = auth.gen_token()
            db.execute("UPDATE projects "
                            "SET jobid=? "
                            "WHERE projectid=?", ("diarize_audio",
                                                  request["projectid"]))
            db.execute("INSERT INTO incoming "
                            "(projectid, url, servicetype) VALUES (?,?,?)", (request["projectid"],
                                                                             inurl,
                                                                             "diarize"))
            db.execute("INSERT INTO outgoing "
                            "(projectid, url, audiofile) VALUES (?,?,?)", (request["projectid"],
                                                                           outurl,
                                                                           row["audiofile"]))
        #MAKE JOB REQUEST

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
            with db:
                db.execute("UPDATE projects "
                           "SET jobid=? "
                           "WHERE projectid=?", (reqstatus["jobid"],
                                                 request["projectid"]))
            LOG.info("ProjID:{} JobID:{} Diarize audio request sent.".format(request["projectid"], reqstatus["jobid"]))
            return "Request successful!"
        #Something went wrong: undo project setup
        with db:
            db.execute("UPDATE projects "
                       "SET jobid=? "
                       "WHERE projectid=?", (None,
                                             request["projectid"]))
            db.execute("DELETE FROM incoming "
                       "WHERE projectid=?", (request["projectid"],))
            db.execute("DELETE FROM outgoing "
                       "WHERE projectid=?", (request["projectid"],))
        LOG.info("ProjID:{} Diarize audio request failed".format(request["projectid"]))
        return reqstatus #DEMIT TODO: translate error from speech server!

    def outgoing(self, uri):
        LOG.debug("Outgoing audio on temp URL:{}".format(uri))
        db = sqlite.connect(self._config['projectdb'])
        db.row_factory = sqlite.Row
        with db:
            row = db.execute("SELECT projectid, audiofile "
                             "FROM outgoing WHERE url=?", (uri,)).fetchone()
            if row is None: #url exists?
                raise MethodNotAllowedError(uri)
            row = dict(row)
            db.execute("DELETE FROM outgoing WHERE url=?", (uri,))
        LOG.info("ProjID:{} Returning audio".format(row["projectid"]))
        return {"mime": "audio/ogg", "filename": row["audiofile"]}


    def incoming(self, uri, data):
        LOG.debug("Incoming data on temp URL:{} data: {}".format(uri, data))
        db = sqlite.connect(self._config['projectdb'])
        db.row_factory = sqlite.Row        
        with db:
            row = db.execute("SELECT projectid, servicetype "
                             "FROM incoming "
                             "WHERE url=?", (uri,)).fetchone()
        if row is None: #url exists?
            raise MethodNotAllowedError(uri)
        row = dict(row)
        #SWITCH TO HANDLER FOR "SERVICETYPE"
        assert row["servicetype"] in self._config["speechservices"], "servicetype '{}' not supported...".format(row["servicetype"])
        handler = getattr(self, "_incoming_{}".format(row["servicetype"]))
        handler(data, row["projectid"]) #will throw exception if not successful
        #CLEANUP DB
        with db:
            db.execute("DELETE FROM incoming WHERE url=?", (uri,))
        LOG.info("ProjID:{} Incoming data processed".format(row["projectid"]))
        return "Request successful!"


    def _incoming_diarize(self, data, projectid):
        LOG.debug("ProjID:{} Processing data: {}".format(projectid, data))
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
                LOG.info("ProjID:{} JobID:{} Diarisation success".format(projectid, jobid))
                #Parse CTM file
                segments = [map(float, line.split()) for line in data["CTM"].splitlines()]
                segments.sort(key=lambda x:x[0]) #by starttime
                LOG.info("ProjID:{} JobID:{} CTM parsing successful...".format(projectid, jobid))
                tasktable = "T{}".format(year)
                db_curs.execute("DELETE FROM {} ".format(tasktable) +\
                                "WHERE projectid=?", (projectid,)) #assume already OK'ed
                for taskid, (starttime, endtime) in enumerate(segments):
                    db_curs.execute("INSERT INTO {} (taskid, projectid, start, end) VALUES(?,?,?,?)".format(tasktable),
                                    (taskid, projectid, starttime, endtime))
                db_curs.execute("UPDATE projects SET jobid=?, errstatus=? WHERE projectid=?", (None, None, projectid))
            else: #"unlock" and recover error status
                LOG.info("ProjID:{} JobID:{} Diarisation failure".format(projectid, jobid))
                db_curs.execute("UPDATE projects SET jobid=?, errstatus=? WHERE projectid=?", (None, data["errstatus"], projectid))
            db_conn.commit()
        LOG.info("ProjID:{} Diarization result received successfully".format(projectid))


class ProjectDB(sqlite.Connection):
    """DEMIT: Review lock/err checking structure/parameters

       DEMIT: Have to be careful with the implementation in here: We
       actually don't want any non-SQLite exceptions to happen here
       since that may invalidate assumptions about rollback in higher
       level code. The exception is `check_project`
    """

    def lock(self):
        self.execute("BEGIN IMMEDIATE")

    def insert_project(self, fields):
        fieldnames = list(fields)
        fieldsq = ", ".join(fieldnames)
        valuesq = ",".join(["?"] * len(fieldnames))
        self.execute("INSERT INTO projects ({}) VALUES({})".format(fieldsq, valuesq),
                     tuple(fields[fieldname] for fieldname in fieldnames))

    def create_tasktable(self, year):
        table_name = "T{}".format(year)
        query = ( "CREATE TABLE IF NOT EXISTS {} ".format(table_name) +\
                  "( taskid INTEGER, projectid VARCHAR(36), editor VARCHAR(20), collator VARCHAR(20), "
                  "start REAL, end REAL, language VARCHAR(20), "
                  "textfile VARCHAR(64), creation REAL, modified REAL, commitid VARCHAR(40), "
                  "ownership INTEGER, jobid VARCHAR(36), errstatus VARCHAR(128) )" )
        self.execute(query)


    def get_projects(self, fields=None, where=None):
        if not fields is None:
            selectq = ", ".join(fields)
        else:
            selectq = "*"
        if not where is None:
            wherefields = list(where)
            whereq = ", ".join(["{}=?".format(f) for f in wherefields])
            rows = self.execute("SELECT {} ".format(selectq) +\
                                "FROM projects "
                                "WHERE {}".format(whereq), tuple(where[k] for k in wherefields)).fetchall()
        else:
            rows = self.execute("SELECT {} FROM projects".format(selectq)).fetchall()            
        if rows is None:
            return []
        return map(dict, rows)

    def check_project(self, projectid, check_err=False):
        """This should be run before attempting to make changes to a project,
           it does the following:
             -- Locks the DB
             -- Checks whether the project exists
             -- Check whether the project is "locked"
             -- Optionally check whether the project has `errstatus` set
        """
        self.lock()
        row = self.execute("SELECT jobid, errstatus FROM projects WHERE projectid=?", (projectid,)).fetchone()
        if row is None: #project exists?
            message = "ProjID:{} Project not found".format(projectid)
            LOG.debug(message)
            raise NotFoundError(message)
        row = dict(row)
        if row["jobid"]: #project clean?
            message = "ProjID:{} This project is currently locked with jobid: {}".format(projectid, jobid)
            LOG.debug(message)
            raise ConflictError(message)
        if check_err and row["errstatus"]:
            message = "ProjID:{} A previous job resulted in error: '{}'".format(projectid, errstatus)
            LOG.debug(message)
            raise ConflictError(message)

    def get_project(self, projectid, fields):
        """Should typically run `check_project` before doing this.
        """
        fields = set(fields)
        query = "SELECT {} FROM projects WHERE projectid=?".format(", ".join(fields))
        row = self.execute(query, (projectid,)).fetchone()
        try:
            row = dict(row)
        except TypeError:
            row = {}
        return row

    def delete_project(self, projectid):
        self.delete_tasks(projectid)
        self.execute("DELETE FROM projects WHERE projectid=?", (projectid,))
        

    def project_assigned(self, projectid):
        return self.get_project(projectid, fields=["assigned"])["assigned"].upper() == "Y"

    def get_tasks(self, projectid, fields=None):
        year = self.get_project(projectid, fields=["year"])["year"]
        tasktable = "T{}".format(year)
        if not fields is None:
            selectq = ", ".join(fields)
        else:
            selectq = "*"
        tasks = self.execute("SELECT {} FROM {} ".format(selectq, tasktable) +\
                           "WHERE projectid=?", (projectid,)).fetchall()
        if tasks is None:
            message = "ProjID:{} No tasks found".format(projectid)
            LOG.debug(message)
            raise NotFoundError(message)
        return map(dict, tasks)

    def delete_tasks(self, projectid):
        year = self.get_project(projectid, fields=["year"])["year"]
        tasktable = "T{}".format(year)
        self.execute("DELETE FROM {} ".format(tasktable) +\
                     "WHERE projectid=?", (projectid,))

    def insert_tasks(self, projectid, tasks, fields):
        year = self.get_project(projectid, fields=["year"])["year"]
        tasktable = "T{}".format(year)
        #Build query
        fieldnames = list(fields)
        fieldsq = ", ".join(fieldnames)
        valuesq = ",".join(["?"] * len(fieldnames))
        for task in tasks:
            self.execute("INSERT INTO {} {} VALUES({})".format(tasktable, fieldsq, valuesq),
                         tuple(task[fieldname] for fieldname in fieldnames))

    def lock_project(self, projectid, jobid=None):
        jobid = str(jobid)
        self.execute("UPDATE projects "
                     "SET jobid=? "
                     "WHERE projectid=?", (jobid,
                                           projectid))
        
    def unlock_project(self, projectid, errstatus=None):
        self.execute("UPDATE projects "
                     "SET jobid=?, errstatus=? "
                     "WHERE projectid=?", (None,
                                           errstatus,
                                           projectid))


    def update_tasks(self, projectid, tasks, fields, check_alldef=True):
        year = self.get_project(projectid, fields=["year"])["year"]
        tasktable = "T{}".format(year)
        #Make sure all required fields are set (DEMIT: Maybe this
        #should be done at higher level -- we don't want any
        #non-SQLite exceptions to be raised here)
        if check_alldef:
            undefined = (None, "")
            for task in tasks:
                if not all(v not in undefined for k, v in task.iteritems() if k in fields):
                    log_raise("ProjID:{} Not all necessary task fields are defined for assign_tasks()".format(projectid),
                              Exception)
        #Commit to DB (currently fail silently if nonexistent)
        for task in tasks:
            self.execute("UPDATE {} ".format(tasktable) +\
                         "SET {} ".format(", ".join(field + "=?" for field in fields)) +\
                         "WHERE projectid=? AND taskid=?",
                         tuple([task[k] for k in fields] + [projectid, task["taskid"]]))

    def update_project(self, projectid, fields):
        fieldkeys = tuple(fields)
        setq = ", ".join(k + "=?" for k in fieldkeys)
        self.execute("UPDATE projects "
                     "SET {} ".format(setq) +\
                     "WHERE projectid=?", tuple([fields[k] for k in fieldkeys] + [projectid]))

## Helper funcs
def approx_eq(a, b, epsilon=0.01):
    return abs(a - b) < epsilon

def log_raise(message, exception=Exception, level=DEBUG):
    LOG.log(level, message)
    raise exception(message)

if __name__ == "__main__":
    pass

