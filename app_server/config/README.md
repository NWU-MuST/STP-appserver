# Application server configuration

Server modules are configured using JSON configuration files.
Most of the default configurations should work without having to edit the contents as they are contained in the docker image.

## Speech server login credentials

During the speech server build and install, you have to add an application server user to the speech server. The `username` and `password` that was entered must be included in `dispatcher.conf` file. You should make changes to the username and password configuration variables found at the bottom of the configuration file:

```
    "speechserver" : {
        "username" : USERNAME,
        "password" : PASSWORD,
        "login" : "jobs/login",
        "logout" : "jobs/logout",
        "logout2": "jobs/logout2",
        "discover" : "jobs/discover"
    }
```
