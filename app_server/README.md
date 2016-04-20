18 April 2016:
--------------

Initial TODOs:
--------------

i) Configure Apache to forward requests

ii) Compile UWSGI python module and binary

	- download uwsgi-2.0.12.tar.gz
	- extract
	- apply patch uwsgi-2.0.12.stp.patch
		$ patch -p7 < uwsgi-2.0.12.stp.patch
	- build binary and python module
		$ sudo apt-get install libpcre3 libpcre3-dev
		$ make
		$ python uwsgiconfig.py --build buildconf/python.ini
	


Start application server:
-------------------------

$ uwsgi/bin/uwsgi -l 2 -p 1  --enable-threads --plugin uwsgi/plugins/python_plugin.so --socket 127.0.0.1:9090 --wsgi-file wsgi.py  --env services_config=config/dispatcher.json

Basic Tests:
-----------

Add token to server
$ curl -i -k -v -H "Content-Type: application/json" -X PUT -d '{"name": "neil"}' https://127.0.0.1/wsgi/addtoken

Request token - doesn't work as token are not persistent at this stage
$ curl -i -k -v -X GET https://127.0.0.1/wsgi/checktoken?name=neil

