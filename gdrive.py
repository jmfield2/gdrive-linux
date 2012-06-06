#!/usr/bin/env python
#
# Copyright 2012 Jim Lawton. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import sys
import optparse
import pprint

import gdocs
from drived import DriveDaemon

session = None
commands = {}
aliases = {}

def command(func):
    if not func.__doc__:
        sys.exit("Error: commands must have formatted docstrings!")
    commands[func.func_name] = func
    func_aliases = [alias for alias in aliases.iterkeys() if aliases[alias].func_name == func.func_name]
    if func_aliases:
        func.__doc__ += "Aliases: %s" % ",".join(func_aliases)
    return func

def alias(name):
    def decorator(func):
        if name in commands:
            sys.exit("Error, this alias has the same name as a command!")
        aliases[name] = func
        return func
    return decorator

@command
def help(argv):
    """Print help message.
gdrive help [COMMAND]

If no argument is specified, print a list of commands with a short description of each. If a command is specified, print help on that command.
"""
    if not argv:
        return usage()
    for cmd in commands:
        if cmd == argv[0]:
            print commands[cmd].__doc__.split('\n', 1)[1]
            return
    print >>sys.stderr, "Unknown command '%s'" % argv[0]

def usage():
    "Print usage."
    print "Google Drive command-line interface"
    print
    print "Commands:"
    print
    print "Note: use gdrive help <command> to view usage for a specific command."
    print
    lines = []
    cmdlist = commands.keys()
    cmdlist.sort()
    for cmd in cmdlist:
        lines.append((cmd, commands[cmd].__doc__.splitlines()[0]))
    space = max(len(line[0]) + 3 for line in lines)
    for line in lines:
        print " %-*s%s" % (space, line[0], line[1])
    print

@command
def start(argv):
    """Start GDrive daemon.
gdrive start

Starts the GDrive daemon, gdrived, if it is not already running.

"""
    daemon = DriveDaemon()
    daemon.start()

@command
def stop(argv):
    """Stop GDrive daemon.
gdrive stop

Stops the GDrive daemon, gdrived, if it is running.

"""
    daemon = DriveDaemon()
    daemon.stop()

@command
def status(argv):
    """Show the status of the GDrive daemon.
gdrive status

Shows the status of the GDrive daemon.

"""
    daemon = DriveDaemon()
    print daemon.status()

@command
def restart(argv):
    """Restart GDrive daemon.
gdrive restart

Restarts the GDrive daemon, gdrived.

"""
    daemon = DriveDaemon()
    daemon.restart()

@command
@alias("ls")
def list(argv):
    """List folder contents.
gdrive list <path>

Lists the contents of the specified path. If no path is specified, then the root folder is assumed.

"""
    if len(argv) == 0:
        root = '/'
    else:
        root = argv[0]
    folders, files = session.readFolder(root)
    for path in folders:
        print path
    for path in files:
        print path, session.getFileSize(path)

@command
@alias("up")
def update(argv):
    """Update a folder.
gdrive update <path>

Update the contents of the specified path, recursively. If no path is specified, then the entire GDrive will be updated.

"""
    if len(argv) == 0:
        path = '/'
    else:
        path = argv[0]
    session.update(path)

@command
def sync(argv):
    """Synchronise a folder.
gdrive sync <path>

Synchronise the contents of the specified path, recursively. If no path is specified, then the entire GDrive will be synchronised.
This command will create a local copy of the specified folder tree, or if it exists already, will update it to match the server contents..
"""
    if len(argv) == 0:
        path = '/'
    else:
        path = argv[0]
    #session.sync(path)
    sys.exit("Not implemented!")

@command
@alias("get")
def download(argv):
    """Download a file or folder.
gdrive download [<path> [<localpath>]]

Download the contents of the specified path, recursively. If no path is specified, then the entire GDrive will be downloaded.
This command will create a local copy of the specified file or folder tree, or if it exists already, will update it to match 
the server contents. If a local path is specified, then the file or folder will be downloaded at that path. If no localpath 
is specified, then the "localstore"/"path" configuration option will be used. 
"""
    localpath = None
    if len(argv) == 0:
        path = '/'
    else:
        path = argv[0]
        if len(argv) > 1:
            localpath = argv[1]
    session.download(path, localpath)

@command
@alias("put")
def upload(argv):
    """Upload a file or folder.
gdrive upload <localpath> [<path>]

Upload the contents of the specified path, recursively. A local path must be specified.
This command will create a server copy of the specified file or folder tree, or if it exists already on the server, will update 
it to match the local contents. If a remote path is specified, then the file or folder will be uploaded at that path relative to 
the root of the server tree.  
"""
    path = None
    if len(argv) == 0:
        return usage()
    else:
        localpath = argv[0]
        if len(argv) > 1:
            path = argv[1]
    session.upload(localpath, path)

@command
def reset(argv):
    """Reset GDrive cached metadata.
gdrive reset

This command clears cached GDrive metadata and recreates it by querying the server.
"""
    session.reset()

@command
def dump(argv):
    """Dump GDrive cached metadata.
gdrive dump

This command dumps cached GDrive metadata.
"""
    session.dump()

@command
def info(argv):
    """Print general information.
gdrive info

Prints out general information, e.g. total number of files/folders, quotas used, etc.

"""
    pprint.pprint(session.getInfo())

def _parseArgs():
    "Parse command-line arguments."
    helpStr = """
%prog [options] 

Utility to access Google Drive.

"""
    parser = optparse.OptionParser(description=helpStr)
    parser.add_option('-v', '--verbose', dest='verbose', action='store_true', default=False,                   help='Turn on extra logging')
    parser.add_option('-d', '--debug',   dest='debug',   action='store_true', default=False,                   help='Turn on debug logging')
    (options, args) = parser.parse_args()
    return (options, args)


def main(argv):
    "Main function."

    (opts, args) = _parseArgs()

    cmdfound = False
    i = 0
    for i in range(len(args)):
        if args[i] in commands or args[i] in aliases:
            cmdfound = True
            break
    
    if not cmdfound:
        usage()
        return None

    global session
    session = gdocs.Session(verbose=opts.verbose, debug=opts.debug)
    if session == None:
        sys.exit("Error, could not create Google Docs session!")

    res = None
    if args[i] in commands:
        res = commands[args[i]](args[i+1:])
    elif args[i] in aliases:
        res = aliases[args[i]](args[i+1:])

    return res


if __name__ == "__main__":
    result = main(sys.argv)
    if result != None:
        sys.exit(result)
