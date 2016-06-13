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
        """
        auth.token_auth(request["token"], self._config["authdb"])

        #Check whether all necessary fields are in input for each task
        infields = ("editor", "collator", "start", "end", "language")
        fields = ("taskid", "projectid") + infields
        tasks = list(request["tasks"])
        for task in tasks:
            if not all(k in task for k in infields):
                message = "ProjID:{} Tasks do not contain all the required fields".format(request["projectid"])
                LOG.debug(message); raise BadRequestError(message)

        #Extract relevant project fields from input
        infields = ("projectname", "category")
        projectdata = dict([(k, v) for k, v in request["project"].iteritems() if k in infields])

        #Check received tasks are: contiguous, non-overlapping,
        #completely spanning audiofile (implicitly: audio uploaded)
        tasks.sort(key=lambda x:x["start"])
        prevtask_end = 0.0
        for taskid, task in enumerate(tasks):
            if not approx_eq(prevtask_end, task["start"]):
                message = "ProjID:{} Tasks times not contiguous and non-overlapping".format(request["projectid"])
                LOG.debug(message); raise BadRequestError(message)
            prevtask_end = task["end"]
            task["taskid"] = taskid
            task["projectid"] = request["projectid"]

        with self.db as db:
            #This will lock the DB:
            db.check_project(request["projectid"], check_err=True) #later "try" to recover from certain issues
            row = db.get_project(request["projectid"], fields=["audiodur"])
            #Check audio has been uploaded
            if row["audiodur"] is None:
                message = "ProjID:{} No audio has been uploaded".format(request["projectid"])
                LOG.debug(message); raise ConflictError(message)
            #Check tasks span audio
            if not approx_eq(row["audiodur"], prevtask_end):
                message = "ProjID:{} Tasks do not span entire audio file".format(request["projectid"])
                LOG.debug(message); raise BadRequestError(message)
            #Check whether tasks already assigned
            if db.project_assigned(request["projectid"]):
                message = "ProjID:{} Cannot be re-saved because tasks are already assigned (use: update_project())".format(request["projectid"])
                LOG.debug(message); raise ConflictError(message)
            #Delete current list of tasks and re-insert from input
            db.delete_tasks(request["projectid"])
            db.insert_tasks(request["projectid"], tasks, fields)
            db.update_project(request["projectid"], projectdata)
        ##########
        LOG.info("ProjID:{} Saved project".format(request["projectid"]))
        return 'Project saved!'

    def assign_tasks(self, request):
        """Assign tasks to editors:
            - Create documents associated with speech segments
            - Ensure that tasks table is fully completed (i.a. editors assigned)
            - Sets permissions appropriately
            - Sets project state to `assigned` disallowing revision of task segments
        """
        auth.token_auth(request["token"], self._config["authdb"])

        with self.db as db:
            #This will lock the DB:
            db.check_project(request["projectid"], check_err=True) #later "try" to recover from certain issues
            if db.project_assigned(request["projectid"]):
                message = "ProjID:{} Tasks have already been assigned".format(request["projectid"])
                LOG.debug(message); raise ConflictError(message)
            #Fetch tasks and project info
            row = db.get_project(request["projectid"], fields=["audiofile"])
            tasks = db.get_tasks(request["projectid"])
            if not tasks:
                message = "ProjID:{} No tasks found to assign".format(request["projectid"])
                LOG.debug(message); raise ConflictError(message)
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
            #Make sure all required fields are set
            undefined = (None, "")
            for task in tasks:
                if not all(v not in undefined for k, v in task.iteritems() if k in updatefields):
                    message = "ProjID:{} Not all necessary task fields are defined for".format(request["projectid"])
                    LOG.debug(message); raise BadRequestError(message)
            #Update fields and unlock project
            with self.db as db:
                db.update_tasks(request["projectid"], tasks, fields=updatefields)
                db.update_project(request["projectid"], data={"assigned": "Y"})
                db.unlock_project(request["projectid"])
            LOG.info("ProjID:{} Assigned tasks".format(request["projectid"]))
            return 'Project tasks assigned!'
        except:
            #Unlock the project and set errstatus
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
        """
        username = auth.token_auth(request["token"], self._config["authdb"])

        with self.db as db:
            #This will lock the DB:
            db.check_project(request["projectid"], check_err=True) #later "try" to recover from certain issues
            #Check whether tasks already assigned
            if db.project_assigned(request["projectid"]):
                message = "ProjID:{} Cannot re-upload audio because tasks are already assigned".format(request["projectid"])
                LOG.debug(message); raise ConflictError(message)
            #Get current project details
            row = db.get_project(request["projectid"], ["audiofile", "creation"])
            #Lock project
            db.lock_project(request["projectid"], jobid="upload_audio")
        try:
            #Create project path if needed
            pcreation = datetime.datetime.fromtimestamp(row["creation"])
            ppath = os.path.join(self._config["storage"],
                                 username,
                                 str(pcreation.year),
                                 str(pcreation.month).zfill(2),
                                 str(pcreation.day).zfill(2),
                                 request["projectid"])
            if not os.path.exists(ppath):
                os.makedirs(ppath)

            #Write audio file (DEMIT: check audiofile name creation)
            audiofile = os.path.join(ppath, base64.urlsafe_b64encode(str(uuid.uuid4())))
            with open(audiofile, 'wb') as f:
                f.write(request['file'])
            audiodur = float(subprocess.check_output([SOXI_BIN, "-D", audiofile]))

            #Update fields and unlock project            
            with self.db as db:
                db.update_project(request["projectid"], {"audiofile": audiofile, "audiodur": audiodur})
                db.delete_tasks(request["projectid"])
                db.unlock_project(request["projectid"])
            #Remove previous audiofile if it exists
            if row["audiofile"]:
                os.remove(row["audiofile"])
            LOG.info("ProjID:{} Audio uploaded".format(request["projectid"]))
            return 'Audio Saved!'
        except:
            #Unlock the project and set errstatus
            with self.db as db:
                db.unlock_project(request["projectid"], errstatus="upload_audio")
            raise


    def get_audio(self, request):
        """Make audio available for project user
        """
        auth.token_auth(request["token"], self._config["authdb"])

        with self.db as db:
            row = db.get_project(request["projectid"], fields=["audiofile"])
            if not row:
                message = "ProjID:{} Project not found".format(request["projectid"])
                LOG.debug(message); raise NotFoundError(message)                
            if not row["audiofile"]:
                message = "ProjID:{} No audio has been uploaded".format(request["projectid"])
                LOG.debug(message); raise ConflictError(message)
        LOG.info("ProjID:{} Returning audio for project".format(request["projectid"]))
        return {"mime": "audio/ogg", "filename" : row["audiofile"]}

    def diarize_audio(self, request):
        auth.token_auth(request["token"], self._config["authdb"])
        
        with self.db as db:
            #This will lock the DB:            
            db.check_project(request["projectid"], check_err=True) #later "try" to recover from certain issues
            #Check whether tasks already assigned
            if db.project_assigned(request["projectid"]):
                message = "ProjID:{} Tasks have already been assigned".format(request["projectid"])
                LOG.debug(message); raise ConflictError(message)
            #Get audiofile path and exists?
            row = db.get_project(request["projectid"], ["audiofile"])
            if not row["audiofile"]:
                message = "ProjID:{} No audio has been uploaded".format(request["projectid"])
                LOG.debug(message); raise ConflictError(message)            
            #Set up I/O access and lock the project
            db.insert_incoming(request["projectid"], url=auth.gen_token(), servicetype="diarize")
            db.insert_outgoing(request["projectid"], url=auth.gen_token(), audiofile=row["audiofile"])
            db.lock_project(request["projectid"], jobid="diarize_audio")
            
        #Make job request:
        try:

            # TEMPORARILY COMMENTED OUT FOR TESTING WITHOUT SPEECHSERVER:
            # jobreq = {"token" : request["token"], "getaudio": os.path.join(APPSERVER, outurl),
            #           "putresult": os.path.join(APPSERVER, inurl), "service" : "diarize", "subsystem" : "default"}
            # LOG.debug(os.path.join(SPEECHSERVER, self._config["speechservices"]["diarize"]))
            # reqstatus = requests.post(os.path.join(SPEECHSERVER, self._config["speechservices"]["diarize"]), data=json.dumps(jobreq))
            # reqstatus = reqstatus.json()
            reqstatus = {"jobid": auth.gen_token()} #DEMIT: dummy call for testing!
            #TODO: handle return status
            LOG.debug("{}".format(reqstatus))
            #Check reqstatus from SpeechServ OK?
            if not "jobid" in reqstatus:
                message = "ProjID:{} Diarize fail, SpeechServ says: {}".format(request["projectid"], reqstatus["message"])
                LOG.debug(message); raise Exception(message)
            #Update project with jobid from SpeechServ
            with self.db as db:
                db.update_project(request["projectid"], {"jobid": reqstatus["jobid"]})
            LOG.info("ProjID:{} JobID:{} Diarize audio request sent.".format(request["projectid"], reqstatus["jobid"]))
            return "Request successful!"
        except:
            with self.db as db:
                db.delete_incoming(request["projectid"])
                db.delete_outgoing(request["projectid"])
                db.unlock_project(request["projectid"], errstatus="diarize_audio")
            raise

    def outgoing(self, uri):
        LOG.debug("Outgoing audio on temp URL:{}".format(uri))
        with self.db as db:
            row = db.get_outgoing(uri)
            if not row:
                raise MethodNotAllowedError(uri)
        LOG.info("ProjID:{} Returning audio".format(row["projectid"]))
        return {"mime": "audio/ogg", "filename": row["audiofile"]}


    #DEMIT
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
    """

    def lock(self):
        self.execute("BEGIN IMMEDIATE")

    def get_projects(self, fields=None, where=None):
        if not fields is None:
            fields = set(fields)
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



##################################################
############################## WRITE OPERATIONS
##################################################
    def insert_project(self, data):
        fields = list(data)
        fieldsq = ", ".join(fields)
        valuesq = ",".join(["?"] * len(fields))
        self.execute("INSERT INTO projects ({}) VALUES({})".format(fieldsq, valuesq),
                     tuple(data[field] for field in fields))

    def insert_tasks(self, projectid, tasks, fields):
        year = self.get_project(projectid, fields=["year"])["year"]
        tasktable = "T{}".format(year)
        #Build query
        fields = tuple(fields)
        fieldsq = ", ".join(fields)
        valuesq = ",".join(["?"] * len(fields))
        for task in tasks:
            self.execute("INSERT INTO {} ({}) VALUES({})".format(tasktable, fieldsq, valuesq),
                         tuple(task[field] for field in fields))

    def update_project(self, projectid, data):
        fields = tuple(data)
        if fields:
            setq = ", ".join(k + "=?" for k in fields)
            self.execute("UPDATE projects "
                         "SET {} ".format(setq) +\
                         "WHERE projectid=?", tuple([data[k] for k in fields] + [projectid]))

    def update_tasks(self, projectid, tasks, fields):
        year = self.get_project(projectid, fields=["year"])["year"]
        tasktable = "T{}".format(year)
        #Commit to DB (currently fail silently if nonexistent)
        for task in tasks:
            self.execute("UPDATE {} ".format(tasktable) +\
                         "SET {} ".format(", ".join(field + "=?" for field in fields)) +\
                         "WHERE projectid=? AND taskid=?",
                         tuple([task[k] for k in fields] + [projectid, task["taskid"]]))

    def delete_project(self, projectid):
        self.delete_tasks(projectid)
        self.execute("DELETE FROM projects WHERE projectid=?", (projectid,))

    def delete_tasks(self, projectid):
        year = self.get_project(projectid, fields=["year"])["year"]
        tasktable = "T{}".format(year)
        self.execute("DELETE FROM {} ".format(tasktable) +\
                     "WHERE projectid=?", (projectid,))


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

    def create_tasktable(self, year):
        table_name = "T{}".format(year)
        query = ( "CREATE TABLE IF NOT EXISTS {} ".format(table_name) +\
                  "( taskid INTEGER, projectid VARCHAR(36), editor VARCHAR(20), collator VARCHAR(20), "
                  "start REAL, end REAL, language VARCHAR(20), "
                  "textfile VARCHAR(64), creation REAL, modified REAL, commitid VARCHAR(40), "
                  "ownership INTEGER, jobid VARCHAR(36), errstatus VARCHAR(128) )" )
        self.execute(query)

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
        

        
        



## Helper funcs
def approx_eq(a, b, epsilon=0.01):
    return abs(a - b) < epsilon


if __name__ == "__main__":
    pass

