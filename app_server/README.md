# APPLICATION SERVER

This is the application server implementation. It handles authentication and requests originating from authenticated user sessions.


## INSTALL


The application server requires:

  - Python and associated modules
  - uWSGI and associated Python modules
  - Apache 2 and associated uWSGI module

The recommended way of installing and running is via [Docker][1], either pre-built or by building using the files provided in `../install`. See `README.md` in `../install` for instructions to start and test the server in this way.

## Contents

 * `config/` - Application server configuration files
 * `service/` - Application server modules
 * `tools/` - database and user management tools

See the README.md files in each of the sub-directories for more information.

----------------------------------------------------------------------------------------------------

[1]: https://www.docker.com/
