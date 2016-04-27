#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function #Py2

import datetime
FORMAT = "%Y-%m-%d %H:%M:%S"

def timestamp_now():
    """
        Return string version of current date and time
    """
    return datetime.datetime.now().strftime(FORMAT)

def timestamp_datetime(timestamp_string):
    """
        Convert string timestamp to datetime object for further processing
    """
    return datetime.datetime.strptime(timestamp_string, FORMAT)

