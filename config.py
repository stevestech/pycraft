#!/usr/bin/env python
# -*- coding: utf-8 -*-

# This server wrapper can monitor multiple servers. Each server must have a unique nick and a unique jar name.
# The config variable is a list of all the servers to be monitored. The list contains dictionaries.
# Each dictionary contains a complete set of configuration options for one particular server.

config = [
    {
        # General
        'SERVER_NICK': 'test',                                       # Nickname, must be unique to the server being monitored. Used to name the screen session.
        'SERVER_PATH': '/home/minecraft/test',                       # Where the server files are located
        'SERVER_JAR': 'test-server.jar',                             # Name of the server jar file, must be unique to the server being monitored. Used to identify server process.
        'START_SCRIPT': 'ServerStart.sh',                            # Script with Java parameters used to launch the server
        
        # Modules
        'ENABLE_CHATLOG': True,                                      # Extract chat entries from ForgeModLoader-server-0.log and record into a chatlog file (Forge servers only)
        'ENABLE_RESPONSIVENESS_CHECK': True,                         # Request the server MOTD at 60 second intervals, restart if server unresponsive.
        'ENABLE_AUTOMATED_RESTARTS': True,
        
        # Wrapper
        'START_SERVER': True,                                        # If set to True, starting mc-daemon will launch the server automatically.
        'MULTIUSER_ENABLED': True,                                   # Should screen session be configured to use multiuser mode.
        'AUTHORISED_ACCOUNTS': [
            'anedaar',
            'JeRoNiMoKaNT'
        ],                                                           # List of user accounts which will receive permission to access the multiuser screen session containing the server console.

        # Responsiveness module
        'HOSTNAME': 'localhost',                                     # The hostname (URL or IP address) of the server to be monitored. Use localhost or 127.0.0.1 for servers on this machine.
        'PORT': 25595,                                               # The port of the server to be monitored. By default 25565.
        'STARTUP_TIME': 30,                                          # Number of seconds to wait before checking server responsiveness.

        # Restart module
        'RESTART_TIME': 2*60                                         # Number of seconds to wait before restarting Minecraft server
    },

    {
        'SERVER_NICK': 'skies',
        'SERVER_PATH': '/home/minecraft/skies',
        'SERVER_JAR': 'skies-server.jar',
        'START_SCRIPT': 'ServerStart.sh',

        'ENABLE_CHATLOG': False,
        'ENABLE_RESPONSIVENESS_CHECK': True,
        'ENABLE_AUTOMATED_RESTARTS': True,

        'START_SERVER': False,

        'HOSTNAME': 'localhost',
        'PORT': 25575,
        'STARTUP_TIME': 120,

        'RESTART_TIME': 12 * 60 * 60
    }
]
