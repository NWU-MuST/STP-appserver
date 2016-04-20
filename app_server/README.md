APPLICATION SERVER
==================

This is the application server implementation. It handles authentication and requests originating from authenticated user sessions.


INSTALL
-------

The application server requires:

  - Python and associated modules
  - uWSGI and associated Python modules
  - Apache 2 and associated uWSGI module

The recommended way of installing and running is via [Docker][1], either pre-built or by building using the files provided in `../install`.


MANUALLY RUNNING THE SERVER
---------------------------

Example of how to run the server (Apache2 + uWSGI):

```bash
/usr/sbin/apache2ctl start & uwsgi --uid 1000 -l 2 -p 1  --enable-threads --plugin /usr/lib/uwsgi/plugins/python27_plugin.so --socket 127.0.0.1:9090 --wsgi-file wsgi.py  --env services_config=config/dispatcher.json
```

### Basic Tests:

Add token to server:

```bash
curl -i -k -v -H "Content-Type: application/json" -X PUT -d '{"name": "neil"}' https://127.0.0.1/wsgi/addtoken
```

Request token - doesn't work as token are not persistent at this stage:

```bash
curl -i -k -v -X GET https://127.0.0.1/wsgi/checktoken?name=neil
```

----------------------------------------------------------------------------------------------------

[1]: https://www.docker.com/
