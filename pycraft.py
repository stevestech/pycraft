#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
A Minecraft server wrapper which can monitor and maintain multiple Minecraft server processes.
Each server has its own configuration options which are defined in config.py.
"""

# Library modules
import logging
import signal
import sys

# Project modules
import chatlog
import config
import server
import stdinListener

# Authorship information
__author__ = "Francis Baster"
__license__ = "GPL"
__version__ = "0.2"
__maintainer__ = "Francis Baster"
__email__ = "francisbaster@gmail.com"
__status__ = "Development"


class Pycraft:
    """    
    Used to encapsulate unbound members, and provides functions to initialise, run
    and stop Pycraft. All functions and members are unbound / static, this class is not meant
    to be instantiated.
    """

    def __init__(self):

        # A list to contain instances of the server.Server class
        self.serverInstances = []

        # A list to contain instances of the chatlog.FMLLogObserver class
        self.observerInstances = []

        # The instance of the stdinListener thread.
        self.stdinListenerThread = None

        # Register Pycraft.stop() as the function to call when the OS sends any of
        # the following signals
        logging.debug('Registering signal handlers.')

        for sig in [signal.SIGTERM, signal.SIGINT, signal.SIGHUP, signal.SIGQUIT]:
            signal.signal(sig, self.stop)


        # Add new instances of the server.Server class to the serverInstances list, and initialise
        # them with the corresponding config dictionary.

        for configDict in config.config:
            self.serverInstances.append(
                server.Server(configDict)
            )


        # For each server that is configured to have a chatlog, instantiate a FMLLogObserver
        # class to monitor that server's log file and extract the chat entries to a chatlog.

        for s in self.serverInstances:
            if s.getConfig('ENABLE_CHATLOG'):
                self.observerInstances.append(
                    chatlog.FMLLogObserver(
                        s.getConfig('SERVER_NICK'),
                        s.getConfig('SERVER_PATH')
                    )
                )


        logging.debug('Initialising stdin listener thread.')
        
        self.stdinListenerThread = stdinListener.StdinListener(
            self.serverInstances,
            __version__
        )


    def run(self):
        """
        Begin execution of the server wrapper
        """

        # Tell any chatlog observers to begin running in their seperate threads.
        for o in self.observerInstances:
            logging.debug(str.format('Starting FMLLogObserver for {} server.', o.SERVER_NICK))
            o.start()

        self.stdinListenerThread.start()

        # Main thread will now call the run method in server.Server.scheduler, which will
        # perform server check and server restart events as scheduled, and will call time.sleep
        # between events.
        server.Server.run()


    def stop(self, signum=None, frame=None):
        """
        Handles any signals sent from the OS which indicate that this program
        should exit.
        """

        logging.info('Pycraft is stopping.')

        # Stop any FMLLogObserver threads that may be running,
        # then wait for them to finish.
        for o in self.observerInstances:
            o.stop()

        self.stdinListenerThread.stop()


        for o in self.observerInstances:
            o.join()

        self.stdinListenerThread.join()


        sys.exit(0)


# Only execute if this is the main module.
# Don't configure the logger or begin execution if this module was imported.
if __name__ == "__main__":
    logging.basicConfig(
        format='%(asctime)s %(levelname)s %(message)s',
        filename='pycraft.log',
        level=logging.INFO
    )

    p = Pycraft()
    p.run()
