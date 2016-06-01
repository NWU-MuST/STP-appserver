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
from httperrs import *

LOG = logging.getLogger("APP.EDITOR")
SPEECHSERVER = os.getenv("SPEECHSERVER")
APPSERVER = os.getenv("APPSERVER")

class Admin(admin.Admin):
    pass

class Editor(auth.UserAuth):

    def __init__(self, config_file):
        with open(config_file) as infh:
            self._config = json.loads(infh.read())

    def load_tasks(self, request):
        """
            Load tasks assigned to editor
        """
        this_user = auth.token_auth(request["token"], self._config["authdb"])

        with sqlite.connect(self._config['projectdb']) as db_conn:
            db_curs = db_conn.cursor()

            # Fetch all the projects which have been assigned
            db_curs.execute("SELECT * FROM projects WHERE assigned='Y'")
            projects = db_curs.fetchall()
            if projects is None:
                return "No projects have been created"

            # Fetch all the years 
            db_curs.execute("SELECT DISTINCT year FROM projects")
            years = db_curs.fetchall()
            years = [str(int(x[0])) for x in years]

            # Fetch all tasks assigned to user
            """
            taskid VARCHAR(36), projectid VARCHAR(36), editor VARCHAR(20), collator VARCHAR(20), start REAL, end REAL, textfile VARCHAR(64),
            timestamp REAL, jobid VARCHAR(36), errstatus VARCHAR(128), editorrw VARCHAR(1), collatorrw VARCHAR(1)
            """
            raw_tasks = []
            for year in years:
                table_name = 'T%s' % table_name
                db_curs.execute("SELECT * FROM ? WHERE editor=?", (table_name, this_user))
                _tmp = db_curs.fetchall()
                #TODO: I don't think I should send the table name back
                # This does not work with style
                _tmp = [x + (table_name,) for x in _tmp]
                raw_tasks.extend(_tmp)

            # Sort tasks
            tasks  = {'SPEECHLOCKED' : [], 'NOTASSIGNED' : [], 'CANOPEN' : []}
            for this_task in raw_tasks:
                if this_task[-4] is not None and this_task[-4] != '':
                     tasks['SPEECHLOCKED'].append(this_task)
                elif this_task[-1] is not None and this_task[-1] != '':
                     tasks['NOTASSIGNED'].append(this_task)
                else:
                     tasks['CANOPEN'].append(this_task)

            return tasks

    def task_audio(self, request):
        """
            Return the audio for this specific task
        """
        auth.token_auth(request["token"], self._config["authdb"])
        with sqlite.connect(self._config['projectdb']) as db_conn:
            db_curs = db_conn.cursor()
            db_curs.execute("SELECT audiofile FROM projects")
            audiofile = db_curs.fetchone()

            db_curs.execute("SELECT start, end FROM ? WHERE taskid=?", (request["tablename"], request["taskid"]))
            _tmp = db_curs.fetchone()
            audiorange = [float(_tmp[0][0]), float(_tmp[0][1])]

        return {'filename' : audiofile, 'range' : audiorange, 'mime' : 'audio/ogg'}

    def task_text(self, request):
        """
            Return the text data for this specific task
        """
        auth.token_auth(request["token"], self._config["authdb"])
        with sqlite.connect(self._config['projectdb']) as db_conn:
            db_curs = db_conn.cursor()
            db_curs.execute("SELECT textfile FROM ? WHERE taskid=?", (request["tablename"], request["taskid"]))
            textfile = db_curs.fetchone()

        with codecs.open(textfile[0], "r", "utf-8") as f:
            text = f.read()

        return {'text' : text}

    def save_text(self, request):
        """
            Save the provided text to task
        """
        #TODO: Fall in with DvN implementation
        auth.token_auth(request["token"], self._config["authdb"])
        with sqlite.connect(self._config['projectdb']) as db_conn:
            db_curs = db_conn.cursor()
            db_curs.execute("SELECT textfile FROM ? WHERE taskid=?", (request["tablename"], request["taskid"]))
            textfile = db_curs.fetchone()

        with codecs.open(textfile[0], "w", "utf-8") as f:
            f.write(request["text"])

    #TODO: can't generalise with projects.py - this version accesses the tasks table not project table
    def speech_job(self, request):
        """
            Diarize, Recognize or align audio
        """
        auth.token_auth(request["token"], self._config["authdb"])

        #Parse speech job
        if request["service"] not in self._config["speechservices"]:
            raise NotFoundError("{} not supported. Options are: {}".format(request['service'], self._config["speechservices"]))

        #Attempt to "lock" project and create I/O access
        with sqlite.connect(self._config['tasksdb']) as db_conn:
            db_curs = db_conn.cursor()
            db_curs.execute("BEGIN IMMEDIATE") #lock the db early...
            db_curs.execute("SELECT * FROM projects WHERE taskid=?", (request["taskid"],))
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
            #TODO: should change `projectid` to something more general
            db_curs.execute("INSERT INTO incoming (projectid, url, tasktype) VALUES (?,?,?)", (request["taskid"],
                                                                                               inurl,
                                                                                               "diarize"))
            db_curs.execute("INSERT INTO outgoing (projectid, url, audiofile) VALUES (?,?,?)", (request["taskid"],
                                                                                                outurl,
                                                                                                audiofile))
            db_conn.commit()
        #Make job request
        jobreq = {"token" : request["token"], "getaudio": os.path.join(APPSERVER, outurl),
            "putresult": os.path.join(APPSERVER, inurl)}
	    jobreq.update(self.config["speechservices"][request["service"])

        LOG.debug(os.path.join(SPEECHSERVER, self._config["speechservices"][request["service"]]))
        reqstatus = requests.post(os.path.join(SPEECHSERVER, self._config["speech"][request["service"]]["url"]), data=json.dumps(jobreq))
        reqstatus = reqstatus.json()
        #TODO: handle return status
        LOG.debug("{}".format(reqstatus))
        #Handle request status
        if "jobid" in reqstatus: #no error
            with sqlite.connect(self._config['projectdb']) as db_conn:
                db_curs = db_conn.cursor()
                db_curs.execute("UPDATE projects SET jobid=? WHERE projectid=?", (reqstatus["jobid"],
                                                                                  request["projectid"]))
                db_conn.commit()
            LOG.info("Diarize audio request sent for project ID: {}, job ID: {}".format(request["projectid"], reqstatus["jobid"]))
            return "Request successful!"
        #Something went wrong: undo project setup
        with sqlite.connect(self._config['projectdb']) as db_conn:
            db_curs = db_conn.cursor()
            db_curs.execute("UPDATE projects SET jobid=? WHERE projectid=?", ("",
                                                                              request["projectid"]))
            db_curs.execute("DELETE FROM incoming WHERE projectid=?", (request["projectid"],))
            db_curs.execute("DELETE FROM outgoing WHERE projectid=?", (request["projectid"],))
            db_conn.commit()
        LOG.info("Diarize audio request failed for project ID: {}".format(request["projectid"]))
        return reqstatus #DEMIT TODO: translate error from speech server!

   def outgoing(self, uri):
        with sqlite.connect(self._config['projectdb']) as db_conn:
            db_curs = db_conn.cursor()
            db_curs.execute("SELECT * FROM outgoing WHERE url=?", (uri,))
            entry = db_curs.fetchone()
            #URL exists?
            if entry is None:
                raise MethodNotAllowedError(uri)
            projectid, url, audiofile = entry
            db_curs.execute("DELETE FROM outgoing WHERE url=?", (uri,))
            db_conn.commit()
        LOG.info("Returning audio for project ID: {}".format(projectid))
        return {"mime": "audio/ogg", "filename": audiofile}


    def incoming(self, uri, data):
        LOG.debug("incoming_data: {}".format(data))
        with sqlite.connect(self._config['projectdb']) as db_conn:
            db_curs = db_conn.cursor()
            db_curs.execute("SELECT * FROM incoming WHERE url=?", (uri,))
            entry = db_curs.fetchone()
        #URL exists?
        if entry is None:
            raise MethodNotAllowedError(uri)
        projectid, url, tasktype = entry
        #Switch to handler for "tasktype"
        assert tasktype in self._config["speechtasks"], "tasktype '{}' not supported...".format(tasktype)
        #assert data["projectid"] == projectid, "Unexpected Project ID..."
        handler = getattr(self, "_incoming_{}".format(tasktype))
        handler(data, projectid) #should throw exception if not successful
        #Cleanup DB
        with sqlite.connect(self._config['projectdb']) as db_conn:
            db_curs = db_conn.cursor()
            db_curs.execute("DELETE FROM incoming WHERE url=?", (uri,))
            db_conn.commit()
        LOG.info("Incoming data processed for project ID: {}".format(projectid))
        return "Request successful!"

    def _incoming_speech(self, data, taskid)
        """
            Process incoming text data send from the speech server
        """
        with sqlite.connect(self._config['projectdb']) as db_conn:
            db_curs = db_conn.cursor()
            db_curs.execute("SELECT * FROM projects WHERE projectid=?", (projectid,))
            entry = db_curs.fetchone()
            #Need to check whether project exists?
            projid, projname, projcat, username, audiofile, year, creation, jobid, errstatus = entry
            if "CTM" in data: #all went well
                LOG.info("Diarisation success (Project ID: {}, Job ID: {})".format(projectid, jobid))
                #Parse CTM file
                segments = [line.split() for line in data["CTM"].splitlines()]
                LOG.info("CTM parsing successful..")
                db_curs.execute("DELETE FROM T{} WHERE projectid=?".format(year), (projectid,)) #assume already OK'ed
                for starttime, endtime in segments:
                    taskid = str(uuid.uuid4())
                    while taskid in projects:
                        taskid = str(uuid.uuid4())
                    taskid = 't%s' % taskid.replace('-', '')
                    db_curs.execute("INSERT INTO T{} (taskid, projectid, start, end) VALUES(?,?,?,?)".format(year),
                                    (taskid, projectid, starttime, endtime))
                db_curs.execute("UPDATE projects SET jobid=? WHERE projectid=?", (None, projectid))
                db_curs.execute("UPDATE projects SET errstatus=? WHERE projectid=?", (None, projectid))
            else: #"unlock" and recover error status
                LOG.info("Diarisation failure (Project ID: {}, Job ID: {})".format(projectid, jobid))
                db_curs.execute("UPDATE projects SET jobid=? WHERE projectid=?", (None, projectid))
                db_curs.execute("UPDATE projects SET errstatus=? WHERE projectid=?", (data["errstatus"], projectid))
            db_conn.commit()
        LOG.info("Diarization result received successfully for project ID: {}".format(projectid))

    def _ctm_editor(self, ctm):
        """
            Convert the speech server output CTM format to editor format
        """
        return ctm

    def task_done(self, request):
        """
            Re-assign this task to collator
        """
        auth.token_auth(request["token"], self._config["authdb"])
        with sqlite.connect(self._config['projectdb']) as db_conn:
            db_curs = db_conn.cursor()
            db_curs.execute("SELECT * FROM projects WHERE projectid=?", (projectid,))
            entry = db_curs.fetchone()
            year = entry[-4]
            db_curs.execute("UPDATE T{} SET editorrw='N' WHERE taskid='{}'" % (year, request["taskid"]))
            db_curs.execute("UPDATE T{} SET collatorrw='Y' WHERE taskid='{}'" % (year, request["taskid"]))
            db_conn.commit()

