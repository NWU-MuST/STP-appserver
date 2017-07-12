# Testing Tools

## authdb.py

Used to create an admin and user authentication databases for different services:

```
./authdb.py --rootpass rootpass /path/to/database/admin.db
./authdb.py /path/to/database/auth.db
```

This tool should be used to create a single authentication database for project and editor and a single administration database.
Edit config/auth.db and config/admin.db to refer to these databases.

## projectdb.py

Create an initial project table used to store project details:

```
./projectdb.py /path/to/database/project.db
```

## user_manage.py

Command line tool to add a user, delete a user, list the users and remove a login token for a user.

Usage:

```bash
$ ./user_manage.py INDB (ADD|DEL|LSUSR|RMTOK)
```

```
ADD - Add a new user
DEL - delete an existing user
LSUSR - list all registered users
RMTOK - remove a stale login token for a specific user
```

## project_tester:

Run project_tester.py to test project functionality of application server.  
It runs in two modes: simulation and interactive

## Simulation mode

In this mode the tester simulates a random work flow.

```
./project_tester.py --testfile ptest01.json --dbfile ~/stp/projects.db --mindelay 0.0 --maxdelay 0.0 --nusers 4 --nprocs 4 simulation
```

## Interactive mode

When run you'll get the following output:

```
$ /project_tester.py --testfile ptest01.json --dbfile ~/stp/projects.db interactive
2016-10-26 17:54:13,133 [INFO] PTESTER on tid:admin in __init__(): SEED: None
Enter command (type help for list)>
```

Type `help` or `list` to  get a list of commands:
```
Enter command (type help for list)> list
ADMINLIN - Admin login
ADMINLOUT - Admin logout
ADMINLOUT2 - Admin logout (with username & password)
ADDUSER - add new user
DELUSER - delete new user
LOGIN - user login
LOGOUT - user logout
LOGOUT2 - user logout (with username & password)
CHANGEPASSWORD - change user user password
CHANGEBACKPASSWORD - change user user password back
LISTCATEGORIES - list project categories
LISTLANGUAGES - list languages
CREATEPROJECT - create a new project
LISTPROJECTS - list projects
LOADUSERS - load users
LOADPROJECT - load projects
UPLOADAUDIO - upload audio to project
GETAUDIO - retrieve project audio
SAVEPROJECT - save tasks to a project
ASSIGNTASKS - assign tasks to editors
DIARIZEAUDIO - save tasks to a project via diarize request (simulate speech server)
DIARIZEAUDIO2 - like DIARIZEAUDIO but withouth speech server (project stays locked)
UNLOCKPROJECT - unlock project (can test this against DIARIZEAUDIO2)
EXIT - quit
Enter command (type help for list)>
```

To test the functionality you type the command and hit enter.

## Project Command description:


### ADMINLIN

* Login as Admin

## ADMINLOUT

* Logout as Admin

### ADMINLOUT2

* Logout as Admin using a username and password (used when a token is still registered in the database)

### DELUSER

* Delete a user

## ADDUSER

* Add a new user to project database. You must run `ADMINLIN` first to login as Admin user

### LOGIN

* Login as user. You must run `ADDUSER` before running this command

### LOGOUT

* Logout as user using a token

### LOGOUT2

* Logout using a username and password (remove token in database)

### CHANGEPASSWORD

* Change user user password

### CHANGEBACKPASSWORD

* Change user user password back

### LISTLANGUAGES

* List languages supported by the platform

### LISTCATEGORIES

* List project categories as defined in project JSON config -- see `config/project.json`

### LOADUSERS

* Load all registered users

### CREATEPROJECT

* Create a new project. You must have first run `ADDUSER` to add a project user and `LOGIN` to login as that user

### LISTPROJECTS

* List projects all projects owned by user. You run `LOGIN` first

### LOADPROJECT

* Load a specific project's details. Run `LOGIN` and `CREATEPROJECT` before running this command

### UPLOADAUDIO

* Upload audio to a new project. `test.ogg` must be in the script directory. You must run `LOGIN` and `CREATEPROJECT` first

### GETAUDIO

* Retrieve uploaded project audio. This will save the audio to `tmp.ogg`. Run `LOGIN`, `CREATEPROJECT`, `UPLOADAUDIO` first.

### SAVEPROJECT

* Save defined tasks to a project. Run `LOGIN`, `CREATEPROJECT`, `UPLOADAUDIO` first.

### ASSIGNTASKS

* Assign tasks to editors

### DIARIZEAUDIO

* Save tasks to a project via diarize request (simulate speech server)

### DIARIZEAUDIO2

* Similar to DIARIZEAUDIO but withouth speech server (project stays locked)

### UNLOCKPROJECT

* Unlock project (can test this against DIARIZEAUDIO2)

### EXIT

* Quit the script and logout as user and admin, if logged in.

## simple_speech_server

Simulates a speech server with limited functionality.  
Need to run this before running any editor testers.
You may have to edit the IP and port

```
./simple_speech_server.py
```

## editor_tester

### Simulation mode

Simulates a number of editors accessing the application server.  
Before running the simulation the dummy speech server must be running.  
To run the editor tester you must running the code in the following order.

* P_ADDUSERS : add project users to database
* ADDPROJECT : add projects to database
* E_ADDUSERS : add editors to database
* SIMULATE : run the simulation

Below is the commands run in the CLI:
```
$ ./editor_tester.py P_ADDUSERS
$ ./editor_tester.py ADDPROJECT
$ ./editor_tester.py E_ADDUSERS
$ ./editor_tester.py SIMULATE
```

### Command line mode

This version of the editor tester runs in an one-shot mode i.e. you call each command seperately.  
Before testing the editor you should create projects, add project users and add editor users.  
Below are the project-specific commands:

### P_ADDUSERS
* Add project users to database

### ADDPROJECT
* Add projects to database

### E_ADDUSERS
* Add editors to database

Once the project content has been loaded you can test the editor-specific interface.  
You must provide a user name when running these commands.  
The user name can be in the range of `usr001` to `usr020`.

E.G.
```
./editor_tester.py <COMMAND> usr001
```

### GETAUDIO
* Return task audio

### GETTEXT
* Return task text

### SAVETEXT
* Save text to file

### SAVEALLTEXT
* Save text to all tasks in project

### CLEARTEXT
* Remove text from file

### TASKDONE
* Set the task is done

### UNLOCKTASK
* Cancel a speech job

### CLEARERROR
* Remove task error status

### DIARIZE
* Submit diarize job

### RECOGNIZE
* Submit recognize job

### ALIGN
* Submit align job


## Collator testing

The editor tester can also test the following collator functionality in command line mode:

E.G.
```
./editor_tester.py <COMMAND> usr001
```

### REASSIGNTASK
* Assign task back to editor

### BUILDMASTER
* Collate all project text and build a MS-WORD document

