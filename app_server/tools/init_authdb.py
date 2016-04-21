#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Simple script to make empty authentication database ("auth.db") for
   the application server.
"""
from __future__ import unicode_literals, division, print_function #Py2

__author__ = "Daniel van Niekerk"
__email__ = "dvn.demitasse@gmail.com"

import os
import argparse

try:
    from sqlite3 import dbapi2 as sqlite
except ImportError:
    from pysqlite2 import dbapi2 as sqlite

DEF_OUTDIR = os.getenv("STP_AUTHDB_DIR")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--outdir', metavar='OUTDIR', type=str, dest="outdir", default=DEF_OUTDIR, help="")
    args = parser.parse_args()
    outdir = args.outdir
    
    with sqlite.connect(os.path.join(outdir, "auth.db")) as db_conn:
        db_curs = db_conn.cursor()
        db_curs.execute("CREATE TABLE users ( name VARCHAR(20) PRIMARY KEY, role_admin INTEGER )")
        db_curs.execute("CREATE TABLE tokens ( token VARCHAR(20) PRIMARY KEY, username VARCHAR(20) )")
        db_conn.commit()
