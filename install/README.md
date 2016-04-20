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
