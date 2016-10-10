# Application server for the Parliament transcription Platform

WSGI RESTful application server that implements an API specific to the RSA Parliament

## INSTALL

Assuming Ubuntu 14.04/16.04:

### Clone source

Cloned Parliament application server from BitBucket [https://bitbucket.org/ntkleynhans/parliament_platform.git](https://bitbucket.org/ntkleynhans/parliament_platform.git)

```
$ sudo apt-get install git python-bcrypt
$ mkdir work
$ cd work
$ git clone https://bitbucket.org/ntkleynhans/parliament_platform.git
```

### Docker
Next step is to install Docker:
```
$ sudo apt-get install docker.io
```

Add yourself to the docker group:
```
$ sudo gpasswd -a <your_user_name> docker
```

Log out and log in for group change to take effect


**Change docker location (optional)**

Change docker image location.

Stop docker service:
```
sudo service docker stop
```

Edit /etc/defaults/docker file and add the following option:
```
DOCKER_OPTS="-g /home/docker"
```

Create new docker location:
```
sudo mkdir /home/docker
```

Restart the docker service:
```
sudo docker start
```

### Build docker image

Build the application server Docker image.
For more instructions see `./install/README.md`

### Create databases

Use the database creation tools in `./app_server/tools/` to create the various databases.  

Setup authentication databases using `./app_server/tools/authdb.py`

```
$ mkdir ~/stp
$ ./app_server/tools/authdb.py ~/stp/editor_admin_auth.db
$ ./app_server/tools/authdb.py ~/stp/editor_auth.db
$ ./app_server/tools/authdb.py ~/stp/projects_admin_auth.db
$ ./app_server/tools/authdb.py ~/stp/projects_auth.db
```
Setup project databases using `./app_server/tools/projectdb.py`

```
$ mkdir -p ~/stp/
$ ./app_server/tools/authdb.py ~/stp/projects.db
```

Refer to `./install/README.md` on how to build and run docker image using these databases.

## TESTING

Testing tools are located in `./app_server/tools/`

* project_tester.py - Project interface tester
* sim_editor_tester.py - Automatic editor interface workflow simulation tester
* cmd_editor_tester.py - One-shot editor interface tester

For more information see `./app_server/tools/README.md`
