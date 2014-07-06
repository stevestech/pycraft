#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Library modules
import sched
import socket
import subprocess
import time

# Third party modules
import psutil


class Server:
    # Class / static variable containing an instance of the sched.scheduler
    # class, used to schedule restart and server check events across all servers.
    serverScheduler = sched.scheduler(
        time.time,
        time.sleep
    )


    def __init__(self, config):
        """
        Constructor to initialise the Server class.
        """

        # A dictionary containing all configuration options for this server
        self.config = config

        # The desired state of the server, True | False
        self.online = self.config['START_SERVER']

        # If server is currently online, and START_SERVER set to False, set self.online
        # to True not False. Prevents unnecessary server shutdown.
        if not self.config['START_SERVER'] and self.isOnline():
            self.online = True

        # This list holds all future restart events. Used for event cancellations.
        self.restartEvents = []


    def sendCommand(self, command):
        """
        Execute a server command by calling the stuff command on the screen session
        which contains the Minecraft server console.
        """

        # Stuffing commands into a screen session too quickly is a bad idea.
        time.sleep(1)

        # Send stuff command to screen session. Screen session is named with server nick.
        # \r simulates the return key and causes the command to be executed.
        subprocess.call(
            'screen -p 0 -S '
            + self.config['SERVER_NICK']
            + ' -X stuff \r'
            + command
            + '\r',
            shell=True
        )        


    def getServerPIDs(self):
        """
        Returns a list of integers containing the PIDs of each Java Runtime Environment currently
        executing the server jar-file
        """
    
        try:
            pgrep_output = subprocess.check_output(
                'pgrep -f ' + self.config['SERVER_JAR'],
                shell=True
            )

        except subprocess.CalledProcessError:
            # pgrep found no matches, and returned non-zero. Return empty list.
            return []
    
        pgrep_output_list = pgrep_output.split()

        # Convert from list of strings to list of integers
        for index in range(len(pgrep_output_list)):
            pgrep_output_list[index] = int(pgrep_output_list[index])

        return pgrep_output_list


    def isOnline(self):
        """
        Returns True if any server processes are currently running.
        """

        return len(self.getServerPIDs()) > 0


    def getUptime(self):
        """
        Returns the number of seconds for which this server has been running
        """

        serverPIDs = self.getServerPIDs()

        if not self.online or len(serverPIDs) == 0:
            return None

        else:
            process = psutil.Process(serverPIDs[0])
            return time.time() - process.create_time


    def scheduleCheck(self):
        """
        Enter an event in the server scheduler that will call this server's
        self.check() method in 60 seconds.
        """

        Server.serverScheduler.enter(
            60,
            1,
            self.check,
            ()
        )


    def scheduleRestarts(self):
        """
        If the server has automated restarts enabled in config,
        then enter the future restart events in the server scheduler. These
        events include warnings that are announced to the players in the
        leadup to the restart, and the restart itself.
        """

        if self.config['ENABLE_AUTOMATED_RESTARTS']:        
            upTime = self.getUptime()

            if upTime is not None:
                # If restart or restart warnings are already overdue during
                # scheduling, don't restart immediately, warn the users then
                # restart after 10 minutes.
                if upTime >= self.config['RESTART_TIME'] - 10*60:
                    self.restartEvents.append(
                        Server.serverScheduler.enter(
                            0*60,                     # Execute task in 0 seconds
                            1,                        # Task has priority of 1
                            self.restartWarning,      # Call self.restartWarning(10)
                            (10,)
                        )
                    )
                    
                    self.restartEvents.append(
                        Server.serverScheduler.enter(
                            5*60,
                            1,
                            self.restartWarning,
                            (5,)
                        )
                    )
                    
                    self.restartEvents.append(
                        Server.serverScheduler.enter(
                            9*60,
                            1,
                            self.restartWarning,
                            (1,)
                        )
                    )

                    self.restartEvents.append(
                        Server.serverScheduler.enter(
                            10*60,
                            1,
                            self.restart,
                            ()
                        )
                    )

                else:
                    # Schedule the restart events as planned in the configuration.
                    self.restartEvents.append(
                        Server.serverScheduler.enter(
                            self.config['RESTART_TIME'] - upTime - 10*60,
                            1,
                            self.restartWarning,
                            (10,)
                        )
                    )

                    self.restartEvents.append(
                        Server.serverScheduler.enter(
                            self.config['RESTART_TIME'] - upTime - 5*60,
                            1,
                            self.restartWarning,
                            (5,)
                        )
                    )

                    self.restartEvents.append(
                        Server.serverScheduler.enter(
                            self.config['RESTART_TIME'] - upTime - 1*60,
                            1,
                            self.restartWarning,
                            (1,)
                        )
                    )

                    self.restartEvents.append(
                        Server.serverScheduler.enter(
                            self.config['RESTART_TIME'] - upTime,
                            1,
                            self.restart,
                            ()
                        )
                    )


    def cancelRestartEvents(self):
        """
        Cancel any future restart events from the server scheduler
        """

        for event in self.restartEvents:
            try:
                Server.serverScheduler.cancel(event)
            except ValueError:
                # Event was no longer on the queue
                pass
            
        self.restartEvents = []


    def restartWarning(self, minutes):
        if minutes == 1:
            self.sendCommand('say An automated restart will occur in 1 minute.')

        else:
            self.sendCommand('say An automated restart will occur in ' + str(minutes) + ' minutes.')        


    def killServer(self):
        """
        Sends a SIGKILL signal to any process that was started with a command
        containing the server jar name.

        External calls should use stop() instead.
        """

        subprocess.call(
            'pkill -SIGKILL -f '
            + self.config['SERVER_JAR'],
            shell=True
        )


    def quitScreenSession(self):
        """
        Forces the screen session to quit, necessary tidyup in case user has opened new window
        inside the session causing screen not to close with the server process. This would
        otherwise interfere with the sendCommand method.
        """
        
        subprocess.call(
            'screen -S '
            + self.config['SERVER_NICK']
            + ' -X quit',
            shell=True
        )


    def stop(self):
        """
        Attempt to stop server gracefully, else stop forcefully.
        """

        # Prevent any restart events from being executed on the stopped server
        self.cancelRestartEvents()

        self.sendCommand('stop')

        # Update state variable to indicate that the server should now be offline
        self.online = False        

        # Wait 60 seconds for process to terminate
        for index in range(12):
            time.sleep(5)

            if not self.isOnline():
                return

        # If process did not terminate, then stop forcefully.
        self.killServer()

    
    def start(self):
        """
        Create a new screen session for the server and execute the server start script
        """        

        # Just in case there is an existing screen session from a previous server
        # instance.
        self.quitScreenSession()

        subprocess.call(
            'screen -d -m -S '
            + self.config['SERVER_NICK']
            + ' '
            + self.config['SERVER_PATH']
            + '/'
            + self.config['START_SCRIPT'],
            shell=True
        )
        
        if self.config['MULTIUSER_ENABLED']:
            subprocess.call(
                'screen -S '
                + self.config['SERVER_NICK']
                + ' -X multiuser on',
                shell=True
            )

            for user in self.config['AUTHORISED_ACCOUNTS']:
                subprocess.call(
                    'screen -S '
                    + self.config['SERVER_NICK']
                    + ' -X acladd '
                    + user,
                    shell=True
                )

        # Update state variable to indicate that the server should now be online
        self.online = True           

        # Give OS a chance to launch the process, as scheduleRestarts requires
        # the process to be running in order to calculate the restart times.
        time.sleep(5)
        self.scheduleRestarts()

        # TODO: schedule server check.


    def restart(self):
        self.sendCommand('say Server is restarting, see you soon!')
        self.stop()
        self.start()


    def isResponsive(self):
        """
        Test the server responsiveness by opening a network socket and asking the server
        for its player count and message of the day.
        """

        try:
            # Set up our socket
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(10)
            s.connect((self.config['HOSTNAME'], self.config['PORT']))

            # Send 0xFE: Server list ping
            s.send('\xfe\x01')

            # Read some data
            d = s.recv(1024)
            s.close()

            # Check we've got a 0xFF Disconnect
            assert d[0] == '\xff'

            # Remove the packet ident (0xFF) and the short containing the length of the string
            # Decode UCS-2 string
            d = d[3:].decode('utf-16be')

            #Check the first 3 characters of the string are what we expect
            assert d[:3] == u'\xa7\x31\x00'

            """
            Commented in case the returned information becomes useful:

            # Split
            d = d[3:].split('\x00')
            
            # Return a dict of values
            return {'protocol_version': int(d[0]),
                    'server_version':       d[1],
                    'motd':                 d[2],
                    'players':          int(d[3]),
                    'max_players':      int(d[4])}
            """

        except (socket.error, socket.timeout, AssertionError, IndexError):
            return False

        else:
            return True


    def check(self):
        """
        Compare the desired state with the actual state of the server,
        and take action as necessary.
        """

        # List of process IDs of Java Runtime Environment processes currently
        # executing the Minecraft server.
        # len(serverPIDs) gives the number of processes currently running.
        serverPIDs = self.getServerPIDs()    

        while len(serverPIDs) > 1:
            # Multiple instances of this server are running simultaneously. Kill the ones
            # most recently started, leaving one remaining.

            newestProcess = psutil.Process(serverPIDs[0])

            for p in serverPIDs:                
                process = psutil.Process(p)

                if process.create_time > newestProcess.create_time:
                    newestProcess = process


            newestProcess.terminate()

            for index in range(30):
                time.sleep(1)

                if not newestProcess.is_running():
                    break


            if newestProcess.is_running():
                newestProcess.kill()

            time.sleep(5)
            assert not newestProcess.is_running()
            serverPIDs = self.getServerPIDs()


        if self.online:
            # Minecraft server should currently be online and responsive

            if len(serverPIDs) == 0:                
                self.start()

            elif len(serverPIDs) == 1:
                if self.config['ENABLE_RESPONSIVENESS_CHECK']:
                    upTime = self.getUptime()

                    # Perform a responsiveness test if the server has been online for long
                    # enough.
                    if upTime > self.config['STARTUP_TIME']:

                        if not self.isResponsive():
                            # Server has failed responsiveness test, repeat test up to 10 more times
                            # and if test fails at least 3 times, restart the server

                            prevResults = []

                            for index in range(10):
                                time.sleep(5)
                                prevResults.append(self.isResponsive())

                                if prevResults.count(False) >= 3:
                                    self.restart()
                                    break            

        else:
            # Minecraft server should be offline
            if len(serverPIDs) > 0:
                self.stop()


        # Tell the scheduler to call the self.check method again in 60 seconds
        self.scheduleCheck()
