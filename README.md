Application Server for Parliament Transcription Platform
========================================================

This is the "Parliament-specific" application server component implemented as a proof-of-concept during the Speech Transcription Platform project by the [Multilingual Speech Technologies](http://www.nwu.ac.za/must/) group at North-West University. The project was sponsored by the Department of Arts and Culture of South Africa.

This is a WSGI RESTful application server that implements an API specific to the RSA Parliament.

Below are the basic installation instructions for __this component__, however, documentation for the project/platform as a whole can be found [here](https://bitbucket.org/ntkleynhans/stp_docs), refer specifically to the [Master Installation Document](https://bitbucket.org/ntkleynhans/stp_docs/raw/e2cf012def8a2a1aa1ebd132f826bff95e361592/installation/Master_Installation.pdf).

## Installation

Assuming Ubuntu 14.04/16.04:

### Clone source

Cloned Parliament application server from BitBucket https://bitbucket.org/ntkleynhans/parliament_platform.git

```bash
$ sudo apt-get install git python-bcrypt
$ git clone https://bitbucket.org/ntkleynhans/parliament_platform.git stp
```

To build the docker file for the "deployment version" select the correct docker script:

```bash
$ cd parliament_platform
$ ln -s stp/install/Dockerfile
```

alternatively, build the "development version" which launches a minimal "dummy" speech server inside the docker container. To use this version link to the following Docker file:

```bash
$ cd parliament_platform
$ ln -s stp/install/Dockerfile.dev Dockerfile
```

### Install Docker

Next step is to install Docker:
```bash
$ sudo apt-get install docker.io
```

Add yourself to the docker group:
```bash
$ sudo gpasswd -a <your_user_name> docker
```

Log out and log in for group change to take effect


**Change docker location (optional)**

Change docker image location.

Stop docker service:
```bash
sudo service docker stop
```

Edit `/etc/defaults/docker` file and add the following option:
```bash
DOCKER_OPTS="-g /home/docker"
```

Create new docker location:
```bash
sudo mkdir /home/docker
```

Restart the docker service:
```bash
sudo service docker start
```

### Create databases

Use the database creation tools in `./app_server/tools/` to create the various databases.  

Setup authentication databases using `./app_server/tools/authdb.py`. We assume that the user is creating these databases in `~/stp`.

```bash
$ mkdir ~/stp
$ ./app_server/tools/authdb.py --rootpass ROOT_PASSWORD ~/stp/admin.db
$ ./app_server/tools/authdb.py ~/stp/auth.db
```
Setup project databases using `./app_server/tools/projectdb.py`

```bash
$ ./app_server/tools/projectsdb.py ~/stp/projects.db
```

### Build docker image

Build the application server Docker image. For more instructions see `./install/README.md`. A developmental version is also avaliable: see `./install/README.dev.md`

## Testing

Testing tools are located in `./app_server/tools/`:

 * project_tester.py - Project interface tester
 * editor_tester.py - Editor interface tester

For more information see `./app_server/tools/README.md`
