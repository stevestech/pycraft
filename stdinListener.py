# WARNING: This module will only work on UNIX systems.
# Need a method to read stdin without blocking on Windows.


# Library modules
import threading
import select
import signal
import sys

# Third-party modules
import psutil


class StdinListener(threading.Thread):

    def __init__(self, serverInstances, version):
        super(StdinListener, self).__init__(name="Thread-PycraftStdinListener")

        self.daemon = False
        self.serverInstances = serverInstances
        self.stopping = False
        self.version = version


    def displayHelp(self, command=None):
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
            print("Welcome to Pycraft version " + self.version + ". Available pycraft commands:")
            print("\texit")
            print("\thelp\t[command]")
            print("\tlist")
            print("\trestart\t<serverNick>")
            print("\tstart\t<serverNick>")
            print("\tstatus\t<serverNick>")
            print("\tstop\t<serverNick>")        


    def getServerInstance(self, serverNick):
        for s in self.serverInstances:
            if s.getConfig("SERVER_NICK") == serverNick:
                return s

        print("Server {} was not found in the Pycraft configuration file.".format(serverNick))
        print("Please use the \"list\" command to see the list of currently configured")
        print("servers.")

        return None            


    def run(self):
        self.displayHelp()
        sys.stdout.write("\npycraft> ")
        sys.stdout.flush()

        while not self.stopping:   
            # NON-PORTABLE CODE: UNIX ONLY
            # (Couldn't find a Windows alternative to select for stdin)

            # Check if stdin has data to be read, otherwise timeout after 1 second.
            # Non-blocking behaviour allows this thread to be terminated from another
            # thread, which allows pycraft to be exited cleanly.

            if select.select([sys.stdin], [], [], 1) == ([sys.stdin], [], []):

                # Yes, stdin does have data                
                command = sys.stdin.readline()
                commandList = command.split()

                # Empty command given by user
                if len(commandList) == 0:
                    self.displayHelp()

                else:
                    commandList[0] = commandList[0].lower()


                    if commandList[0] == "exit":
                        # Send SIGTERM to this process, terminating the main thread.
                        process = psutil.Process()
                        process.send_signal(signal.SIGTERM)
                        self.stopping = True
                        continue


                    elif commandList[0] == "help":
                        if len(commandList) == 1:
                            self.displayHelp()
                            continue

                        else:
                            self.displayHelp(commandList[1].lower())


                    elif commandList[0] == "list":
                        print("Pycraft has been configured to monitor the following servers:")

                        for s in self.serverInstances:
                            print("\t" + s.getConfig('SERVER_NICK'))


                    elif commandList[0] == "restart":
                        if len(commandList) != 2:
                            self.displayHelp("restart")

                        else:
                            s = self.getServerInstance(commandList[1])

                            if s is not None:
                                s.restart()


                    elif commandList[0] == "start":
                        if len(commandList) != 2:
                            self.displayHelp("start")

                        else:
                            s = self.getServerInstance(commandList[1])

                            if s is not None:
                                s.start()

                                # TODO catch exceptions


                    elif commandList[0] == "status":
                        if len(commandList) != 2:
                            self.displayHelp("status")

                        else:
                            s = self.getServerInstance(commandList[1])

                            if s is not None:
                                print("Current status of server:\t{}".format(s.getConfig("SERVER_NICK")))
                                
                                if s.getTargetState():
                                    print("Target state:\tonline")
                                else:
                                    print("Target state:\toffline")

                                print("Is online:\t{}".format(s.isOnline()))
                                print("Is responsive:\t{}".format(s.isResponsive()))


                    elif commandList[0] == "stop":
                        if len(commandList) != 2:
                            self.displayHelp("stop")

                        else:
                            s = self.getServerInstance(commandList[1])

                            if s is not None:
                                s.stop()

                                # TODO catch exceptions


                    else:
                        # Unrecognised command
                        self.displayHelp()

                sys.stdout.write("\npycraft> ")
                sys.stdout.flush()


    def stop(self):
        self.stopping = True
