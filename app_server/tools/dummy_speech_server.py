#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function #Py2

import time
import BaseHTTPServer
import json
import uuid
import base64
import time
import os
import requests
import threading
import Queue
import urllib
import json
import socket

#Hack to get IP:
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.connect(("gmail.com",80))
host_ip = s.getsockname()[0]
s.close()

HOST_NAME = host_ip # !!!REMEMBER TO CHANGE THIS!!!
PORT_NUMBER = 9950 # Maybe set this to 9000.

Q = Queue.Queue()

class dHandle(threading.Thread):

    def __init__(self, q):
        threading.Thread.__init__ (self)
        self.q = q
        self.running = True

    def run(self):
        while self.running:
            if not self.q.empty():
                job = self.q.get()
                print("Processing job:", "{}".format(job))
                job = json.loads(job)

                print('Fetching: %s -> %s' % (job["getaudio"], "tmp.tmp.tmp"))
                urllib.urlretrieve(job["getaudio"], "tmp.tmp.tmp")
                print(os.path.getsize("tmp.tmp.tmp"))
                time.sleep(1)

                print('Uploading result to: %s' % (job["putresult"]))
                pkg = json.dumps({"CTM" : "0.0\t1.0\tSIL\n1.0\t20.0\tSPK\n"})
                headers = {"Content-Type" : "application/json", "Content-Length" : str(len(pkg))}
                response = requests.put(job["putresult"], headers=headers, data=pkg)
                print(response.status_code, response.text)
                os.remove("tmp.tmp.tmp")

                self.q.task_done()
            else:
                time.sleep(1)

    def stop(self):
        self.running = False


class MyHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    def do_POST(s):
        """Respond to a GET request."""

        s.send_response(200)
        s.send_header("Content-type", "application/json")
        s.end_headers()

        data = None
        if os.path.basename(s.path) == "login":
            data = {"token" : base64.urlsafe_b64encode(str(uuid.uuid4()))}
        elif os.path.basename(s.path) == "logout":
            data = {"message" : "User logged out"}
        elif os.path.basename(s.path) == "addjob":
            length = int(s.headers.getheader('content-length'))
            job = s.rfile.read(length)
            Q.put(job)
            data = {"jobid" : "123"}
        elif os.path.basename(s.path) == "deletejob":
            data = {"message" : "Job deleted"}
        else:
            data = {"message" : "Unknown request"}

        s.wfile.write(json.dumps(data))


if __name__ == '__main__':
    server_class = BaseHTTPServer.HTTPServer
    httpd = server_class((HOST_NAME, PORT_NUMBER), MyHandler)

    dH = dHandle(Q)
    dH.start()

    print(time.asctime(), "Server Starts - %s:%s" % (HOST_NAME, PORT_NUMBER))
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass

    dH.stop()
    dH.join()

    httpd.server_close()
    print(time.asctime(), "Server Stops - %s:%s" % (HOST_NAME, PORT_NUMBER))

