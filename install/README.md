BUILDING AN APPLICATION SERVER DOCKER IMAGE
===========================================

This directory contains the files necessary to build a Docker image. To build place the `Dockerfile` and complete repository in a subdirectory called `stp` in a build location with structure as follows:

```
.
|-- Dockerfile
`-- stp
    |-- app_server
    |   |-- config
    |   |-- logging
    |   `-- service
    `-- install
```

and run:

```bash
docker build -t stp_base .
```

to run the services we need to mount the location where persistent files (such as auth databases) are stored on the host filesystem, e.g. to use the host location `~/stp` to test the system:

```bash
docker run --name stp -v ~/stp:/mnt/stp -d -p 9999:80 stp_base:latest
```
