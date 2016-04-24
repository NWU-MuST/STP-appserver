APPLICATION SERVER
==================

This is the application server implementation. It handles authentication and requests originating from authenticated user sessions.


INSTALL
-------

The application server requires:

  - Python and associated modules
  - uWSGI and associated Python modules
  - Apache 2 and associated uWSGI module

The recommended way of installing and running is via [Docker][1], either pre-built or by building using the files provided in `../install`. See `README.md` in `../install` for instructions to start and test the server in this way.


MANUALLY RUNNING THE SERVER
---------------------------

Example of how to run the server (Apache2 + uWSGI):

```bash
/usr/sbin/apache2ctl start & uwsgi --uid 1000 -l 2 -p 1  --enable-threads --plugin /usr/lib/uwsgi/plugins/python27_plugin.so --socket 127.0.0.1:9090 --wsgi-file wsgi.py  --env services_config=config/dispatcher.json
```

----------------------------------------------------------------------------------------------------

[1]: https://www.docker.com/
