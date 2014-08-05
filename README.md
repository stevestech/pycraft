pycraft
=======

Description
-----------
A Minecraft server wrapper which can monitor and maintain multiple Minecraft server processes.
Each server has its own configuration options which are defined in config.py.

Features
--------
*   Automated restarts, preceded by warning broadcasts to the players.
*   Server processes are monitored to ensure that each running server has one corresponding
    system process.
*   Server network monitoring to ensure that each online server is responding to network
    requests. Any server deadlock will be detected, and a restart will be issued.
*   Server restarts will attempt to stop the server gracefully at first, however a SIGKILL
    signal will be sent to the process if it does not terminate within 60 seconds.
*   Can start each screen session in multiuser mode, with a custom list of authorised users
    for each server.

System requirements
-------------------
UNIX-like operating system with the following executables on the system path:
*   python
*   screen

Required third-party Python modules
-----------------------------------
[psutil](https://pypi.python.org/pypi/psutil)  
[watchdog](https://pypi.python.org/pypi/watchdog)
    