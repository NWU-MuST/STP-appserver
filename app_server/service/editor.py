#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function #Py2

import uuid
import json
import time
import datetime
import base64
import os
import requests
import logging
import codecs
import string
import tempfile
import subprocess
from functools import wraps
from types import FunctionType

try:
    from sqlite3 import dbapi2 as sqlite
except ImportError:
    from pysqlite2 import dbapi2 as sqlite #for old Python versions

import auth
import admin
import repo
from httperrs import *

LOG = logging.getLogger("APP.EDITOR")
SPEECHSERVER = os.getenv("SPEECHSERVER"); assert SPEECHSERVER is not None
APPSERVER = os.getenv("APPSERVER"); assert APPSERVER is not None

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
                username = self.authdb.authenticate(request["token"], self._role)
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

#class Admin(admin.Admin):
#    pass

class Editor(auth.UserAuth):

    def __init__(self, config_file, speechserv):
        #Provides: self._config and self.authdb
        auth.UserAuth.__init__(self, config_file)
        self._speech = speechserv
        self._role = self._config["role"]
        #DB connection setup:
        self.db = sqlite.connect(self._config['projectdb'], factory=EditorDB)
        self.db.row_factory = sqlite.Row

    @authlog("Returning list of users")
    def get_users(self, request):
        """Return all users
        """
        users = dict()
        with sqlite.connect(self._config["authdb"]) as db_conn:
            db_curs = db_conn.cursor()
            for entry in db_curs.execute("SELECT * FROM users").fetchall():
                username, pwhash, salt, name, surname, email, role, tmppwhash = entry
                users[username] = {"name": name, "surname": surname, "email": email, "role" : role}
        LOG.info("Returning user list ({})".format(username))
        return users

    @authlog("Return user's tasks")
    def load_tasks(self, request):
        """
            Load tasks assigned to editor and as collator
        """
        with self.db as db:
            editor_tasks = db.get_all_tasks(username)
            LOG.debug("{}".format(editor_tasks))
            collator_tasks = db.get_all_tasks(username, mode="collator")
            LOG.debug("{}".format(collator_tasks))
            if type(collator_tasks) in [str, unicode]:
                collator_tasks = []
            tasks = {"editor" : editor_tasks, "collator" : collator_tasks }

        return tasks

    @authlog("Return a specific task")
    def load_task(self, request):
        """
            Load a specific task
        """
        with self.db as db:
            db.check_project_task(request["projectid"], request["taskid"], check_err=True)
            project = db.get_project(request["projectid"], fields=["year"])
            year = project["year"]
            task_info = db.get_task_field(request["projectid"], request["taskid"], year, fields=["projectid", "taskid", "editor", "modified", "completed", "jobid", "errstatus"])
        return task_info

    def _test_read(self, filename):
        """
            Check if a file can be opened
        """
        try:
            open(filename, 'rb').close()
        except:
            raise BadRequestError("Cannot open file")

    @authlog("Return audio")
    def get_audio(self, request):
        """
            Return the audio for this specific task
        """
        try:
            with self.db as db:
                db.check_project_task(request["projectid"], request["taskid"], check_err=True)

            with self.db as db:
                project = db.get_project(request["projectid"], fields=["year", "audiofile"])
                year = project["year"]
                audiofile = project["audiofile"]

                if audiofile is None or len(audiofile) == 0:
                    raise NotFoundError("No audio file has been uploaded to the project")

                if not os.path.exists(audiofile):
                    raise NotFoundError("Cannot find audio file uploaded to project")

                self._test_read(audiofile)

                items = db.get_task_field(request["projectid"], request["taskid"], year, fields=["start", "end"])
                if not items:
                    raise BadRequestError("Audio segment has not been defined for this task")

                audiorange = [float(items["start"]), float(items["end"])]

            return {"filename" : audiofile, "range" : audiorange, "mime" : "audio/ogg"}
        except Exception as e:
            LOG.error("Get audio failed: {}".format(e))
            raise

    @authlog("Return text")
    def get_text(self, request):
        """
            Return the text data for this specific task
        """
        try:
            with self.db as db:
                db.check_project_task(request["projectid"], request["taskid"], check_err=True)

            with self.db as db:
                year = db.get_project(request["projectid"], fields=["year"])["year"]
                textfile = db.get_task_field(request["projectid"], request["taskid"], year, fields=["textfile"])["textfile"]

                if textfile is None or len(textfile) == 0:
                    raise NotFoundError("This task has no text file")

                if not os.path.exists(textfile):
                    raise NotFoundError("Cannot find text file")

                self._test_read(textfile)

                with codecs.open(textfile, "r", "utf-8") as f: text = f.read()

            return {"text" : text}
        except Exception as e:
            LOG.error("Get text failed: {}".format(e))
            raise

    @authlog("Save text")
    def save_text(self, request):
        """
            Save the provided text to task
        """
        try:
            #TODO: check if you can save to this task -- check lock
            with self.db as db:
                db.check_project_task(request["projectid"], request["taskid"], check_err=True)

            with self.db as db:
                year = db.get_project(request["projectid"], fields=["year"])["year"]
                textfile = db.get_task_field(request["projectid"], request["taskid"], year, fields=["textfile"])["textfile"]
                db.set_jobid(request["projectid"], request["taskid"], year, 'save_text')

                if textfile is None or len(textfile) == 0:
                    raise NotFoundError("This task has no text file")

                if not os.path.exists(textfile):
                    raise NotFoundError("Cannot find text file for this task")

                self._test_read(textfile)

                textdir = os.path.dirname(textfile)
                try: # Handle repo errors
                    #TODO: check errors, not sure how we recover from here
                    repo.check(textdir)
                    with codecs.open(textfile, "w", "utf-8") as f:
                        f.write(request["text"])
                    commitid, modified = repo.commit(textdir, os.path.basename(textfile), "Changes saved")
                    db.save_text(request["projectid"], request["taskid"], year, commitid, modified)
                    db.set_jobid(request["projectid"], request["taskid"], year, None)
                except Exception as e:
                    raise

            return "Text Saved!"
        except Exception as e:# TODO: exception within exception
            LOG.error("Save text failed: {}".format(e))
            with self.db as db:
                year = db.get_project(request["projectid"], fields=["year"])["year"]
                db.set_errstatus(request["projectid"], request["taskid"], year, "{}".format(e))
                db.set_jobid(request["projectid"], request["taskid"], year, None)
            raise

    @authlog("Return subsystems for speech service")
    def speech_subsystems(self, request):
        """ Return service subsystems
        """
        service = request["service"]
        if service not in self._config["speechservices"]["services"]:
            raise NotFoundError("Speech service not supported!")

        options = self._speech.discover()
        LOG.info("{}".format(options))
        if service not in options["subsystems"]:
            raise NotFoundError("Speech server can't find requested service!")

        subs = options["subsystems"][self._config["speechservices"]["services"][service]]
        systems = []
        for item in subs:
            systems.append(item["subsystem"])

        if len(systems) == 0:
            raise NotFoundError("Speech service has no subsystems defined!")

        return {"systems" : systems}

    @authlog("Perform diarize")
    def diarize(self, request):
        """
            Diarize the audio segment
            This will be run on an empty text file only
        """
        try:
            with self.db as db:
                db.check_project_task(request["projectid"], request["taskid"], check_err=True)
                project = db.get_project(request["projectid"], fields=["audiofile", "year"])
                task = db.get_task_field(request["projectid"], request["taskid"], project["year"], fields=["textfile","start","end"])
                db.set_jobid(request["projectid"], request["taskid"], project["year"], "diarize_task")

            if project["audiofile"] is None or len(project["audiofile"]) == 0:
                raise NotFoundError("No audio file has been uploaded to the project")

            if not os.path.exists(project["audiofile"]):
                raise NotFoundError("Cannot find audio file uploaded to project")

            self._test_read(project["audiofile"])

            if os.path.getsize(task["textfile"]) != 0:
                raise BadRequestError("Cannot run diarize since the document is not empty!")

            if task["textfile"] is None or len(task["textfile"]) == 0:
                raise NotFoundError("This task has no text file")

            self._test_read(task["textfile"])

            request["service"] = self._config["speechservices"]["services"]["diarize"]
            if "subsystem" not in request:
                request["subsystem"] = "default"
                #raise NotFoundError("No diarizer subsystem specified!")

            return self._speech_job(request, project, task)
        except Exception as e:
            LOG.error("Diarize audio failed: {}".format(e))
            with self.db as db:
                year = db.get_project(request["projectid"], fields=["year"])["year"]
                db.set_errstatus(request["projectid"], request["taskid"], year, "{}".format(e))
                db.set_jobid(request["projectid"], request["taskid"], year, None)
            raise

    @authlog("Perform recognize")
    def recognize(self, request):
        """
            Recognize spoken audio in portions that do not contain text
        """
        try:
            with self.db as db:
                db.check_project_task(request["projectid"], request["taskid"], check_err=True)
                project = db.get_project(request["projectid"], fields=["audiofile", "year"])
                task = db.get_task_field(request["projectid"], request["taskid"], project["year"], fields=["textfile","start","end"])
                db.set_jobid(request["projectid"], request["taskid"], project["year"], "recognize_task")

            if project["audiofile"] is None or len(project["audiofile"]) == 0:
                raise NotFoundError("No audio file has been uploaded to the project")

            if not os.path.exists(project["audiofile"]):
                raise NotFoundError("Cannot find audio file uploaded to project")

            self._test_read(project["audiofile"])

            if task["textfile"] is None or len(task["textfile"]) == 0:
                raise NotFoundError("This task has no text file")

            self._test_read(task["textfile"])

            request["service"] = self._config["speechservices"]["services"]["recognize"]
            if "subsystem" not in request:
                if "language" in request:
                    if request["language"] in self._config["speechservices"]["recognize"]:
                        request["subsystem"] = self._config["speechservices"]["recognize"][request["language"]]
                    else:
                        raise NotFoundError("Language not supported by speech server!")
                else:
                    raise NotFoundError("No language has been specified!")

            return self._speech_job(request, project, task)
        except Exception as e:
            LOG.error("Recognize audio failed: {}".format(e))
            with self.db as db:
                year = db.get_project(request["projectid"], fields=["year"])["year"]
                db.set_errstatus(request["projectid"], request["taskid"], year, "{}".format(e))
                db.set_jobid(request["projectid"], request["taskid"], year, None)
            raise

    @authlog("Perform alignment")
    def align(self, request):
        """
            Align text to audio for portions that contain text
        """
        try:
            with self.db as db:
                db.check_project_task(request["projectid"], request["taskid"], check_err=True)
                project = db.get_project(request["projectid"], fields=["audiofile", "year"])
                task = db.get_task_field(request["projectid"], request["taskid"], project["year"], fields=["textfile","start","end"])
                db.set_jobid(request["projectid"], request["taskid"], project["year"], "align_task")

            if project["audiofile"] is None or len(project["audiofile"]) == 0:
                raise NotFoundError("No audio file has been uploaded to the project")

            if not os.path.exists(project["audiofile"]):
                raise NotFoundError("Cannot find audio file uploaded to project")

            self._test_read(project["audiofile"])

            if task["textfile"] is None or len(task["textfile"]) == 0:
                raise NotFoundError("This task has no text file")

            if os.path.getsize(task["textfile"]) == 0:
                raise BadRequestError("Cannot run alignment since the document is empty!")

            self._test_read(task["textfile"])

            request["service"] = self._config["speechservices"]["services"]["align"]
            if "subsystem" not in request:
                if "language" in request:
                    if request["language"] in self._config["speechservices"]["align"]:
                        request["subsystem"] = self._config["speechservices"]["align"][request["language"]]
                    else:
                        raise NotFoundError("Language not supported by speech server!")
                else:
                    raise NotFoundError("No language has been specified!")

            return self._speech_job(request, project, task)
        except Exception as e:
            LOG.error("Align audio failed: {}".format(e))
            with self.db as db:
                year = db.get_project(request["projectid"], fields=["year"])["year"]
                db.set_errstatus(request["projectid"], request["taskid"], year, "{}".format(e))
                db.set_jobid(request["projectid"], request["taskid"], year, None)
            raise

    def _speech_job(self, request, project, task):
        """
            Submit a speech job
        """
        with self.db as db:
            db.lock()
            #Setup I/O access
            inurl = auth.gen_token()
            audio_outurl = auth.gen_token()
            text_outurl = auth.gen_token()

            db.set_jobid(request["projectid"], request["taskid"], project["year"], "pending")            
            db.insert_incoming(request["projectid"], request["taskid"], inurl, request["service"])
            db.insert_outgoing(request["projectid"], audio_outurl, project["audiofile"], task["start"], task["end"])
            db.insert_outgoing(request["projectid"], text_outurl, task["textfile"], -2.0, -2.0)

        #Make job request
        #TEMPORARILY COMMENTED OUT FOR TESTING WITHOUT SPEECHSERVER:
        #TODO: fix editor reference
        jobreq = { "token" : self._speech.token(), "getaudio": os.path.join(APPSERVER, "editor", audio_outurl),
                   "gettext": os.path.join(APPSERVER, "editor", text_outurl),
                   "putresult": os.path.join(APPSERVER, "editor", inurl) }
        jobreq["service"] = request["service"]
        jobreq["subsystem"] = request["subsystem"]

        LOG.debug(os.path.join(SPEECHSERVER, self._config["speechservices"]["API"]["add"]))
        LOG.debug("{}".format(jobreq))
        reqstatus = requests.post(os.path.join(SPEECHSERVER, self._config["speechservices"]["API"]["add"]), data=json.dumps(jobreq))
        reqstatus = reqstatus.json()
        #reqstatus = {"jobid": auth.gen_token()} #DEMIT: dummy call for testing!

        #TODO: handle return status
        LOG.debug("{}".format(reqstatus))
        #Handle request status
        if "jobid" in reqstatus: #no error
            with self.db as db:
                db.lock()
                db.set_jobid(request["projectid"], request["taskid"], project["year"], reqstatus["jobid"])
            LOG.info("Speech service request sent for project ID: {}, task ID: {}, job ID: {}".format(request["projectid"], request["taskid"], reqstatus["jobid"]))
            return "Request successful!"

        #Something went wrong: undo project setup
        with self.db as db:
            db.lock()
            if "message" in reqstatus:
                db.set_errstatus(request["projectid"], request["taskid"], project["year"], reqstatus["message"])
            db.delete_incoming_byurl(inurl)
            db.delete_outgoing_byurl(audio_outurl)
            db.delete_outgoing_byurl(text_outurl)
            db.set_jobid(request["projectid"], request["taskid"], project["year"], None)

        LOG.error("Speech service request failed for project ID: {}, task ID: {}".format(request["projectid"], request["taskid"]))
        return reqstatus #DEMIT TODO: translate error from speech server!

    def outgoing(self, uri):
        """ Return task data for retrieval
        """
        try:
            LOG.debug(uri)
            with self.db as db:
                row = db.get_outgoing(uri)
                LOG.debug(row)
                #URL exists?
                if not row:
                    raise MethodNotAllowedError(uri)
                LOG.info("Returning audio for project ID: {}".format(row["projectid"]))
                projectname = db.get_project(row["projectid"], fields=["projectname"])["projectname"]

                # Check if audio range is available
                if row["start"] is not None and row["end"] is not None:
                    if float(row["start"]) == -2.0 and float(row["end"]) == -2.0: # Task text
                        return {"mime": "text/html", "filename": row["audiofile"], "savename" : "{}.html".format(projectname), "delete" : "N"}
                    elif float(row["start"]) == -1.0 and float(row["end"]) == -1.0: # Masterfile MS-WORD document
                        return {"mime": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                "filename": row["audiofile"], "savename" : "{}.docx".format(projectname), "delete" : "Y"}
                    else:# Normal audio
                        return {"mime": "audio/ogg", "filename": row["audiofile"], "range" : (float(row["start"]), float(row["end"]))}
                else: # Full audio return
                    return {"mime": "audio/ogg", "filename": row["audiofile"]}
        except Exception as e:
            LOG.error("Requested outgoing resource failed: {}".format(e))

    def incoming(self, uri, data):
        """ Processing incoming data and save to task
        """
        try:
            LOG.debug("incoming_data: {}".format(data))
            with self.db as db:
                row = db.get_incoming(uri)
                LOG.debug(row)
                #URL exists?
                if not row:
                    raise MethodNotAllowedError(uri)

                #if not row["servicetype"] in self._config["speechservices"]["services"]:
                #    raise Exception("Service type '{}' not defined in AppServer".format(row["servicetype"]))

                self._incoming_base(data, row["projectid"], row["taskid"], row["servicetype"])

                LOG.info("Incoming data processed for project ID: {}, task ID: {}".format(row["projectid"], row["taskid"]))
            return "Request successful!"
        except Exception as e:
            LOG.error("Request incoming resource failed: {}".format(e))

    def _incoming_base(self, data, projectid, taskid, service_name):
        """
            Basic incoming data processor
            Redirect based on service type
            Save result to text file
        """
        try:
            LOG.debug("Speech processing incoming {} (Project ID: {}, Task ID: {})".format(service_name, projectid, taskid))
            with self.db as db:
                year = db.get_project(projectid, fields=["year"])["year"]
                if not year:
                    raise ConflictError("(projectid={}) Project no longer exists".format(projectid))
                jobid = db.get_task_field(projectid, taskid, year, fields=["jobid"])["jobid"]
                if not jobid:
                    raise ConflictError("No job expected (Project ID: {}, Task ID: {})".format(projectid, taskid))

                textfile = db.get_task_field(projectid, taskid, year, fields=["textfile"])["textfile"]
                if textfile is None:
                    raise NotFoundError("This task has no text file")

            self._test_read(textfile)

            if "errstatus" in data:
                if len(data["errstatus"]) != 0:
                    self._append_to_textfile(projectid, taskid, textfile, "ERROR: Speech job fail! {}".format(data["errstatus"]))
                    raise Exception("Speech job failed: (Project ID: {}, Task ID: {})".format(projectid, taskid))

            if "CTM" not in data:
                self._append_to_textfile(projectid, taskid, textfile, "ERROR: Speech job fail! NO CTM from output!!")
                raise Exception("No CTM found in data: (Project ID: {}, Task ID: {})".format(projectid, taskid))

            with self.db as db:
                repo.check(os.path.dirname(textfile))
                with codecs.open(textfile, "w", "utf-8") as f:
                    f.write(data["CTM"])
                commitid, modified = repo.commit(os.path.dirname(textfile), os.path.basename(textfile), "Changes saved")
                db.save_text(projectid, taskid, year, commitid, modified)
                db.set_jobid(projectid, taskid, year, None)
                db.set_errstatus(projectid, taskid, year, None)
                LOG.info("Speech processing result received successfully for project ID: {}, Task ID: {}".format(projectid, taskid))

        except Exception as e:
            LOG.error("Speech processing failure: {}".format(e))
            with self.db as db:
                if "errstatus" in data:
                    if  len(data["errstatus"]) != 0:
                        LOG.error("Speech processing failure: {}".format(data["errstatus"]))
                        db.set_errstatus(projectid, taskid, year, data["errstatus"])
                    elif data["errstatus"] is None:
                        db.set_errstatus(projectid, taskid, year, "Requested Speech Service Error!")
                    else:
                        db.set_errstatus(projectid, taskid, year, "{}".format(e))
                else:
                    db.set_errstatus(projectid, taskid, year, "{}".format(e))
                db.set_jobid(projectid, taskid, year, None)

    def _append_to_textfile(self, projectid, taskid, textfile, text):
        """
            Append error message textfile
            so user knowns what is going on
        """
        try: # Handle repo errors
            with self.db as db:
                out = "<p><font color='red'> {} <font></p>".format(text)
                repo.check(os.path.dirname(textfile))
                with codecs.open(textfile, "a", "utf-8") as f:
                    f.write(out)
                commitid, modified = repo.commit(os.path.dirname(textfile), os.path.basename(textfile), "Changes saved")
                db.save_text(projectid, taskid, year, commitid, modified)
                db.set_jobid(projectid, taskid, year, None)
                db.set_errstatus(projectid, taskid, year, None)
                LOG.info("Appending error message to textfile, project ID: {}, Task ID: {}".format(projectid, taskid))
        except Exception as e:
            raise

    @authlog("Mark task done")
    def task_done(self, request):
        """
            Re-assign this task to collator
        """
        try:
            with self.db as db:
                db.check_project_task(request["projectid"], request["taskid"], check_err=True)
                year = db.get_project(request["projectid"], fields=["year"])["year"]
                db.task_done(request["projectid"], request["taskid"], year)

            return "Task Marked as Done!"
        except Exception as e:
            LOG.error("Mark task done fail: {}".format(e))
            raise

    @authlog("Mark task done")
    def reassign_task(self, request):
        """
            Re-assign this task to editor (from collator)
        """
        try:
            with self.db as db:
                db.check_project_task(request["projectid"], request["taskid"], check_err=True)
                year = db.get_project(request["projectid"], fields=["year"])["year"]
                db.reassign_task(request["projectid"], request["taskid"], year)

            return "Task reassigned to editor!"
        except Exception as e:
            LOG.error("Reassign_task failed: {}".format(e))
            raise

    @authlog("Unlock the task")
    def unlock_task(self, request):
        """
            Cancel speech job
        """
        try:
            with self.db as db:
                db.check_project_task(request["projectid"], request["taskid"], check_err=True, check_task_job=False)
                project = db.get_project(request["projectid"], fields=["year", "audiofile"])
                task = db.get_task_field(request["projectid"], request["taskid"], project["year"], fields=["start", "end", "jobid"])

                if task["jobid"] is None:
                    raise NotFoundError("No Job has been specified")

                jobreq = {"token" : self._speech.token(), "jobid" : task["jobid"]}
                LOG.debug(os.path.join(SPEECHSERVER, self._config["speechservices"]["API"]["delete"]))
                LOG.debug("{}".format(jobreq))
                reqstatus = requests.post(os.path.join(SPEECHSERVER, self._config["speechservices"]["delete"]), data=json.dumps(jobreq))
                reqstatus = reqstatus.json()

                db.set_jobid(request["projectid"], request["taskid"], project["year"], None)
                db.delete_incoming(request["projectid"], request["taskid"],)
                db.delete_outgoing(request["projectid"], request["taskid"], task["start"], task["end"])

            return "Speech job cancelled"
        except Exception as e:
            LOG.error("Unlock task fail: {}".format(e))
            raise

    @authlog("Clear task error status")
    def clear_error(self, request):
        """
            Clear the error status for task
        """
        try:
            with self.db as db:
                db.check_project_task(request["projectid"], request["taskid"])
                year = db.get_project(request["projectid"], fields=["year"])["year"]
                db.set_errstatus(request["projectid"], request["taskid"], year, None)

            return "Cleared task error status"
        except Exception as e:
            LOG.error("Clear error fail: {}".format(e))
            raise

    @authlog("Build up MS-WORD document")
    def buildmaster(self, request):
        """
            Return MS-WORD document from all the files
        """
        try:
            with self.db as db:
                options = db.get_project_text(request["projectid"])

                all_text = []
                for taskid in sorted(options.keys()):
                    textfile = options[taskid]

                    if textfile is None or len(textfile) == 0:
                        raise NotFoundError("Text file is missing for a task")

                    if not os.path.exists(textfile):
                        raise NotFoundError("Cannot find text file")

                    self._test_read(textfile)

                    with codecs.open(textfile, "r", "utf-8") as f:
                        text = f.read()
                        all_text.append(text)

                all_text = u"\n".join(all_text)
                LOG.info(all_text)
                _html = tempfile.NamedTemporaryFile(delete=False)
                with codecs.open(_html.name, "w", "utf-8") as f:
                    f.write(all_text)

                _docx = tempfile.NamedTemporaryFile(delete=False)
                _docx.close()

                cmd = "pandoc -f html -t docx -o {} {}".format(_docx.name, _html.name)
                ps = subprocess.Popen(cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                stdout, stderr = ps.communicate()
                LOG.info(stdout)
                LOG.error(stderr)

                outurl = auth.gen_token()
                db.insert_outgoing(request["projectid"], outurl, _docx.name, "-1.0", "-1.0")
                os.remove(_html.name)
            return {"url" : outurl}

        except Exception as e:
            LOG.error("Get text failed: {}".format(e))
            raise

    @authlog("Returning list of languages")
    def list_languages(self, request):
        """Return languages
        """
        return {"languages" : self._config["languages"]}

    @authlog("Update assigned language")
    def update_language(self, request):
        """Update language
        """
        try:
            if request["language"] not in self._config["languages"]:
                raise NotFoundError("Language not supported by speech services!")
            with self.db as db:
                db.check_project_task(request["projectid"], request["taskid"], check_err=False)
                year = db.get_project(request["projectid"], fields=["year"])["year"]
                db.update_language(request["projectid"], request["taskid"], year, request["language"])
            return "Language changed!"
        except Exception as e:
            LOG.error("Update language fail: {}".format(e))
            raise


class EditorDB(sqlite.Connection):
    def lock(self):
        self.execute("BEGIN IMMEDIATE")

    def check_project(self, projectid, check_err=False):
        """This should be run before attempting to make changes to a project,
           it does the following:
             -- Locks the DB
             -- Checks whether the project exists
             -- Check whether the project is "locked"
             -- Optionally check whether the project has `errstatus` set
        """
        self.lock()
        row = self.execute("SELECT year, jobid, errstatus FROM projects WHERE projectid=?", (projectid,)).fetchone()
        if row is None: #project exists?
            raise NotFoundError("Project not found")
        row = dict(row)
        if row["jobid"]: #project clean?
            raise ConflictError("This project is currently locked with jobid: {}".format(row["jobid"]))
        if check_err and row["errstatus"]:
            raise PrevJobError("{}".format(row["errstatus"]))

    def check_project_task(self, projectid, taskid, check_err=False, check_task_job=True):
        """This should be run before attempting to make changes to a project,
           it does the following:
             -- Locks the DB
             -- Checks whether the project exists
             -- Check whether the project is "locked"
             -- Optionally check whether the project has `errstatus` set
        """
        self.lock()
        row = self.execute("SELECT year, jobid, errstatus FROM projects WHERE projectid=?", (projectid,)).fetchone()
        if row is None: #project exists?
            raise NotFoundError("Project not found")
        row = dict(row)
        if row["jobid"]: #project clean?
            raise ConflictError("This project is currently locked with jobid: {}".format(row["jobid"]))
        if check_err and row["errstatus"]:
            raise PrevJobError("{}".format(row["errstatus"]))

        row_t = self.execute("SELECT jobid, errstatus FROM T{} WHERE taskid=? AND projectid=?".format(row["year"]), (taskid, projectid,)).fetchone()
        if row_t is None: #task exists?
            raise NotFoundError("Task not found")
        row_t = dict(row_t)
        if check_task_job:
            if row_t["jobid"]: #task clean?
                raise ConflictError("This task is currently locked with jobid: {}".format(row_t["jobid"]))
        if check_err and row_t["errstatus"]:
            raise PrevJobError("{}".format(row_t["errstatus"]))

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

    def get_task_field(self, projectid, taskid, year, fields):
        fields = set(fields)
        query = "SELECT {} FROM T{} WHERE taskid=? AND projectid=?".format(", ".join(fields), year)
        row = self.execute(query, (taskid, projectid)).fetchone()
        try:
            row = dict(row)
        except TypeError:
            row = {}
        return row

    def get_project_text(self, projectid):
        self.check_project(projectid, check_err=True)
        _tmp = self.get_project(projectid, fields=["year"])
        query = "SELECT taskid, textfile FROM T{} WHERE projectid=?".format(_tmp["year"])
        row = self.execute(query, (projectid,)).fetchall()
        try:
            row = dict(row)
        except TypeError:
            row = {}
        return row

    def get_all_tasks(self, this_user, mode="editor"):
        # Fetch all the projects which have been assigned
        if mode == "editor":
            projectids = self.execute("SELECT projectid, projectname, category FROM projects WHERE assigned='Y'").fetchall()
        elif mode == "collator":
            projectids = self.execute("SELECT projectid, projectname, category FROM projects WHERE assigned='Y' AND collator='{}'".format(this_user)).fetchall()
        else:
            raise BadRequestError("get_all_tasks: unknown mode = {}".format(mode))

        if projectids is None:
            return "No projects have been created"
        projectids = map(dict, projectids)
        LOG.debug("{}".format(projectids))

        # Check if project is okay
        project_okay = []
        for projectid in projectids:
            self.check_project(projectid["projectid"], check_err=True)
            project_okay.append((projectid["projectid"], projectid["projectname"], projectid["category"]))
        if not project_okay:
            return "No projects have been created"

        # Fetch all the years 
        years = []
        for projectid, projectname, category in project_okay:
            _tmp = self.get_project(projectid, fields=["year"])
            years.append((projectid, projectname, category, _tmp["year"]))
        LOG.debug("{}".format(years))

        # Fetch all tasks
        raw_tasks = []
        for projectid, projectname, category, year in years:
            if mode == "editor":
                _tmp = self.execute("SELECT * FROM T{} WHERE projectid=? AND editor=?".format(year), (projectid, this_user,)).fetchall()
            elif mode == "collator":
                _tmp = self.execute("SELECT * FROM T{} WHERE projectid=?".format(year), (projectid,)).fetchall()

            if _tmp is not None:
                _tmp = map(dict, _tmp)
                for x in _tmp: x.update({"year" : year, "projectname" : projectname, "category" : category})
                raw_tasks.extend(_tmp)

        return raw_tasks

    def save_text(self, projectid, taskid, year, commitid, modified):
        self.execute("UPDATE T{} SET commitid=?, modified=? WHERE taskid=? AND projectid=?".format(year),
            (commitid, modified, taskid, projectid))

    def task_done(self, projectid, taskid, year):
        row = self.execute("SELECT collator FROM projects WHERE projectid=?", (projectid,)).fetchone()
        if row is None: #project exists?
            raise NotFoundError("Project not found")
        row = dict(row)
        self.execute("UPDATE T{} SET editing='{}' WHERE taskid=? AND projectid=?".format(year, row["collator"]), (taskid, projectid))
        self.execute("UPDATE T{} SET completed=? WHERE taskid=? AND projectid=?".format(year), (time.time(), taskid, projectid))

    def reassign_task(self, projectid, taskid, year):
        row = self.execute("SELECT editor FROM T{} WHERE taskid=? AND projectid=?".format(year), (taskid, projectid)).fetchone()
        row = dict(row)
        self.execute("UPDATE T{} SET editing='{}' WHERE taskid=? AND projectid=?".format(year, row["editor"]), (taskid, projectid))
        self.execute("UPDATE T{} SET completed=? WHERE taskid=? AND projectid=?".format(year), (None, taskid, projectid))

    def update_language(self, projectid, taskid, year, language):
        self.execute("UPDATE T{} SET language='{}' WHERE taskid=? AND projectid=?".format(year, language), (taskid, projectid))

    def insert_incoming(self, projectid, taskid, inurl, servicetype):
        self.execute("INSERT INTO incoming (projectid, taskid, url, servicetype) VALUES (?,?,?,?)", (projectid, taskid, inurl, servicetype))

    def insert_outgoing(self, projectid, outurl, audiofile, start, end):
        self.execute("INSERT INTO outgoing (projectid, url, audiofile, start, end) VALUES (?,?,?,?,?)", (projectid,
            outurl, audiofile, start, end))

    def delete_incoming_byurl(self, inurl):
        self.execute("DELETE FROM incoming WHERE url=?", (inurl,))

    def delete_outgoing_byurl(self, outurl):
        self.execute("DELETE FROM outgoing WHERE url=?", (outurl,))

    def set_jobid(self, projectid, taskid, year, jobid):
        self.execute("UPDATE T{} SET jobid=? WHERE taskid=? AND projectid=?".format(year), (jobid, taskid, projectid))

    def set_errstatus(self, projectid, taskid, year, message):
        self.execute("UPDATE T{} SET errstatus=? WHERE taskid=? AND projectid=?".format(year), (message, taskid, projectid))

    def delete_incoming(self, projectid, taskid):
        self.execute("DELETE FROM incoming WHERE taskid=? AND projectid=?", (taskid, projectid))

    def delete_outgoing(self, projectid, audiofile, start, end):
        self.execute("DELETE FROM outgoing WHERE projectid=? AND audiofile=? AND start=? AND end=?", (projectid, audiofile, start, end))

    def get_outgoing(self, uri):
        row = self.execute("SELECT projectid, audiofile, start, end FROM outgoing WHERE url=?", (uri,)).fetchone()
        if row is not None:
            self.execute("DELETE FROM outgoing WHERE url=?", (uri,))
            row = dict(row)
        else:
            row = {}
        return row

    def get_incoming(self, uri):
        row = self.execute("SELECT projectid, taskid, servicetype FROM incoming WHERE url=?", (uri,)).fetchone()
        if row is not None:
            self.execute("DELETE FROM incoming WHERE url=?", (uri,))
            row = dict(row)
        else:
            row = {}
        return row


class PrevJobError(Exception):
    pass

if __name__ == "__main__":
    pass

