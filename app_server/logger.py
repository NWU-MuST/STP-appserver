#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import unicode_literals, division, print_function, with_statement #Py2

import logging
import logging.handlers
import json
import codecs
import os

class Logger:

    def __init__(self, config_file):
        self._config_file = config_file
        self._config = {}

    def new_logger(self, name):
        """
            Create a new logging file
        """
        with codecs.open(self._config_file, 'r', 'utf-8') as f:
            self._config = json.load(f)

        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)

        _new_file = os.path.join(self._config['logging']['dir'], '%s.log' % name)
        fh = logging.handlers.TimedRotatingFileHandler(_new_file, when="d", interval=1)
        formatter = logging.Formatter(self._config['logging']['format'])
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)

    def get_logger(self, name):
        """
            Return logging instance
        """
        return self.logger.getChild(name)

if __name__ == "__main__":
    pass

