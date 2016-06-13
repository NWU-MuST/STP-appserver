project_tester:
===============

Run project_tester.py to test project functionality of application server.

When run you'll get the following output:

```
$ ./project_tester.py

Accessing Docker app server via: http://127.0.0.1:9999/wsgi/
Enter command (type help for list)>
```

Type `help` or `list` to  get a list of commands:
```
Enter command (type help for list)> list
ADMINLIN - Admin login
ADMINLOUT - Admin logout
ADDUSER - add new user

LOGIN - user login
LOGOUT - user logout
LISTCATEGORIES - list project categories
CREATEPROJECT - create a new project
LISTPROJECTS - list projects
LOADPROJECT - load projects
UPLOADAUDIO - upload audio to project
GETAUDIO - retrieve project audio
SAVEPROJECT - save tasks to a project

EXIT - quit
Enter command (type help for list)>
```

To test the functionality you type the command and hit enter.

Command description:
====================

ADMINLIN
--------
    Login as Admin

ADMINLOUT
---------
    Logout as Admin

ADDUSER
-------
    Add a new user to project database. You must run `ADMINLIN` first to login as Admin user

LOGIN
-----
    Login as user. You must run `ADDUSER` before running this command

LOGOUT
------
    Logout as user

LISTCATEGORIES
--------------
    List project categories as defined in project JSON config -- see `config/project.json`

CREATEPROJECT
-------------
    Create a new project. You must have first run `ADDUSER` to add a project user and `LOGIN` to login as that user

LISTPROJECTS
------------
    List projects all projects owned by user. You run `LOGIN` first

LOADPROJECT
-----------
    Load a specific project's details. Run `LOGIN` and `CREATEPROJECT` before running this command

UPLOADAUDIO
-----------
    Upload audio to a new project. `test.ogg` must be in the script directory. You must run `LOGIN` and `CREATEPROJECT` first

GETAUDIO
------------
    Retrieve uploaded project audio. This will save the audio to `tmp.ogg`. Run `LOGIN`, `CREATEPROJECT`, `UPLOADAUDIO` first.

SAVEPROJECT
-----------
    Save defined tasks to a project. Run `LOGIN`, `CREATEPROJECT`, `UPLOADAUDIO` first.

EXIT
----
    Quit the script and logout as user and admin, if logged in.

