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
import time

import daemon

UPDATE_INTERVAL = 30    # Sync update interval in seconds.

class DriveDaemon(daemon.Daemon, object):
    
    def __init__(self):
        "Class constructor."
        
        # Use pidfile in Gdrive config directory.
        pidfile = None
        
        # Use loglevel from GDrive config.
        loglevel = None

        # Use logfile in GDrive config directory.
        stdout = None
        
        super(DriveDaemon, self).__init__(pidfile, loglevel, stdout)

    def run(self):
        "Run the daemon."
    
        while True:

            time.sleep(UPDATE_INTERVAL)

