#!/usr/bin/env python
"""
A Minecraft server wrapper which can monitor and maintain multiple Minecraft server processes.
Each server has its own configuration options which are defined in config.py.

Features:
*   Automated restarts, preceded by warning broadcasts to the players.
*   Server processes are monitored to ensure that each running server has one corresponding
    system process.
*   Server network monitoring to ensure that each online server is responding to network
    requests. Any server deadlock will be detected, and a restart will be issued.
*   Server restarts will attempt to stop the server gracefully at first, however a SIGKILL
    signal will be sent to the process if it does not terminate within 60 seconds.
*   Can start each screen session in multiuser mode, with a custom list of authorised users
    for each server.
"""

# Library modules
import signal
import sys

# Project modules
import chatlog
import config
import server

# Authorship information
__author__ = "Francis Baster"
__license__ = "GPL"
__version__ = "0.1"
__maintainer__ = "Francis Baster"
__email__ = "francisbaster@gmail.com"
__status__ = "Development"


class MC_wrapper:
    # Unbound / static variables:
    # A list to contain instances of the server.Server class
    serverInstances = []

    # A list to contain instances of the chatlog.FMLLogObserver class
    observerInstances = []


    def init():
        """
        Perform initialisation tasks.
        """

        # Register MC_wrapper.stop() as the function to call when the OS sends any of
        # the following signals
        for sig in [signal.SIGTERM, signal.SIGINT, signal.SIGHUP, signal.SIGQUIT]:
            signal.signal(sig, MC_wrapper.stop)


        # Add new instances of the server.Server class to the serverInstances list, and initialise
        # them with the corresponding config dictionary.

        for configDict in config.config:
            MC_wrapper.serverInstances.append(
                server.Server(configDict)
            )


        # For each server that is configured to have a chatlog, instantiate a FMLLogObserver
        # class to monitor that server's log file and extract the chat entries to a chatlog.

        for s in MC_wrapper.serverInstances:
            if s.config['ENABLE_CHATLOG']:
                MC_wrapper.observerInstances.append(
                    chatlog.FMLLogObserver(s.config)
                )


    def run():
        """
        Begin execution of the server wrapper
        """

        # Tell any chatlog observers to begin running in their seperate threads.
        for o in MC_wrapper.observerInstances:
            o.start()


        # Schedule the first server check for each of the instantiated servers. Each time the
        # server check method completes, it will reschedule itself to run again in 60 seconds.

        for s in MC_wrapper.serverInstances:
            s.scheduleCheck()


        # Main thread will now call the run function in server.Server.serverScheduler, which will
        # perform server check and server restart events as scheduled, and will call time.sleep
        # between events.

        server.Server.serverScheduler.run()


    def stop(signum=None, frame=None):
        """
        Handles any signals sent from the OS which indicate that this program
        should exit.
        """

        # Stop any FMLLogObserver threads that may be running,
        # then wait for them to finish.
        for o in MC_wrapper.observerInstances:
            o.stop()

        for o in MC_wrapper.observerInstances:
            o.join()

        sys.exit(0)


# Don't execute if this module was imported. This must be the main module.
if __name__ == "__main__":
    MC_wrapper.init()
    MC_wrapper.run()