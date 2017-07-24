BUILDING AN APPLICATION SERVER DOCKER IMAGE
===========================================

This directory contains the files necessary to build an application server Docker image. To build, place the `Dockerfile` and complete repository in a build location with structure as follows:

```
.
|-- Dockerfile
`-- stp
    |-- app_server
    |   |-- config
    |   |-- service
    |   `-- tools
    `-- install
```

To build the docker image you must provide the user (UID) and group (GID) ids. To retrieve the UID and GID, type `id` in the Linux command line:
```bash
id
```
You will get an output that looks something like this:
```
uid=1024(ntkleynhans) gid=1027(ntkleynhans) groups=1027(ntkleynhans),4(adm),20(dialout),24(cdrom)
```

To build the docker image run, with your UID and GID (below is just an example!):

```bash
docker build -t stp --build-arg UID=1024 --build-arg GID=1027 .
```

Testing the built service
-------------------------

### Create databases

Firstly, create a directory on the host filesystem to serve as persistent file storage location (we will use `~/stp` as an example):

```bash
mkdir ~/stp
```

Set up two new authentication databases, for the main (projects, editor) and admin services, in this directory using the `authdb.py` tool (these files should match the setup in `app_server/config/dispatcher.json`:

```bash
python stp/app_server/tools/authdb.py ~/stp/auth.db
python stp/app_server/tools/authdb.py --rootpass <rootpass> ~/stp/admin.db
```

### Install speech server

Next, build the speech docker image and run before continuing.
Cloned the Speech server from BitBucket: [https://bitbucket.org/ntkleynhans/tech_services](https://bitbucket.org/ntkleynhans/tech_services).
Once cloned, following the install instructions.

*NOTE*: remember to add a user to the speech auth database and update the `app_server/config/dispatcher.conf` file, where you
add the new USERNAME and PASSWORD.

```
   "speechserver" : {
        "username" : "USERNAME",
        "password" : "PASSWORD",
        "login" : "jobs/login",
        "logout" : "jobs/logout",
        "logout2": "jobs/logout2",
        "discover" : "jobs/discover"
    }
```

[comment]: # (Open another terminal, edit the code if needed and then start simple speech server located in `~/stp/app_server/tools/`)

[comment]: # (``` $ ./simple_speech_server.py ```)

### Fix Host Apache configuration

Enable Apache Proxy modules:
```bash
sudo a2enmod proxy
sudo a2enmod proxy_http
sudo a2enmod proxy_balancer
sudo a2enmod lbmethod_byrequests
```

Edit the hosts Apache configuration file (/etc/apache2/apache.conf) and add the following `ProxyPass` commands:
```
ProxyPass "/app" "http://127.0.0.1:9999/wsgi"
ProxyPassReverse "/app" "http://127.0.0.1:9999/wsgi"
```

If your system has a firewall then you should open the port `9999`.

Restart the Apache service:
```bash
sudo service apache2 restart
```

[comment]: # ( ``` ProxyPass "/app" "http://127.0.0.1:9999/wsgi" ProxyPassReverse "/app" "http://127.0.0.1:9999/wsgi" ```)

### Run application server docker images

Run the docker image making sure:
 
  - to mount the host directory created above
  - and designate a host port for usage (`9999` in this case)
  - provide UID and GID (as in when you built the `stp` docker image above)
  - provide the URL for the application server (APPSERVER=URL)
  - provide the URL for the speech server (SPEECHSERVER=URL)

```bash
docker run --name stp --env UID=1024 --env GID=1027 --env APPSERVER=http://127.0.0.1/app --env SPEECHSERVER=http://127.0.0.1/speech --env SO_SNDTIMEO=600 -v /mnt/data2/home2/ntkleynhans/stp:/mnt/stp -d -p 9999:80 stp:latest
```

### Test the application server using CURL

Log into the _projects admin_ service as root:

```bash
curl -i -k -v -H "Content-Type: application/json" -X POST -d '{"username": "root", "password": <rootpass>, "role" : "admin"}' http://127.0.0.1/app/admin/login
```

which should return a token (your token will be different and you must keep track of this token as subsquent requests make use of this token), e.g.:

```json
{"message": "YmVkNWEyNzYtM2IwZS00ZDFmLTg0YjAtYzk0YjU3ZjI2N2I1"}
```

Use this token to add a user to the _projects_ service:

```bash
curl -i -k -v -H "Content-Type: application/json" -X POST -d '{"token": "YmVkNWEyNzYtM2IwZS00ZDFmLTg0YjAtYzk0YjU3ZjI2N2I1", "username": "neil", "password": "neil", "name": "neil", "surname": "kleynhans", "email": "neil@organisation.org", "role" : "project"}' http://127.0.0.1/app/admin/adduser
```

Log into the _projects_ service as the new user:

```bash
curl -i -k -v -H "Content-Type: application/json" -X POST -d '{"username": "neil", "password": "neil", "role" : "project"}' http://127.0.0.1/app/projects/login
```

Use the returned token to access other functions of the _projects_ service.

### Stop and remove the docker image

To stop and remove the docker container run the following:
```bash
docker stop stp
docker rm stp
```
