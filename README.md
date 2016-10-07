# Application server for the Parliament transcription Platform

WSGI RESTful application server that implements an API specific to the RSA Parliament

## INSTALL

### Clone source

Cloned Parliament application server from Github [https://ntkleynhans@bitbucket.org/ntkleynhans/parliament_platform.git](https://ntkleynhans@bitbucket.org/ntkleynhans/parliament_platform.git)
```
$ git clone https://ntkleynhans@bitbucket.org/ntkleynhans/parliament_platform.git
```

### Docker
Next step is to install Docker *(on ubuntu)*:
```
$ apt-get install docker.io
```

**Change docker location (optional)**

Change docker image location (*ubuntu*).

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

Here we chose the `~/stp` location to store the databases.  
This must be passed via the docker run command using the `-v` option:

```
$ docker run -d --name stp -v ~/stp:/mnt/stp -p 9999:80 stp_base:latest
```

## TESTING

Testing tools are located in `./app_server/tools/`

* project_tester.py - Project interface tester
* sim_editor_tester.py - Automatic editor interface workflow simulation tester
* cmd_editor_tester.py - One-shot editor interface tester

For more information see `./app_server/tools/README.md`
