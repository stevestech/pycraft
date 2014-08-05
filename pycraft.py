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
import threading

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


class Pycraft:
    """    
    Used to encapsulate unbound members, and provides functions to initialise, run
    and stop Pycraft. All functions and members are unbound / static, this class is not meant
    to be instantiated.
    """

    # A list to contain instances of the server.Server class
    serverInstances = []

    # A list to contain instances of the chatlog.FMLLogObserver class
    observerInstances = []

    # The instance of the stdinListener thread.
    stdinListenerThread = None

    @staticmethod
    def init():
        """
        Perform initialisation tasks. This method is for initalising unbound members,
        so __init__ is not used.
        """

        # Register Pycraft.stop() as the function to call when the OS sends any of
        # the following signals
        logging.info('Registering signal handlers.')

        for sig in [signal.SIGTERM, signal.SIGINT, signal.SIGHUP, signal.SIGQUIT]:
            signal.signal(sig, Pycraft.stop)


        # Add new instances of the server.Server class to the serverInstances list, and initialise
        # them with the corresponding config dictionary.

        for configDict in config.config:
            Pycraft.serverInstances.append(
                server.Server(configDict)
            )


        # For each server that is configured to have a chatlog, instantiate a FMLLogObserver
        # class to monitor that server's log file and extract the chat entries to a chatlog.

        for s in Pycraft.serverInstances:
            if s.getConfig('ENABLE_CHATLOG'):
                Pycraft.observerInstances.append(
                    chatlog.FMLLogObserver(
                        s.getConfig('SERVER_NICK'),
                        s.getConfig('SERVER_PATH')
                    )
                )


        logging.info('Initialising stdin listener thread.')
        Pycraft.stdinListenerThread = StdinListener()


    @staticmethod
    def run():
        """
        Begin execution of the server wrapper
        """

        # Tell any chatlog observers to begin running in their seperate threads.
        for o in Pycraft.observerInstances:
            logging.info(
                'Starting FMLLogObserver for {SERVER_NICK} server.'.format(
                    SERVER_NICK=o.SERVER_NICK
                )
            )

            o.start()


        Pycraft.stdinListenerThread.start()


        # Main thread will now call the run method in server.Server.scheduler, which will
        # perform server check and server restart events as scheduled, and will call time.sleep
        # between events.
        server.Server.run()


    @staticmethod
    def stop(signum=None, frame=None):
        """
        Handles any signals sent from the OS which indicate that this program
        should exit.
        """

        logging.info('Pycraft is stopping.')

        # Stop any FMLLogObserver threads that may be running,
        # then wait for them to finish.
        for o in Pycraft.observerInstances:
            o.stop()

        Pycraft.stdinListenerThread.stop()


        for o in Pycraft.observerInstances:
            o.join()

        Pycraft.stdinListenerThread.join()


        sys.exit(0)


class StdinListener(threading.Thread):
    @staticmethod
    def displayHelp(command=None):
        if command == "exit":
            print("exit:")
            print("Closes the Pycraft server wrapper. Any servers that are currently being")
            print("monitored by Pycraft will remain running inside their respective screen")
            print("sessions. Pycraft can be started again at any time and monitoring of those")
            print("servers will resume.")

        elif command == "help":
            print("help [command]:")
            print("Displays a description of the specified command, or a list of all available")
            print("commands if argument is omitted.")

        elif command == "list":
            print("list:")
            print("Displays a list of all of the Minecraft servers which Pycraft has been")
            print("configured to monitor. Servers are listed using their server nicknames,")
            print("which are unique server identifiers to be used when issuing a Pycraft")
            print("command.")

        elif command == "restart":
            print("restart <serverNick>:")
            print("If the specified server is currently in the online state, this command")
            print("will stop and then start the specified Minecraft server.")

        elif command == "start":
            print("start <serverNick>:")
            print("If the specified server is currently in the offline state, this command")
            print("will switch it into the online state. This will cause the server's start")
            print("script to the started inside a screen session. Server monitoring, automated")
            print("restarts, and other actions will then be performed on the running server")
            print("according to its Pycraft configuration.")

        elif command == "status":
            print("status <serverNick>:")
            print("Shows whether the specified server process is currently running, and if that")
            print("server is responding to network requests.")
            
        elif command == "stop":
            print("stop <serverNick>:")
            print("If the specified server is currently in the online state, this command")
            print("will switch it into the offline state. Pycraft will attempt to stop the")
            print("server gracefully at first, by issuing the \"stop\" command to the")
            print("Minecraft server console. If the server process does not terminate within")
            print("60 seconds, then a SIGKILL signal will be sent to the process.")

        else:
            print("Welcome to Pycraft version " + __version__ + ". Available pycraft commands:")
            print("\texit")
            print("\thelp\t[command]")
            print("\tlist")
            print("\trestart <serverNick>")
            print("\tstart <serverNick>")
            print("\tstatus <serverNick>")
            print("\tstop <serverNick>")


    @staticmethod
    def getServerInstance(serverNick):
        for s in Pycraft.serverInstances:
            if s.getConfig("SERVER_NICK") == serverNick:
                return s

        print("Server {} was not found in the Pycraft configuration file.".format(serverNick))
        print("Please use the \"list\" command to see the list of currently configured")
        print("servers.")

        return None


    def __init__(self):
        super(StdinListener, self).__init__(name="Thread-PycraftStdinListener")
        self.stopping = False


    def stop(self):
        self.stopping = True


    def run(self):
        StdinListener.displayHelp()

        while not self.stopping:
            # Command should be in the form:
            # <serverNick> <action> [parameters]
            sys.stdout.write("\n")
            command = raw_input("pycraft> ")

            commandList = command.split()

            # Empty command given by user
            if len(commandList) == 0:
                StdinListener.displayHelp()

            else:
                commandList[0] = commandList[0].lower()


                if commandList[0] == "exit":
                    print("TODO: Exit pycraft.")
                    continue


                elif commandList[0] == "help":
                    if len(commandList) == 1:
                        StdinListener.displayHelp()
                        continue

                    else:
                        StdinListener.displayHelp(commandList[1].lower())


                elif commandList[0] == "list":
                    print("Pycraft has been configured to monitor the following servers:")

                    for s in Pycraft.serverInstances:
                        print("\t" + s.getConfig('SERVER_NICK'))


                elif commandList[0] == "restart":
                    if len(commandList) != 2:
                        StdinListener.displayHelp("restart")

                    else:
                        s = StdinListener.getServerInstance(commandList[1])

                        if s is not None:
                            s.restart()


                elif commandList[0] == "start":
                    if len(commandList) != 2:
                        StdinListener.displayHelp("start")

                    else:
                        s = StdinListener.getServerInstance(commandList[1])

                        if s is not None:
                            s.start()

                            # TODO catch exceptions


                elif commandList[0] == "status":
                    if len(commandList) != 2:
                        StdinListener.displayHelp("status")

                    else:
                        s = StdinListener.getServerInstance(commandList[1])

                        if s is not None:
                            print("Current status of server: {}".format(s.getConfig("SERVER_NICK")))
                            
                            if s.getTargetState():
                                print("Target state: online")
                            else:
                                print("Target state: offline")

                            print("Is online: {}".format(s.isOnline()))
                            print("Is responsive: {}".format(s.isResponsive()))


                elif commandList[0] == "stop":
                    if len(commandList) != 2:
                        StdinListener.displayHelp("stop")

                    else:
                        s = StdinListener.getServerInstance(commandList[1])

                        if s is not None:
                            s.stop()

                            # TODO catch exceptions


                else:
                    # Unrecognised command
                    StdinListener.displayHelp()


# Only execute if this is the main module.
# Don't configure the logger or begin execution if this module was imported.
if __name__ == "__main__":
    logging.basicConfig(
        format='%(asctime)s %(levelname)s %(message)s',
        filename='pycraft.log',
        level=logging.DEBUG
    )

    Pycraft.init()
    Pycraft.run()
