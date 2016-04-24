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
    from pysqlite2 import dbapi2 as sqlite #for old Python versions

import bcrypt #Ubuntu/Debian: apt-get install python-bcrypt

def create_new_db(dbfn):
    db_conn = sqlite.connect(dbfn)
    db_curs = db_conn.cursor()
    db_curs.execute("CREATE TABLE users ( username VARCHAR(30) PRIMARY KEY, pwhash VARCHAR(60), salt VARCHAR(30), name VARCHAR(30), surname VARCHAR(30), email VARCHAR(50) )")
    db_curs.execute("CREATE TABLE tokens ( token VARCHAR(20) PRIMARY KEY, username VARCHAR(20), expiry TIMESTAMP)")
    db_conn.commit()
    return db_conn


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("outfn", metavar="OUTFN", type=str, help="Output DB filename.")
    parser.add_argument("rootpass", metavar="ROOTPASS", type=str, help="Password for default user 'root'.")
    args = parser.parse_args()
    outfn = args.outfn
    
    salt = bcrypt.gensalt()
    pwhash = bcrypt.hashpw(args.rootpass, salt)
    
    db_conn = create_new_db(outfn)
    db_curs = db_conn.cursor()
    db_curs.execute("INSERT INTO users ( username, pwhash, salt, name, surname, email ) VALUES (?,?,?,?,?,?)", ("root", pwhash, salt, "", "", ""))
    db_conn.commit()
