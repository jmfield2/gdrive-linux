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
import os
import time
import atexit
import logging
from signal import SIGTERM

from log import Formatter


# Based in part on code originally from:
# http://www.jejik.com/articles/2007/02/a_simple_unix_linux_daemon_in_python/

# To use, subclass the Daemon class and override the run() method.
# See http://www.erlenstar.demon.co.uk/unix/faq_2.html#SEC16 for details.

class Daemon(object):
    "A generic Unix daemon class."

    def __init__(self, pidfile, loglevel=None, logfile=None):
        self._pidfile = pidfile
        self._loglevel = loglevel
        self._stdout = None
        if logfile:
            self._stdout = logfile
        self._stderr = self._stdout
        self._logger = None

    def daemonise(self):
        "Daemonise the process."

        try:
            pid = os.fork()
            if pid > 0:
                sys.exit(0)
        except OSError, e:
            sys.exit("Fork #1 failed: %d (%s)\n" % (e.errno, e.strerror))

        os.chdir("/")
        os.setsid()
        os.umask(0)

        try:
            pid = os.fork()
            if pid > 0:
                sys.exit(0)
        except OSError, e:
            sys.exit("Fork #2 failed: %d (%s)\n" % (e.errno, e.strerror))

        sys.stdout.flush()
        sys.stderr.flush()
        si = file("/dev/null", 'r')
        so = file(self._stdout, 'w')
        se = file(self._stderr, 'w', 0)
        os.dup2(si.fileno(), sys.stdin.fileno())
        os.dup2(so.fileno(), sys.stdout.fileno())
        os.dup2(se.fileno(), sys.stderr.fileno())

        atexit.register(self._deletePidFile)
        pid = str(os.getpid())
        file(self._pidfile,'w+').write("%s\n" % pid)

        formatter = Formatter()
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)
        self._logger = logging.getLogger()
        if self._logger.handlers:
            for handler in self._logger.handlers:
                self._logger.removeHandler(handler)
        self._logger.addHandler(handler)
        if self._loglevel:
            self._logger.setLevel(self._loglevel)
        else:
            self._logger.setLevel(logging.DEBUG)

        logging.debug("Finished daemonising...")

    def _deletePidFile(self):
        "Remove the pidfile."
        os.remove(self._pidfile)

    def _getPid(self):
        "Return the pid of the running daemon process, or None."
        try:
            with open(self._pidfile, "r") as f:
                pid = int(f.read())
        except IOError:
            pid = None
        return pid

    def _getCmdLine(self, pid):
        "Return the command line of the specified pid, or None."
        if pid == None:
            return None
        try:
            with open("/proc/%d/cmdline" % pid, "r") as f:
                cmdline = f.read().lower()
        except IOError:
            cmdline = ""
        return cmdline

    def start(self):
        "Start the daemon."
        logging.debug("Starting the daemon...")
        pid = self._getPid()
        if self.isRunning():
            sys.exit("Daemon already running!")
        self.daemonise()
        self.run()

    def stop(self):
        "Stop the daemon."
        logging.debug("Stopping the daemon...")
        pid = self._getPid()
        if not pid:
            sys.stderr.write("Daemon is not running.\n")
            return
        try:
            while 1:
                os.kill(pid, SIGTERM)
                time.sleep(0.1)
        except OSError, err:
            err = str(err)
            if err.find("No such process") > 0:
                if os.path.exists(self._pidfile):
                    os.remove(self._pidfile)
            else:
                print str(err)
                sys.exit(1)

    def isRunning(self):
        "Return True if the daemon is running, False otherwise."
        return self._getPid() != None

    def status(self):
        "Get the status of the daemon."
        if self.isRunning():
            return "Daemon is running (pid %d)." % self._getPid()
        else:
            return "Daemon is not running."

    def restart(self):
        "Restart the daemon."
        logging.debug("Restarting the daemon...")
        self.stop()
        self.start()

    def run(self):
        "Run the daemon."
        # Override this method when you subclass Daemon.
        # It will be called after the process has been
        # daemonized by start() or restart().
        sys.stderr.write("This method should never execute, it must be overridden!\n")
