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
from signal import SIGTERM 

# Based in part on code originally from:
# http://www.jejik.com/articles/2007/02/a_simple_unix_linux_daemon_in_python/

# To use, subclass the Daemon class and override the run() method.
# See http://www.erlenstar.demon.co.uk/unix/faq_2.html#SEC16
# for details on the daemonisation process.

class Daemon:
    "A generic daemon class."
    
    
    def __init__(self, pidfile, stdin='/dev/null', stdout='/dev/null', stderr='/dev/null'):
        self._stdin = stdin
        self._stdout = stdout
        self._stderr = stderr
        self._pidfile = pidfile
    
    def daemonise(self):
        "Daemonise the process."
        
        try: 
            pid = os.fork() 
            if pid > 0:
                # Exit the first parent.
                sys.exit(0) 
        except OSError, e: 
            sys.stderr.write("fork #1 failed: %d (%s)\n" % (e.errno, e.strerror))
            sys.exit(1)
    
        # Decouple from parent environment.
        os.chdir("/") 
        os.setsid() 
        os.umask(0) 
    
        # Do the second fork.
        try: 
            pid = os.fork() 
            if pid > 0:
                # Exit from the second parent.
                sys.exit(0) 
        except OSError, e: 
            sys.stderr.write("fork #2 failed: %d (%s)\n" % (e.errno, e.strerror))
            sys.exit(1) 
    
        # Redirect standard file descriptors.
        sys.stdout.flush()
        sys.stderr.flush()
        si = file(self._stdin, 'r')
        so = file(self._stdout, 'a+')
        se = file(self._stderr, 'a+', 0)
        os.dup2(si.fileno(), sys.stdin.fileno())
        os.dup2(so.fileno(), sys.stdout.fileno())
        os.dup2(se.fileno(), sys.stderr.fileno())
    
        # Write pidfile.
        atexit.register(self._delpid)
        pid = str(os.getpid())
        file(self._pidfile,'w+').write("%s\n" % pid)
    
    def _delpid(self):
        os.remove(self._pidfile)

    def start(self):
        "Start the daemon."
        
        # Check for a pidfile to see if the daemon is already running.
        try:
            pf = file(self._pidfile,'r')
            pid = int(pf.read().strip())
            pf.close()
        except IOError:
            pid = None
    
        if pid:
            sys.stderr.write("pidfile %s already exists. Daemon already running?\n" % self._pidfile)
            sys.exit(1)
        
        # Start the daemon.
        self.daemonise()
        self.run()

    def stop(self):
        "Stop the daemon."
        
        # Get the pid from the pidfile.
        try:
            pf = file(self._pidfile,'r')
            pid = int(pf.read().strip())
            pf.close()
        except IOError:
            pid = None
    
        if not pid:
            sys.stderr.write("pidfile %s does not exist. Daemon not running?\n" % self._pidfile)
            return 

        # Try killing the daemon process.    
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

    def restart(self):
        "Restart the daemon."
        self.stop()
        self.start()

    def run(self):
        "Run the daemon."
        # Override this method when you subclass Daemon. 
        # It will be called after the process has been
        # daemonized by start() or restart().
        pass


if __name__ == "__main__":

    class MyDaemon(Daemon):
        def run(self):
            while True:
                time.sleep(1)
    
    daemon = MyDaemon('/tmp/daemon-example.pid')
    if len(sys.argv) == 2:
        if 'start' == sys.argv[1]:
            daemon.start()
        elif 'stop' == sys.argv[1]:
            daemon.stop()
        elif 'restart' == sys.argv[1]:
            daemon.restart()
        else:
            print "Unknown command"
            sys.exit(2)
        sys.exit(0)
    else:
        print "usage: %s start|stop|restart" % sys.argv[0]
        sys.exit(2)
