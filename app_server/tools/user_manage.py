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
import getpass

try:
    from sqlite3 import dbapi2 as sqlite
except ImportError:
    from pysqlite2 import dbapi2 as sqlite #for old Python versions

import bcrypt #Ubuntu/Debian: apt-get install python-bcrypt

def new_db(dbfn):
    db_conn = sqlite.connect(dbfn)
    db_curs = db_conn.cursor()
    return db_conn


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("outfn", metavar="OUTFN", type=str, help="Output DB filename.")
    parser.add_argument("task", metavar="TASK", type=str, help="Task to perform: ADD, DEL, LSUSR, RMTOK")
    args = parser.parse_args()

    db_conn = new_db(args.outfn)
    db_curs = db_conn.cursor()

    if args.task.upper() == "ADD":
        inputs = {}
        params = ["username", "name", "surname", "email", "role"]
        for item in params:
            stdin = ""
            while stdin == "":
                stdin = raw_input("Enter {}: ".format(item))
                inputs[item] = stdin

        pw = ""
        while pw == "":
            pw = getpass.getpass()
            inputs["password"] = pw

        try:
            salt = bcrypt.gensalt(prefix=b"2a")
        except:
            salt = bcrypt.gensalt()
        pwhash = bcrypt.hashpw(inputs["password"], salt)

        db_curs.execute("INSERT INTO users ( username, pwhash, salt, name, surname, email, role, tmppwhash ) VALUES (?,?,?,?,?,?,?,?)", (inputs["username"], pwhash, salt, inputs["name"], inputs["surname"], inputs["email"], inputs["role"], None))
        db_conn.commit()

    elif args.task.upper() == "DEL":
        username = ""
        while username == "":
            username = raw_input("Enter username: ")

        db_curs.execute("DELETE FROM users WHERE username=?", (username,))
        db_conn.commit()

    elif args.task.upper() == "LSUSR":
        db_curs.execute("SELECT username FROM users")
        rows = db_curs.fetchall()
        for usr in rows:
            print(usr[0])

    elif args.task.upper() == "RMTOK":
        username = ""
        while username == "":
            username = raw_input("Enter username: ")

        db_curs.execute("DELETE FROM tokens WHERE username=?", (username,))
        db_conn.commit()

    else:
        print("Unknown command: {}".format(args.task.upper()))
        import sys
        sys.exit(-1)

