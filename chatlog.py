#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Library modules
import codecs
import re
import watchdog.events
import watchdog.observers


class FMLLogHandler(watchdog.events.PatternMatchingEventHandler):
    """
    The FMLLogHandler class inherits the PatternMatchingEventHandler class
    from the watchdog package. When the Minecraft server moves the
    ForgeModLoader-server-0.log file to ForgeModLoader-server-1.log during
    startup, this class will handle the event by extracting all chat logs from
    the file and saving them in chatlog.txt.
    """

    def __init__(self, config):        
        # Save config dictionary as an instance variable
        self.config = config   

        # Call constructor from parent class
        super(FMLLogHandler, self).__init__(
            # Files matching these patterns will be monitored for events
            patterns=[self.config['SERVER_PATH'] + '/ForgeModLoader-server-0.log']
        )

        # Compile commonly used regular expressions
        self.colourRegEx = re.compile(u"""
            \x1b        # UTF-8 character code point at start of colour code
            .+?         # Match any characters apart from newline non-greedily
            m           # Colour codes always terminate with m
            """,
            re.VERBOSE)

        self.chatRegEx = re.compile(ur"""
           # Capture the date and time of message
           (?P<date>\d\d\d\d-\d\d-\d\d\ \d\d\:\d\d\:\d\d)

           # Capture the user name and prefix of the user
           # (?:...) syntax for a non-capturing group, useful with the | operator
           # A|B match either regex A or regex B
           # .+? will match any characters apart from newline non-greedily
           \ \[INFO\]\ \[(?:MyTown|Dynmap)\]\ (?P<username>.+?\:)

           # Capture the chat message
           \ (?P<message>.+)""",
           re.VERBOSE)

        self.broadcastRegEx = re.compile(ur'(?P<date>\d\d\d\d-\d\d-\d\d \d\d\:\d\d\:\d\d)'
                                         + ur' \[INFO\] \[Minecraft\-Server\] \[Server\]'
                                         + ur' (?P<message>.+)')

    def on_moved(self, event):
        """
        event.event_type
            'modified' | 'created' | 'moved' | 'deleted'
        event.is_directory
            True | False
        event.src_path
            path/to/observed/file
        event.dest_path
            new file path after move operation
        """

        if event.dest_path == self.config['SERVER_PATH'] + '/ForgeModLoader-server-1.log':

            with codecs.open(self.config['SERVER_PATH'] + '/chatlog.txt',
                             'a', encoding='utf-8') as chatLog:

                with codecs.open(self.config['SERVER_PATH'] + '/ForgeModLoader-server-1.log',
                                 'r', encoding='utf-8') as fmlLog:

                    fmlLine = fmlLog.readline()

                    if fmlLine:
                        # Find the date and time from the first log entry

                        match = re.match(ur'(\d\d\d\d-\d\d-\d\d \d\d\:\d\d\:\d\d)',
                                         fmlLine)

                        if match:
                            # The first line appended to chatlog.txt should announce that the server is starting
                            # *^60 means 60 character wide column, with center aligned text, padded with asterisc
                            # characters

                            chatLog.write(u'''\n{date} {message:*^60}\n'''.format(
                                    date=match.group(0),
                                    message=u'Starting Minecraft server'
                                )
                            )

                            # Continue parsing fmlLog until we meet end of file

                            fmlLine = fmlLog.readline()

                            while fmlLine:
                                # Remove colour codes from FMLLine
                                fmlLine = self.colourRegEx.sub(u'', fmlLine)

                                # Attempt to match MyTown or Dynmap chat entry
                                match = self.chatRegEx.match(fmlLine)

                                if match:

                                    # Use string formatting to create a username and prefix column,
                                    # 30 characters wide with right hand text alignment
                                    chatLog.write(u'{date} {username:>30} {message}\n'.format(
                                            date=match.group('date'),
                                            username=match.group('username'),
                                            message=match.group('message')
                                        )
                                    )

                                    fmlLine = fmlLog.readline()
                                    continue

                                # Attempt to match console broadcast
                                match = self.broadcastRegEx.match(fmlLine)

                                if match:
                                    chatLog.write(u'{date} {username:>30} {message}\n'.format(
                                            date=match.group('date'),
                                            username=u'[Server]',
                                            message=match.group('message')
                                        )
                                    )

                                fmlLine = fmlLog.readline()


class FMLLogObserver(watchdog.observers.Observer):
    """
    Observe the file system, and call the FmlLogHandler methods to handle the event when the Minecraft
    logs are rolled.
    """

    def __init__(self, config):
        """
        Configure the observer so that all the main execution module needs to do is call this class's start()
        method to launch the observer in a new thread.
        """

        # We are overriding the constructor of an inherited class, so it's probably a good idea to call the
        # parent's constructor method first!
        super(FMLLogObserver, self).__init__()

        # Instantiate the FmlLogHandler class
        fmlLogHandler = FMLLogHandler(config)

        # Pass the fmlLogHandler instance to this observer, and restrict the observer to just watch
        # the server path.
        self.schedule(fmlLogHandler, config['SERVER_PATH'])
