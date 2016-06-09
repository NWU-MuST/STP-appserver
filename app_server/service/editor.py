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

class Admin(admin.Admin):
    pass

class Editor(auth.UserAuth):

    def __init__(self, config_file, speechserv):
        with open(config_file) as infh:
            self._config = json.loads(infh.read())
        self._speech = speechserv

    def load_tasks(self, request):
        """
            Load tasks assigned to editor
            Task state is: CANOPEN, READONLY, SPEECHLOCKED, ERROR
        """
        this_user = auth.token_auth(request["token"], self._config["authdb"])

        with sqlite.connect(self._config["projectdb"]) as db_conn:
            db_conn.row_factory = sqlite.Row
            db_curs = db_conn.cursor()

            # Fetch all the projects which have been assigned
            db_curs.execute("SELECT projectid FROM projects WHERE assigned='Y'")
            projects = map(dict, db_curs.fetchall())
            if projects is None:
                return "No projects have been created"

            # Fetch all the years 
            db_curs.execute("SELECT DISTINCT year FROM projects")
            years = map(dict, db_curs.fetchall())

            # Fetch all tasks
            raw_tasks = []
            for year in years:
                db_curs.execute("SELECT * FROM T{} WHERE editor=?".format(year["year"]), (this_user,))

                _tmp = map(dict, db_curs.fetchall())
                for x in _tmp: x.update({"year" : year["year"]})
                raw_tasks.extend(_tmp)

            if len(raw_tasks) == 0:
                return "No tasks assigned to editor"

            # Sort tasks
            tasks  = {"SPEECHLOCKED" : [], "READONLY" : [], "CANOPEN" : [], "ERROR" : []}
            for this_task in raw_tasks:
                if this_task["errstatus"] is not None and this_task["errstatus"] != "":
                     tasks["ERROR"].append(this_task)
                elif this_task["jobid"] is not None and this_task["jobid"] != "":
                     tasks["SPEECHLOCKED"].append(this_task)
                elif int(this_task["ownership"]) == 1: #TODO: this enum should most probably sit somewhere
                     tasks["READONLY"].append(this_task)
                elif int(this_task["ownership"]) == 0:
                     tasks["CANOPEN"].append(this_task)
                else:
                    #TODO: should we raise a 500?
                    this_task["errstatus"] = "This task is malformed -- something went wrong"
                    tasks["ERROR"].append(this_task)

            return tasks

    def task_audio(self, request):
        """
            Return the audio for this specific task
        """
        #TODO: check if audiofile, start and end is valid
        # check if you can access this project

        auth.token_auth(request["token"], self._config["authdb"])
        with sqlite.connect(self._config["projectdb"]) as db_conn:
            db_conn.row_factory = sqlite.Row
            db_curs = db_conn.cursor()

            db_curs.execute("SELECT * FROM projects WHERE projectid=?", (request["projectid"],))
            project = db_curs.fetchone()
            if project is None:
                raise NotFoundError("Project not found")
            project = dict(project)

            db_curs.execute("SELECT start, end FROM T{} WHERE taskid=? AND projectid=?".format(project["year"]), (request["taskid"], request["projectid"]))
            _tmp = dict(db_curs.fetchone())
            audiorange = [float(_tmp["start"]), float(_tmp["end"])]

        return {"filename" : project["audiofile"], "range" : audiorange, "mime" : "audio/ogg"}

    def task_text(self, request):
        """
            Return the text data for this specific task
        """
        #TODO: check if user can access this task - not speech or error lock

        auth.token_auth(request["token"], self._config["authdb"])
        with sqlite.connect(self._config["projectdb"]) as db_conn:
            db_conn.row_factory = sqlite.Row
            db_curs = db_conn.cursor()

            db_curs.execute("SELECT * FROM projects WHERE projectid=?", (request["projectid"],))
            project = db_curs.fetchone()
            if project is None:
                raise NotFoundError("Project not found")
            project = dict(project)

            db_curs.execute("SELECT textfile FROM T{} WHERE taskid=? AND projectid=?".format(project["year"]), (request["taskid"],request["projectid"]))
            task = dict(db_curs.fetchone())
            if task is None:
                raise NotFoundError("Task not found")
            task = dict(task)

        with codecs.open(task["textfile"], "r", "utf-8") as f: text = f.read()

        return {"text" : text}

    def save_text(self, request):
        """
            Save the provided text to task
        """
        #TODO: check if you can save to this task -- check lock

        auth.token_auth(request["token"], self._config["authdb"])
        with sqlite.connect(self._config["projectdb"]) as db_conn:
            db_conn.row_factory = sqlite.Row
            db_curs = db_conn.cursor()

            db_curs.execute("SELECT * FROM projects WHERE projectid=?", (request["projectid"],))
            project = db_curs.fetchone()
            if project is None:
                raise NotFoundError("Project not found")
            project = dict(project)

            db_curs.execute("SELECT * FROM T{} WHERE taskid=? AND projectid=?".format(project["year"]), (request["taskid"],request["projectid"]))
            task = db_curs.fetchone()
            if task is None:
                raise NotFoundError("Task not found")
            task = dict(task)
            textdir = os.path.dirname(task["textfile"])
            #TODO: check errors, not sure how we recover from here
            repo.check(textdir)
            with codecs.open(task["textfile"], "w", "utf-8") as f:
                f.write(request["text"])
            task["commitid"], task["modified"] = repo.commit(textdir, os.path.basename(task["textfile"]), "Changes saved")
            db_curs.execute("UPDATE T{} SET commitid=?, modified=? WHERE taskid=? AND projectid=?".format(project["year"]),
                (task["commitid"], task["modified"], request["taskid"], request["projectid"]))
            db_conn.commit()

        return "Text Saved!"

    def speech_job(self, request):
        """
            Request speech processing: diarize, speech recognition or alignment
        """
        auth.token_auth(request["token"], self._config["authdb"])

        # Check if service exists
        if request["service"] not in self._config["speechservices"]["services"]:
            raise NotFoundError("Requested speech service not available")

        # Check all parameters
        for value in self._config["speechservices"]["services"][request["service"]]["require"]:
            if value not in request:
                raise BadRequestError("Missing parameter in request: {}".format(value))

        #Attempt to "lock" projects and create I/O access
        with sqlite.connect(self._config['projectdb']) as db_conn:
            db_conn.row_factory = sqlite.Row
            db_curs = db_conn.cursor()
            db_curs.execute("BEGIN IMMEDIATE") #lock the db early...

            db_curs.execute("SELECT * FROM projects WHERE projectid=?", (request["projectid"],))
            project = db_curs.fetchone()
            if project is None:
                raise NotFoundError("Project not found")
            project = dict(project)

            db_curs.execute("SELECT start, end, jobid "
                            "FROM T{} "
                            "WHERE taskid=? AND projectid=?".format(project["year"]), (request["taskid"],request["projectid"]))
            task = db_curs.fetchone()
            #Task exists?
            if task is None:
                db_conn.commit()
                raise NotFoundError("Task not found")
            task = dict(task)

            #Task clean? #DEMIT: Also check whether already split into tasks?
            if task["jobid"]:
                db_conn.commit()
                raise ConflictError("A job with id '{}' is already pending on this task".format(jobid))

            #Setup I/O access
            inurl = auth.gen_token()
            outurl = auth.gen_token()

            db_curs.execute("UPDATE T{} "
                            "SET jobid=? "
                            "WHERE taskid=? AND projectid=?".format(project["year"]), ("pending",
                                                  request["taskid"], request["projectid"]))
            db_curs.execute("INSERT INTO incoming "
                            "(projectid, taskid, url, servicetype) VALUES (?,?,?,?)", (request["projectid"], request["taskid"],
                                                                          inurl,
                                                                          request["service"]))
            db_curs.execute("INSERT INTO outgoing "
                            "(projectid, url, audiofile, start, end) VALUES (?,?,?,?,?)", (request["projectid"],
                                                                           outurl, project["audiofile"], task["start"], task["end"]))
            db_conn.commit()
        #Make job request
        #TEMPORARILY COMMENTED OUT FOR TESTING WITHOUT SPEECHSERVER:
        #TODO: fix editor reference
        jobreq = {"token" : self._speech.token(), "getaudio": os.path.join(APPSERVER, "editor", outurl),
                   "putresult": os.path.join(APPSERVER, "editor", inurl)}
        jobreq["service"] = request["service"]
        jobreq["subsystem"] = self._config["speechservices"]["services"][request["service"]]["subsystem"]
        for value in self._config["speechservices"]["services"][request["service"]]["require"]:
            jobreq[value] = request[value]

        LOG.debug(os.path.join(SPEECHSERVER, self._config["speechservices"]["url"]))
        LOG.debug("{}".format(jobreq))
        reqstatus = requests.post(os.path.join(SPEECHSERVER, self._config["speechservices"]["url"]), data=json.dumps(jobreq))
        reqstatus = reqstatus.json()
        #reqstatus = {"jobid": auth.gen_token()} #DEMIT: dummy call for testing!

        #TODO: handle return status
        LOG.debug("{}".format(reqstatus))
        #Handle request status
        if "jobid" in reqstatus: #no error
            with sqlite.connect(self._config['projectdb']) as db_conn:
                db_curs = db_conn.cursor()
                db_curs.execute("UPDATE T{} "
                                "SET jobid=? "
                                "WHERE taskid=? AND projectid=?".format(project["year"]), (reqstatus["jobid"],
                                                      request["taskid"], request["projectid"]))
                db_conn.commit()
            LOG.info("Speech service request sent for project ID: {}, task ID: {}, job ID: {}".format(request["projectid"], request["taskid"], reqstatus["jobid"]))
            return "Request successful!"
        #Something went wrong: undo project setup
        with sqlite.connect(self._config['projectdb']) as db_conn:
            db_curs = db_conn.cursor()
            db_curs.execute("UPDATE T{} "
                            "SET jobid=? "
                            "WHERE taskid=? AND projectid=?".format(project["year"]), (None,
                                                  request["taskid"], request["projectid"]))
            if "message" in reqstatus:
                db_curs.execute("UPDATE T{} "
                                "SET errstatus=? "
                                "WHERE taskid=? AND projectid=?".format(project["year"]), (reqstatus["message"],
                                                      request["taskid"], request["projectid"]))
            db_curs.execute("DELETE FROM incoming "
                            "WHERE url=?", (inurl,))
            db_curs.execute("DELETE FROM outgoing "
                            "WHERE url=?", (outurl,))
            db_conn.commit()
        LOG.error("Speech service request failed for project ID: {}, task ID: {}".format(request["projectid"], request["taskid"]))
        return reqstatus #DEMIT TODO: translate error from speech server!

    def outgoing(self, uri):
        """
        """
        LOG.debug(uri)
        with sqlite.connect(self._config['projectdb']) as db_conn:
            db_conn.row_factory = sqlite.Row
            db_curs = db_conn.cursor()
            db_curs.execute("SELECT projectid, audiofile, start, end "
                            "FROM outgoing WHERE url=?", (uri,))
            entry = db_curs.fetchone()
            LOG.debug(entry)
            #URL exists?
            if entry is None:
                raise MethodNotAllowedError(uri)
            entry = dict(entry)

            db_curs.execute("DELETE FROM outgoing WHERE url=?", (uri,))
            db_conn.commit()
        LOG.info("Returning audio for project ID: {}".format(entry["projectid"]))

        # Check if audio range is available
        if entry["start"] is not None and entry["end"] is not None:
            return {"mime": "audio/ogg", "filename": entry["audiofile"], "range" : (float(entry["start"]), float(entry["end"]))}
        else:
            return {"mime": "audio/ogg", "filename": entry["audiofile"]}


    def incoming(self, uri, data):
        """
        """
        LOG.debug("incoming_data: {}".format(data))
        with sqlite.connect(self._config['projectdb']) as db_conn:
            db_conn.row_factory = sqlite.Row
            db_curs = db_conn.cursor()
            db_curs.execute("SELECT projectid, taskid, servicetype "
                            "FROM incoming "
                            "WHERE url=?", (uri,))
            entry = db_curs.fetchone()
        #URL exists?
        if entry is None:
            raise MethodNotAllowedError(uri)
        entry = dict(entry)

        #Switch to handler for "servicetype"
        #assert servicetype in self._config["speechservices"], "servicetype '{}' not supported...".format(servicetype)
        #handler = getattr(self, "_incoming_{}".format(servicetype))
        #handler(data, projectid, taskid) #will throw exception if not successful
        #TODO: I don't think the servicetype uis needed

        self._incoming_speech(data, entry["projectid"], entry["taskid"])

        #Cleanup DB
        with sqlite.connect(self._config['projectdb']) as db_conn:
            db_curs = db_conn.cursor()
            db_curs.execute("DELETE FROM incoming "
                            "WHERE url=?", (uri,))
            db_conn.commit()
        LOG.info("Incoming data processed for project ID: {}, task ID: {}".format(entry["projectid"], entry["taskid"]))
        return "Request successful!"


    def _incoming_speech(self, data, projectid, taskid):
        """
        """
        with sqlite.connect(self._config['projectdb']) as db_conn:
            db_conn.row_factory = sqlite.Row
            db_curs = db_conn.cursor()

            # Get task table
            db_curs.execute("SELECT year FROM projects WHERE projectid=?", (projectid,))
            entry = db_curs.fetchone()
            if entry is None:
                LOG.error("Incoming speech processing error (Project ID: {}, Task ID: {}, Job ID: {})".format(projectid, taskid, jobid))
                db_curs.execute("UPDATE projects SET jobid=?, errstatus=? WHERE projectid=?", (None, data["errstatus"], projectid))
                db_conn.commit()
                raise NotFoundError("Project not found!")
            entry = dict(entry)
            year = entry["year"]

            # Fetch jobid
            db_curs.execute("SELECT jobid "
                            "FROM T{} "
                            "WHERE taskid=? AND projectid=?".format(year), (taskid, projectid))
            entry = db_curs.fetchone()
            if entry is None:
                LOG.error("Incoming speech processing error (Project ID: {}, Task ID: {}, Job ID: {})".format(projectid, taskid, jobid))
                db_curs.execute("UPDATE projects SET jobid=?, errstatus=? WHERE projectid=?", (None, data["errstatus"], projectid))
                db_conn.commit()
                raise NotFoundError("Task not found!")
            entry = dict(entry)
            jobid = entry["jobid"]

            #Need to check whether project exists?
            if "CTM" in data: #all went well
                LOG.info("Speech processing success (Project ID: {}, Task ID: {}, Job ID: {})".format(projectid, taskid, jobid))
                #Parse CTM file
                ctm = self._ctm_editor(data["CTM"])

                db_curs.execute("SELECT * FROM T{} WHERE taskid=? AND projectid=?".format(year), (taskid, projectid))
                task = dict(db_curs.fetchone())

                #TODO: if something goes wrong here....
                repo.check(os.path.dirname(task["textfile"]))
                with codecs.open(task["textfile"], "w", "utf-8") as f:
                    f.write(ctm)

                task["commitid"], task["modified"] = repo.commit(os.path.dirname(task["textfile"]), os.path.basename(task["textfile"]), "Changes saved")
                task["errstatus"] = None
                task["jobid"] = None
                db_curs.execute("UPDATE T{} SET commitid=?, modified=? WHERE taskid=? AND projectid=?".format(year),
                    (task["commitid"], task["modified"], taskid, projectid))

            else: #"unlock" and recover error status
                LOG.error("Speech processing failure (Project ID: {}, Task ID: {}, Job ID: {})".format(projectid, taskid, jobid))
                db_curs.execute("UPDATE T{} SET jobid=?, errstatus=? WHERE taskid=? AND projectid=?".format(year), (None, data["errstatus"], taskid, projectid))
            db_conn.commit()
        LOG.info("Speech processing result received successfully for project ID: {}, Task ID: {}".format(projectid, taskid))

    def _ctm_editor(self, ctm):
        """
            Convert the speech server output CTM format to editor format
        """
        #segments = [map(float, line.split()) for line in ctm.splitlines()]
        #segments.sort(key=lambda x:x[0]) #by starttime
        LOG.info("CTM parsing successful..")
        return ctm

    def task_done(self, request):
        """
            Re-assign this task to collator
        """
        auth.token_auth(request["token"], self._config["authdb"])
        #TODO: must perform checks before doing this
        with sqlite.connect(self._config['projectdb']) as db_conn:
            db_conn.row_factory = sqlite.Row
            db_curs = db_conn.cursor()

            db_curs.execute("SELECT * FROM projects WHERE projectid=?", (request["projectid"],))
            project = db_curs.fetchone()
            if project is None:
                raise NotFoundError("Project not found")
            project = dict(project)

            db_curs.execute("UPDATE T{} SET ownership=1 WHERE taskid=? AND projectid=?".format(project["year"]), (request["taskid"], request["projectid"]))
            db_conn.commit()

        return "Task Marked on Done!"

    def cancel_job(self, request):
        """
            Cancel speech job
        """
        auth.token_auth(request["token"], self._config["authdb"])
        with sqlite.connect(self._config['projectdb']) as db_conn:
            db_conn.row_factory = sqlite.Row
            db_curs = db_conn.cursor()

            db_curs.execute("SELECT * FROM projects WHERE projectid=?", (request["projectid"],))
            project = db_curs.fetchone()
            if project is None:
                raise NotFoundError("Project not found")
            project = dict(project)

            db_curs.execute("SELECT * FROM T{} WHERE taskid=? AND projectid=?".format(project["year"]), (request["taskid"], request["projectid"]))
            task = db_curs.fetchone()
            if task is None:
                raise NotFoundError("Task not found")
            task = dict(task)

            if task["jobid"] is None:
                raise NotFoundError("No Job has been specified")

            #TODO: tell speech server to stop job

            db_curs.execute("UPDATE T{} SET jobid=?, errstatus=? WHERE taskid=? AND projectid=?".format(project["year"]),
                (None, None, request["taskid"], request["projectid"]))
            db_curs.execute("DELETE FROM incoming WHERE taskid=? AND projectid=?", (request["taskid"], request["projectid"]))
            db_curs.execute("DELETE FROM outgoing WHERE projectid=? AND audiofile=? AND start=? AND end=?",
                (request["projectid"], project["audiofile"], task["start"], task["end"]))
            db_conn.commit()

        return "Speech job cancelled"

    def update_task(self, request):
        """
            Modify a task field
        """
        #TODO: user can change anything on the task -- is dangerous

        auth.token_auth(request["token"], self._config["authdb"])
        with sqlite.connect(self._config['projectdb']) as db_conn:
            db_conn.row_factory = sqlite.Row
            db_curs = db_conn.cursor()

            db_curs.execute("SELECT * FROM projects WHERE projectid=?", (request["projectid"],))
            project = db_curs.fetchone()
            if project is None:
                raise NotFoundError("Project not found")
            project = dict(project)

            db_curs.execute("SELECT * FROM T{} WHERE taskid=? AND projectid=?".format(project["year"]), (request["taskid"], request["projectid"]))
            task = db_curs.fetchone()
            if task is None:
                raise NotFoundError("Task not found")
            task = dict(task)

            if request["field"] not in task:
                raise NotFoundError("Task does not have field: {}".format(request["field"]))

            db_curs.execute("UPDATE T{} SET {}=? WHERE taskid=? AND projectid=?".format(project["year"], request["field"]),
                (request["value"], request["taskid"], request["projectid"]))
            db_conn.commit()

        return "Task updated"


    def _fetch_task(self):
        pass

    def _fetch_project(self):
        pass

    def _task_check_error(self):
        pass

    def _task_check_job(self):
        pass


if __name__ == "__main__":
    pass

