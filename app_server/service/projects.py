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
from functools import wraps
from types import FunctionType
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
SOXI_BIN = "/usr/bin/soxi"; assert os.stat(SOXI_BIN)

TASKID_DIR_ZFILL = 3

def authlog(okaymsg):
    """This performs authentication (inserting `username` into function
       namespace) and logs the ENTRY, FAILURE or OK return of the
       decorated method...
       http://stackoverflow.com/questions/26746441/how-can-a-decorator-pass-variables-into-a-function-without-changing-its-signatur
    """
    def decorator(f):
        logfuncname = {"funcname": f.__name__}
        @wraps(f)
        def wrapper(*args, **kw):
            self, request = args[:2]
            if not "file" in request:
                LOG.debug("ENTER: request={}".format(request), extra=logfuncname)
            else:
                LOG.debug("ENTER: without 'file' --> request={}".format(
                    dict([(k, request[k]) for k in request if k != "file"])), extra=logfuncname)
            try:
                #AUTH + INSERT USERNAME INTO FUNC SCOPE
                username = self.authdb.authenticate(request["token"])
                fn_globals = {}
                fn_globals.update(globals())
                fn_globals.update({"username": username})
                call_fn = FunctionType(getattr(f, "func_code"), fn_globals) #Only Py2
                #LOG-CALL-LOG-RETURN
                if "projectid" in request:
                    LOG.info("ENTER: (username={} projectid={})".format(username, request["projectid"]), extra=logfuncname)
                else:
                    LOG.info("ENTER: (username={})".format(username), extra=logfuncname)
                result = call_fn(*args, **kw)
                if "projectid" in request:
                    LOG.info("OK: (username={} projectid={}) {}".format(username, request["projectid"], okaymsg), extra=logfuncname)
                else:
                    LOG.info("OK: (username={}) {}".format(username, okaymsg), extra=logfuncname)
                return result
            except Exception as e:
                if "projectid" in request:
                    LOG.info("FAIL: (username={} projectid={}) {}".format(username, request["projectid"], e), extra=logfuncname)
                else:
                    LOG.info("FAIL: (username={}) {}".format(username, e), extra=logfuncname)
                raise
        return wrapper
    return decorator


class Admin(admin.Admin):
    pass


class Projects(auth.UserAuth):
    def __init__(self, config_file, speechserv):
        #Provides: self._config and self.authdb
        auth.UserAuth.__init__(self, config_file)
        self._categories = self._config["categories"]
        self._speech = speechserv
        #DB connection setup:
        self.db = sqlite.connect(self._config['projectdb'], factory=ProjectDB)
        self.db.row_factory = sqlite.Row

    @authlog("Returning list of categories")
    def list_categories(self, request):
        """List Admin-created project categories
        """
        return {'categories' : self._categories}

    @authlog("Created new project")
    def create_project(self, request):
        """Create a new project for a user
        """
        # Fetch project categories and check user supplied category
        if request["category"] not in self._categories:
            raise BadRequestError("Project category '{}' NOT FOUND".format(request["category"]))
        # Create project
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
        LOG.info("Inserted new project: projectid={}".format(projectid))
        return {'projectid' : projectid}

    @authlog("Returning list of projects")
    def list_projects(self, request):
        """List current projects owned by user
        """
        with self.db as db:
            projects = db.get_projects(where={"username": username})
        return {'projects' : projects}

    @authlog("Deleted project")
    def delete_project(self, request):
        """Delete project and remove tasks, including all associated files.
        """
        #Clear project from DB
        with self.db as db:
            row = db.get_project(request["projectid"], ["audiofile"])
            db.delete_project(request["projectid"])
        #Remove any files associated with project
        if row:
            if row["audiofile"]:
                projectpath = os.path.dirname(row["audiofile"])
                shutil.rmtree(projectpath, ignore_errors=True)
        return "Project deleted!"

    @authlog("Returning loaded project")
    def load_project(self, request):
        """Load project tasks
        """
        with self.db as db:
            #This will lock the DB:
            db.check_project(request["projectid"], check_err=False) #DEMIT: check_err?
            project = db.get_project(request["projectid"],
                                     fields=["projectname", "category", "year"])
            tasks = db.get_tasks(request["projectid"],
                                 fields=["editor", "collator", "start", "end", "language"]) #DEMIT: taskid, ownership?
        return {'project' : project, 'tasks' : tasks}

    @authlog("Saved project")
    def save_project(self, request):
        """Save the project state (assignments and task partitioning) in the
           interim. This can only be run BEFORE `assign_tasks` and
           usually after partitioning (e.g. via speech diarize or the
           UI or both). To update project meta-info, assignees or
           toggle ownership after assignment use `update_project` or
           `set_ownership`
        """
        #Check whether all necessary fields are in input for each task
        infields = ("editor", "collator", "start", "end", "language")
        fields = ("taskid", "projectid") + infields
        tasks = list(request["tasks"])
        for task in tasks:
            if not all(k in task for k in infields):
                raise BadRequestError("Tasks do not contain all the required fields")

        #Extract relevant project fields from input
        infields = ("projectname", "category")
        projectdata = dict([(k, v) for k, v in request["project"].iteritems() if k in infields])

        #Check received tasks are: contiguous, non-overlapping,
        #completely spanning audiofile (implicitly: audio uploaded)
        tasks.sort(key=lambda x:x["start"])
        prevtask_end = 0.0
        for taskid, task in enumerate(tasks):
            if not approx_eq(prevtask_end, task["start"]):
                raise BadRequestError("Tasks times not contiguous and non-overlapping")
            prevtask_end = task["end"]
            task["taskid"] = taskid
            task["projectid"] = request["projectid"]

        with self.db as db:
            #This will lock the DB:
            db.check_project(request["projectid"], check_err=False) #DEMIT: check_err? 
            row = db.get_project(request["projectid"], fields=["audiodur"])
            #Check audio has been uploaded
            if row["audiodur"] is None:
                raise ConflictError("No audio has been uploaded")
            #Check tasks span audio
            if not approx_eq(row["audiodur"], prevtask_end):
                raise BadRequestError("Tasks do not span entire audio file")
            #Check whether tasks already assigned
            if db.project_assigned(request["projectid"]):
                raise ConflictError("Cannot be re-saved because tasks are already assigned (use: update_project())")
            #Delete current list of tasks and re-insert from input
            db.delete_tasks(request["projectid"])
            db.insert_tasks(request["projectid"], tasks, fields)
            db.update_project(request["projectid"], projectdata)
        return 'Project saved!'

    @authlog("Assigned tasks")
    def assign_tasks(self, request):
        """Assign tasks to editors:
            - Create documents associated with speech segments
            - Ensure that tasks table is fully completed (i.a. editors assigned)
            - Sets permissions appropriately
            - Sets project state to `assigned` disallowing revision of task segments
        """
        with self.db as db:
            #This will lock the DB:
            db.check_project(request["projectid"], check_err=False) #DEMIT: check_err?
            if db.project_assigned(request["projectid"]):
                raise ConflictError("Tasks have already been assigned")
            #Fetch tasks and project info
            row = db.get_project(request["projectid"], fields=["audiofile"])
            tasks = db.get_tasks(request["projectid"])
            if not tasks:
                raise ConflictError("No tasks found to assign")
            #Make sure all required fields are set
            undefined = (None, "")
            infields = ("taskid", "projectid", "editor", "collator", "start", "end", "language")
            for task in tasks:
                if not all(v not in undefined for k, v in task.iteritems() if k in infields):
                    raise BadRequestError("Not all necessary task fields are defined (use save_project() first)")
            #Lock the project
            db.lock_project(request["projectid"], jobid="assign_tasks")
        try:
            #Create files and update fields
            textname = "text"
            updatefields = ("textfile", "creation", "modified", "commitid", "ownership")
            audiodir = os.path.dirname(row["audiofile"])
            textdirs = []
            for task in tasks:
                textdir = os.path.join(audiodir, str(task["taskid"]).zfill(TASKID_DIR_ZFILL))
                os.makedirs(textdir) #should succeed...
                textdirs.append(textdir)
                repo.init(textdir)
                task["textfile"] = os.path.join(textdir, textname)
                open(task["textfile"], "wb").close()
                task["commitid"], task["creation"] = repo.commit(textdir, textname, "task assigned")
                task["modified"] = task["creation"]
                task["ownership"] = 0 #Actually need an ownership ENUM: {0: "editor", 1: "collator"}
            #Update fields and unlock project
            with self.db as db:
                db.update_tasks(request["projectid"], tasks, fields=updatefields)
                db.update_project(request["projectid"], data={"assigned": "Y"})
                db.unlock_project(request["projectid"])
            return 'Project tasks assigned!'
        except:
            LOG.debug("(projectid={}) FAIL: Cleaning up filesystem and unlocking".format(request["projectid"]))
            #Cleanup filesystem
            for textdir in textdirs:
                shutil.rmtree(textdir, ignore_errors=True)
            #Unlock the project and set errstatus
            with self.db as db:
                db.unlock_project(request["projectid"], errstatus="assign_tasks")
            raise


    @authlog("Project updated")
    def update_project(self, request):
        """Update assignees and/or other project meta-info. Can only be run
           after task assignment.
        """
        taskupdatefields = {"editor", "collator", "language", "ownership"}
        projectupdatefields = {"projectname", "category"}
        projectdata = dict((k, request["project"][k]) for k in projectupdatefields if k in request["project"])
        #Check taskid in all tasks and taskids unique
        try:
            in_taskids = [task["taskid"] for task in request["tasks"]]
        except KeyError:
            raise BadRequestError("Task ID not found in input")
        if len(in_taskids) != len(set(in_taskids)):
            raise BadRequestError("Task IDs not unique in input")
        in_taskids = set(in_taskids)

        with self.db as db:
            #This will lock the DB:
            db.check_project(request["projectid"], check_err=False) #DEMIT: check_err?
            #Check whether tasks assigned
            if not db.project_assigned(request["projectid"]):
                raise ConflictError("Save and assign tasks before calling update...")
            #Check whether all taskids valid
            curr_taskids = set(task["taskid"] for task in db.get_tasks(request["projectid"], fields=["taskid"]))
            if not curr_taskids.issuperset(in_taskids):
                raise BadRequestError("Invalid task ID in input")
            #Update fields
            for task in request["tasks"]:
                taskfields = taskupdatefields.intersection(task)
                db.update_tasks(request["projectid"], [task], fields=taskfields)
            if projectdata:
                db.update_project(request["projectid"], data=projectdata)
        return "Project updated!"

    @authlog("Project unlocked")
    def unlock_project(self, request):
        """Unlock project and send cancel request for speech job if relevant
        """
        with self.db as db:
            db.lock()
            #Project exists and locked?
            row = db.get_project(request["projectid"], ["jobid"])
            if row is None:
                raise ConflictError("Project does not exist")
            jobid = row["jobid"]
            if not jobid:
                raise ConflictError("Project is not locked")
            #Why locked?
            if jobid == "assign_tasks":
                LOG.info("(projectid={}) Previous failure in assign_tasks(): Cleaning up filesystem".format(request["projectid"]))
                audiofile = db.get_project(request["projectid"], fields=["audiofile"])["audiofile"]
                tasks = db.get_tasks(request["projectid"], fields=["taskid"])
                for task in tasks:
                    textdir = os.path.join(os.path.dirname(audiofile), str(task["taskid"]).zfill(TASKID_DIR_ZFILL))
                    shutil.rmtree(textdir, ignore_errors=True)
                db.unlock_project(request["projectid"], errstatus="assign_tasks")
                return "Project unlocked: Task assignment failed"
            elif jobid == "upload_audio": #DEMIT: Revisit audiofile name generation?
                LOG.info("(projectid={}) Previous failure in upload_audio(): Nothing to be done (filesystem may contain spurious audio file)".format(request["projectid"]))
                db.unlock_project(request["projectid"], errstatus="upload_audio")
                return "Project unlocked: Audio upload failed"
            elif jobid == "diarize_audio":
                LOG.info("(projectid={}) Previous failure in diarize_audio(): Cleaning up DB".format(request["projectid"]))
                db.delete_incoming(request["projectid"])
                db.delete_outgoing(request["projectid"])
                db.unlock_project(request["projectid"], errstatus="diarize_audio")
                return "Project unlocked: Diarize request failed"
            else: #Speech job pending
                LOG.info("(projectid={} jobid={}) Speech job pending. Cleaning up DB and cancelling...".format(request["projectid"], jobid))
                db.delete_incoming(request["projectid"])
                db.delete_outgoing(request["projectid"])
                db.unlock_project(request["projectid"], errstatus="diarize_audio")
        #Send cancel job request to SpeechServ:
        # TEMPORARILY COMMENTED OUT FOR TESTING WITHOUT SPEECHSERVER:
        # cancelreq = {}
        # reqstatus = requests.post(os.path.join(SPEECHSERVER, self._config["speechservices"]["diarize"]), data=json.dumps(jobreq))
        # reqstatus = reqstatus.json()
        reqstatus = ["OK"] or ["NOT OK"] #DEMIT: dummy call for testing!
        return "Project unlocked: Diarize job cancelled"

    @authlog("Audio uploaded")
    def upload_audio(self, request):
        """Audio uploaded to project space
           TODO: convert audio to OGG Vorbis, mp3splt for editor
        """
        with self.db as db:
            #This will lock the DB:
            db.check_project(request["projectid"], check_err=False) #DEMIT: check_err?
            #Check whether tasks already assigned
            if db.project_assigned(request["projectid"]):
                raise ConflictError("Cannot re-upload audio because tasks are already assigned")
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
            return 'Audio Saved!'
        except:
            LOG.debug("(projectid={}) FAIL: Unlocking".format(request["projectid"]))
            #Unlock the project and set errstatus
            with self.db as db:
                db.unlock_project(request["projectid"], errstatus="upload_audio")
            raise

    @authlog("Returning audio for project")
    def get_audio(self, request):
        """Make audio available for project user
        """
        with self.db as db:
            row = db.get_project(request["projectid"], fields=["audiofile"])
            if not row:
                raise NotFoundError("Project not found")
            if not row["audiofile"]:
                raise ConflictError("No audio has been uploaded")
        return {"mime": "audio/ogg", "filename" : row["audiofile"]}

    @authlog("Diarize audio request sent")
    def diarize_audio(self, request):
        with self.db as db:
            #This will lock the DB:            
            db.check_project(request["projectid"], check_err=False) #DEMIT: check_err?
            #Check whether tasks already assigned
            if db.project_assigned(request["projectid"]):
                raise ConflictError("Tasks have already been assigned")
            #Get audiofile path and exists?
            row = db.get_project(request["projectid"], ["audiofile"])
            if not row["audiofile"]:
                raise ConflictError("No audio has been uploaded")
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
            LOG.debug("Diarize: reqstatus={}".format(reqstatus))
            #Check reqstatus from SpeechServ OK?
            if not "jobid" in reqstatus:
                raise Exception("Diarize request failed, SpeechServ says: {}".format(reqstatus["message"]))
            #Update project with jobid from SpeechServ
            LOG.info("(username={} projectid={} jobid={}) Diarize request successful".format(username, request["projectid"], reqstatus["jobid"]))
            with self.db as db:
                db.update_project(request["projectid"], {"jobid": reqstatus["jobid"]})
            return "Diarize request successful!"
        except:
            LOG.debug("(projectid={}) FAIL: Cleaning up DB and unlocking".format(request["projectid"]))
            with self.db as db:
                db.delete_incoming(request["projectid"])
                db.delete_outgoing(request["projectid"])
                db.unlock_project(request["projectid"], errstatus="diarize_audio")
            raise

    def outgoing(self, uri):
        try:
            LOG.info("ENTER: url={}".format(uri))
            with self.db as db:
                row = db.get_outgoing(uri)
                if not row:
                    raise MethodNotAllowedError(uri)
            LOG.info("OK: (url={} projectid={}) Returning audio".format(uri, row["projectid"]))
            return {"mime": "audio/ogg", "filename": row["audiofile"]}
        except Exception as e:
            LOG.info("FAIL: {}".format(e))

    def incoming(self, uri, data):
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
            handler = getattr(self, "_incoming_{}".format(row["servicetype"]))
            handler(data, row["projectid"]) #will throw exception if not successful
            LOG.info("OK: (url={} projectid={}) Incoming data processed".format(uri, row["projectid"]))
            return "Request successful!"
        except Exception as e:
            LOG.info("FAIL: {}".format(e))

    def _incoming_diarize(self, data, projectid):
        LOG.debug("ENTER: projectid={} data={}".format(projectid, data))
        try:
            #Check whether SpeechServ job was successful
            if not "CTM" in data:
                raise Exception("(projectid={}) Diarization process not successful (no CTM)".format(projectid))
            #Proceed to update tasks
            with self.db as db:
                row = db.get_project(projectid, ["jobid"])
                #Project still exists and expecting job?
                if not row:
                    raise ConflictError("(projectid={}) Project no longer exists".format(projectid))
                elif row["jobid"] is None:
                    raise ConflictError("(projectid={}) Project no longer expecting job (project unlocked in the meantime)".format(projectid))
                #Parse CTM file and create tasks
                segments = diarize_parse_ctm(data["CTM"])
                LOG.debug("(projectid={} jobid={}) CTM parsing successful...".format(projectid, row["jobid"]))
                tasks = []
                for taskid, (starttime, endtime) in enumerate(segments):
                    tasks.append({"taskid": taskid, "projectid": projectid, "start": starttime, "end": endtime})
                #Delete current list of tasks and re-insert from diarize result
                db.delete_tasks(projectid)
                db.insert_tasks(projectid, tasks, fields=["taskid", "projectid", "start", "end"])
                db.unlock_project(projectid)
            LOG.info("OK: (projectid={}) Diarization result received successfully".format(projectid))
        except Exception as e: #"unlock" and recover error status
            with self.db as db:
                db.unlock_project(projectid, errstatus=data["errstatus"])
            LOG.info("FAIL: {}".format(e))


class ProjectDB(sqlite.Connection):
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
            raise NotFoundError("Project not found")
        row = dict(row)
        if row["jobid"]: #project clean?
            raise ConflictError("This project is currently locked with jobid: {}".format(row["jobid"]))
        if check_err and row["errstatus"]:
            raise PrevJobError("{}".format(row["errstatus"]))

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
            message = "projectid={} No tasks found".format(projectid)
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
        fields = tuple(fields)
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

    def clearerror_project(self, projectid):
        self.execute("UPDATE projects "
                     "SET errstatus=? "
                     "WHERE projectid=?", (None,
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

    def get_incoming(self, url):
        row = self.execute("SELECT projectid, servicetype "
                           "FROM incoming WHERE url=?", (url,)).fetchone()
        if row is not None:
            self.execute("DELETE FROM incoming WHERE url=?", (url,))
            row = dict(row)
        else:
            row = {}
        return row
        
########## Helper funcs/classes
def approx_eq(a, b, epsilon=0.01):
    return abs(a - b) < epsilon

def diarize_parse_ctm(ctm):
    segments = [map(float, line.split()) for line in ctm.splitlines()]
    segments.sort(key=lambda x:x[0]) #by starttime
    return segments

class PrevJobError(Exception):
    pass

if __name__ == "__main__":
    pass

