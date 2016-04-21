#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function #Py2

import os
import json

try:
    from sqlite3 import dbapi2 as sqlite
except ImportError:
    from pysqlite2 import dbapi2 as sqlite

#DEMIT: Here or in Admin config file?
AUTHDB_FILE = os.path.join(os.getenv("STP_AUTHDB_DIR"), "auth.db")

class Admin:
    """Implements all functions related to updating user information in
       the auth database.
    """
    def __init__(self, config_file):
        with open(config_file) as infh:
            self._config = json.loads(infh.read())

    def adduser(self, request):
        with sqlite.connect(AUTHDB_FILE) as db_conn:
            db_curs = db_conn.cursor()
            db_curs.execute("INSERT INTO users (name, role_admin) VALUES (?,?)", (request['name'], 0))
            db_conn.commit()
