#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Library modules
import logging
import sched
import socket
import subprocess
import threading
import time

# Third party modules
import psutil


class Server:
    """
    An object used to monitor and interact with a Minecraft server.

    Constructor:
        __init__(config)

    Public methods:
        getConfig(key)
        getTargetState()    
        getUptime()
        isOnline()
        isResponsive()
        restart()    
        run() [static]
        sendCommand(command)
        start()        
        stop()

    Methods prefixed with _ are private methods, and should not be called externally.
    """

    # Unbound variable containing an instance of the sched.scheduler
    # class, used to schedule restart and server check events across all servers.
    scheduler = sched.scheduler(
        time.time,
        time.sleep
    )


    @staticmethod
    def run():
        """
        Static method which hands execution over to the scheduler.
        scheduler will run server restart and server check events as scheduled, and will
        run time.sleep in between events.
        """

        logging.info('Running scheduler.')

        Server.scheduler.run()


    @staticmethod
    def _executeInShell(command):
        """
        This will execute 'command' in the system shell, and will pipe stdout and stderr
        to the logging module.
        """

        logging.info(
            'Executing the following command in system shell:\n{COMMAND}'.format(
                COMMAND=command
            )
        )

        p = subprocess.Popen(
            args=[command],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True
        )

        # Will block until process terminates.
        stdout, stderr = p.communicate()

        if stdout:
            logging.info(
                'STDOUT:\n{STDOUT}'.format(
                    STDOUT=stdout
                )
            )

        if stderr:
            logging.info(
                'STDERR:\n{STDERR}'.format(
                    STDERR=stderr
                )
            )


    def __init__(self, config):
        """
        Constructor to initialise the Server class.
        """

        # self.lock is used to protect member variables, and also server methods
        # which read or write to these members. Such methods could be called by stdin or
        # network handler threads.
        # It is a reentrant lock, and can be acquired multiple times by the same thread.
        self._lock = threading.RLock()
        
        # Acquires lock and automatically releases it under any circumstance where execution moves
        # on from this block of code.
        with self._lock:
            logging.info(
                'Initialising {SERVER_NICK} server.'.format(
                    SERVER_NICK=config['SERVER_NICK']
                )
            )

            # A dictionary containing all configuration options for this server.
            self._config = config

            # The desired state of the server, True | False
            self._online = self._config['START_SERVER']

            # If server is currently online, and START_SERVER set to False, set self._online
            # to True not False. Prevents unnecessary server shutdown.
            if not self._config['START_SERVER'] and self.isOnline():
                self._online = True

            # This list holds all future restart events. Used for event cancellations.
            self._restartEvents = []

            # Schedule initial restart and server check events.
            self._scheduleCheck(immediate=True)
            self._scheduleRestarts()


    def getConfig(self, key):
        """
        Allow external modules to retrieve server configuration values.
        """

        return self._config.get(key)


    def getTargetState(self):
        """
        Allow external modules to see if the server is meant to be online
        or offline.
        """

        return self._online


    def sendCommand(self, command):
        """
        Execute a server command by calling the stuff command on the screen session
        which contains the Minecraft server console.
        """

        with self._lock:
            logging.info(
                'Sending the following command to {SERVER_NICK} server:\n{COMMAND}'.format(
                    SERVER_NICK=self._config['SERVER_NICK'],
                    COMMAND=command
                )
            )

            # Stuffing commands into a screen session too quickly is a bad idea.
            time.sleep(1)

            # Send stuff command to screen session. Screen session is named with server nick.
            # \r simulates the return key and causes the command to be executed.
            Server._executeInShell(
                'screen -p 0 -S '
                + self._config['SERVER_NICK']
                + ' -X stuff "\r'
                + command
                + '\r"',
            )


    def _getPIDs(self):
        """
        Returns a list of integers containing the PIDs of each Java Runtime Environment currently
        executing the server jar-file
        """

        with self._lock:    
            try:
                pgrep_output = subprocess.check_output(
                    'pgrep -f ' + self._config['SERVER_JAR'],
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

        return len(self._getPIDs()) > 0


    def getUptime(self):
        """
        Returns the number of seconds for which this server has been running
        """

        serverPIDs = self._getPIDs()

        if not self._online or len(serverPIDs) == 0:
            return None

        else:
            process = psutil.Process(serverPIDs[0])
            return time.time() - process.create_time


    def _scheduleCheck(self, immediate=False):
        """
        Enter an event in the server scheduler that will call this server's
        self._check() method.
        """

        with self._lock:
            logging.debug(
                'Scheduling a server check for {SERVER_NICK}. Immediate: {IMMEDIATE}.'.format(
                    SERVER_NICK=self._config['SERVER_NICK'],
                    IMMEDIATE=immediate
                )
            )

            if immediate:
                # Schedule an immediate server check
                Server.scheduler.enter(
                    0,
                    1,
                    self._check,
                    ()
                )

            else:
                # Schedule a server check in 60 seconds
                Server.scheduler.enter(
                    60,
                    1,
                    self._check,
                    ()
                )


    def _scheduleRestarts(self):
        """
        If the server has automated restarts enabled in config,
        then enter the future restart events in the server scheduler. These
        events include warnings that are announced to the players in the
        leadup to the restart, and the restart itself.
        """

        with self._lock:
            # Only schedule restarts if all conditions met:
            # Restarts are enabled in config for this server,
            # Restarts have not already been scheduled for this server,
            # This server is in the online state.

            # NOTE: self._restartEvents will reset next time server stops / restarts
            if self._config['ENABLE_AUTOMATED_RESTARTS'] \
                    and len(self._restartEvents) == 0    \
                    and self._online:

                logging.debug(
                    'Scheduling restart and restart warnings for {SERVER_NICK} server.'.format(
                        SERVER_NICK=self._config['SERVER_NICK']
                    )
                )

                upTime = self.getUptime()

                if upTime is not None:
                    # If restart or restart warnings are already overdue during
                    # scheduling, don't restart immediately, warn the users then
                    # restart after 10 minutes.
                    if upTime >= self._config['RESTART_TIME'] - 10*60:
                        self._restartEvents.append(
                            Server.scheduler.enter(
                                0*60,                     # Execute task in 0 seconds
                                1,                        # Task has priority of 1
                                self._restartWarning,      # Call self.restartWarning(10)
                                (10,)
                            )
                        )
                        
                        self._restartEvents.append(
                            Server.scheduler.enter(
                                5*60,
                                1,
                                self._restartWarning,
                                (5,)
                            )
                        )
                        
                        self._restartEvents.append(
                            Server.scheduler.enter(
                                9*60,
                                1,
                                self._restartWarning,
                                (1,)
                            )
                        )

                        self._restartEvents.append(
                            Server.scheduler.enter(
                                10*60,
                                1,
                                self.restart,
                                ()
                            )
                        )

                    else:
                        # Schedule the restart events as planned in the configuration.
                        self._restartEvents.append(
                            Server.scheduler.enter(
                                self._config['RESTART_TIME'] - upTime - 10*60,
                                1,
                                self._restartWarning,
                                (10,)
                            )
                        )

                        self._restartEvents.append(
                            Server.scheduler.enter(
                                self._config['RESTART_TIME'] - upTime - 5*60,
                                1,
                                self._restartWarning,
                                (5,)
                            )
                        )

                        self._restartEvents.append(
                            Server.scheduler.enter(
                                self._config['RESTART_TIME'] - upTime - 1*60,
                                1,
                                self._restartWarning,
                                (1,)
                            )
                        )

                        self._restartEvents.append(
                            Server.scheduler.enter(
                                self._config['RESTART_TIME'] - upTime,
                                1,
                                self.restart,
                                ()
                            )
                        )


    def _cancelRestartEvents(self):
        """
        Cancel any future restart events from the server scheduler
        """

        with self._lock:
            logging.debug(
                'Cancelling restart events for {SERVER_NICK} server.'.format(
                    SERVER_NICK=self._config['SERVER_NICK']
                )
            )

            for event in self._restartEvents:
                try:
                    Server.scheduler.cancel(event)
                except ValueError:
                    # Event was no longer on the queue
                    pass
                
            self._restartEvents = []


    def _restartWarning(self, minutes):
        if minutes == 1:
            self.sendCommand('say An automated restart will occur in 1 minute.')

        else:
            self.sendCommand('say An automated restart will occur in ' + str(minutes) + ' minutes.')        


    def _killServer(self):
        """
        Sends a SIGKILL signal to any process that was started with a command
        containing the server jar name.

        External calls should use stop() instead.
        """

        with self._lock:
            logging.warning(
                'Sending SIGKILL signal to {SERVER_NICK} server.'.format(
                    SERVER_NICK=self._config['SERVER_NICK']
                )
            )

            Server._executeInShell(
                'pkill -SIGKILL -f '
                + self._config['SERVER_JAR'],
            )


    def _quitScreenSession(self):
        """
        Forces the screen session to quit, necessary tidyup in case user has opened new window
        inside the session causing screen not to close with the server process. This would
        otherwise interfere with the sendCommand method.
        """

        with self._lock:        
            Server._executeInShell(
                'screen -S '
                + self._config['SERVER_NICK']
                + ' -X quit',
            )


    def stop(self):
        """
        Attempt to stop server gracefully, else stop forcefully.
        """

        # TODO: throw exceptions on error

        with self._lock:
            # Don't stop if server already offline
            if self._online:

                logging.info(
                    'Stopping {SERVER_NICK} server.'.format(
                        SERVER_NICK=self._config['SERVER_NICK']
                    )
                )

                # Prevent any restart events from being executed on the stopped server
                self._cancelRestartEvents()

                self.sendCommand('stop')

                # Update state variable to indicate that the server should now be offline
                self._online = False

                # Wait 60 seconds for process to terminate
                for index in range(12):
                    time.sleep(5)

                    if not self.isOnline():

                        logging.info(
                            '{SERVER_NICK} server was closed gracefully.'.format(
                                SERVER_NICK=self._config['SERVER_NICK']
                            )
                        )

                        return

                # If process did not terminate, then stop forcefully.
                self._killServer()


            else:
                logging.warning(
                    'Attempted to stop {SERVER_NICK} server which was in offline state.'.format(
                        SERVER_NICK=self._config['SERVER_NICK']
                    )
                )

    
    def start(self):
        """
        Create a new screen session for the server and execute the server start script
        """

        # TODO: throw exception on error

        with self._lock:
            # Don't start if server already running
            if not self._online and not self.isOnline():

                logging.info(
                    'Starting {SERVER_NICK} server.'.format(
                        SERVER_NICK=self._config['SERVER_NICK']
                    )
                )

                # Just in case there is an existing screen session from a previous server
                # instance.
                self._quitScreenSession()

                Server._executeInShell(
                    'screen -d -m -S '
                    + self._config['SERVER_NICK']
                    + ' '
                    + self._config['SERVER_PATH']
                    + '/'
                    + self._config['START_SCRIPT'],
                )

                if self._config['MULTIUSER_ENABLED']:
                    Server._executeInShell(
                        'screen -S '
                        + self._config['SERVER_NICK']
                        + ' -X multiuser on',
                    )

                    for user in self._config['AUTHORISED_ACCOUNTS']:
                        Server._executeInShell(
                            'screen -S '
                            + self._config['SERVER_NICK']
                            + ' -X acladd '
                            + user,
                        )

                # Update state variable to indicate that the server should now be online
                self._online = True

                # Give OS a chance to launch the process, as scheduleRestarts requires
                # the process to be running in order to calculate the restart times.
                time.sleep(5)
                self._scheduleRestarts()


            else:
                logging.warning(
                    'Attempted to start {SERVER_NICK} server which was in online state.'.format(
                        SERVER_NICK=self._config['SERVER_NICK']
                    )
                )


    def restart(self):
        with self._lock:
            self.sendCommand('say Server is restarting, see you soon!')
            self.stop()
            self.start()


    def isResponsive(self):
        """
        Test the server responsiveness by opening a network socket and asking the server
        for its player count and message of the day.
        """

        with self._lock:
            try:
                # Set up our socket
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(10)
                s.connect((self._config['HOSTNAME'], self._config['PORT']))

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
                logging.debug(
                    'Network responsiveness test for {SERVER_NICK} returning False.'.format(
                        SERVER_NICK=self._config['SERVER_NICK']
                    )
                )

                return False

            else:
                logging.debug(
                    'Network responsiveness test for {SERVER_NICK} returning True.'.format(
                        SERVER_NICK=self._config['SERVER_NICK']
                    )
                )

                return True


    def _check(self):
        """
        Compare the desired state with the actual state of the server,
        and take action as necessary.
        """

        with self._lock:
            logging.debug(
                'Beginning server check of {SERVER_NICK} server.'.format(
                    SERVER_NICK=self._config['SERVER_NICK']
                )
            )

            # List of process IDs of Java Runtime Environment processes currently
            # executing the Minecraft server.
            # len(serverPIDs) gives the number of processes currently running.
            serverPIDs = self._getPIDs()

            while len(serverPIDs) > 1:
                # Multiple instances of this server are running simultaneously. Kill the ones
                # most recently started, leaving one remaining.

                logging.warning(
                    'Multiple instances of {SERVER_NICK} server are running simultaneously.'.format(
                        SERVER_NICK=self._config['SERVER_NICK']
                    )
                    + ' Number of processes found: {NUM_PROCESSES}'.format(
                        NUM_PROCESSES=len(serverPIDs)
                    )
                )


                newestProcess = psutil.Process(serverPIDs[0])

                for p in serverPIDs:                
                    process = psutil.Process(p)

                    if process.create_time > newestProcess.create_time:
                        newestProcess = process


                logging.warning(
                    'Terminating process number {PID}, an instance of {SERVER_NICK} server.'.format(
                        PID=newestProcess.pid,
                        SERVER_NICK=self._config['SERVER_NICK']
                    )
                    + ' Process was originally started with the following command:\n{START_COMMAND}'.format(
                        START_COMMAND=newestProcess.cmdline()
                    )
                )

                newestProcess.terminate()

                for index in range(30):
                    time.sleep(1)

                    if not newestProcess.is_running():
                        break


                if newestProcess.is_running():
                    newestProcess.kill()

                time.sleep(5)
                serverPIDs = self._getPIDs()


            if self._online:
                # Minecraft server should currently be online and responsive

                if len(serverPIDs) == 0:
                    logging.debug(
                        '{SERVER_NICK} server is desired to be online, but no process was found.'.format(
                            SERVER_NICK=self._config['SERVER_NICK']
                        )
                        + ' Server will now be started.'
                    )

                    self.start()

                elif len(serverPIDs) == 1:
                    logging.debug(
                        '{SERVER_NICK} server is desired to be online, and is currently running.'.format(
                            SERVER_NICK=self._config['SERVER_NICK']
                        )
                    )

                    if self._config['ENABLE_RESPONSIVENESS_CHECK']:
                        upTime = self.getUptime()

                        # Perform a responsiveness test if the server has been online for long
                        # enough.
                        if upTime > self._config['STARTUP_TIME']:

                            if not self.isResponsive():
                                # Server has failed responsiveness test, repeat test up to 10 more times
                                # and if test fails at least 3 times, restart the server

                                prevResults = []

                                for index in range(10):
                                    time.sleep(5)
                                    prevResults.append(self.isResponsive())

                                    if prevResults.count(False) >= 3:
                                        logging.warning(
                                            '{SERVER_NICK} server has failed three network'.format(
                                                SERVER_NICK=self._config['SERVER_NICK']
                                            )
                                            + ' responsiveness tests, and will now be restarted.'
                                        )

                                        self.restart()
                                        break            

            else:
                # Minecraft server should be offline
                if len(serverPIDs) > 0:
                    logging.debug(
                        '{SERVER_NICK} server is desired to be offline, but instances of this'.format(
                            SERVER_NICK=self._config['SERVER_NICK']
                        )
                        + ' server are currently running. Server will now be stopped.'
                    )

                    self.stop()

                else:
                    logging.debug(
                        '{SERVER_NICK} server is desired to be offline, and no instances of the'.format(
                            SERVER_NICK=self._config['SERVER_NICK']
                        )
                        + ' server are currently running.'
                    )


            # Tell the scheduler to call the self.check method again in 60 seconds
            self._scheduleCheck()
