#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function #Py2

from admin import Admin

#from exceptions import *

class Projects(Admin):

    def create_project(self, request):
        raise NotImplementedError

    def load_project(self, request):
        raise NotImplementedError

    def save_project(self, request):
        raise NotImplementedError
