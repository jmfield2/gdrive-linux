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

import logging
import time

class Formatter(logging.Formatter):
    "Custom log formatter class."
    
    _DEFAULT_FMT = '%(levelname)-8s [%(asctime)s] %(message)s'
    _DEBUG_FMT = '%(levelname)-8s [%(asctime)s] %(filename)-16s %(lineno)-5d %(funcName)-24s  %(message)s'
    
    def __init__(self, debug=False):
        "Class constructor."
        fmt = self._DEFAULT_FMT
        if debug:
            fmt = self._DEBUG_FMT
        super(Formatter, self).__init__(fmt)
        self.converter = time.gmtime

    def formatException(self, exc_info):
        "Format exception messages."
        text = super(Formatter, self).formatException(exc_info)
        text = '\n'.join(('! %s' % line) for line in text.splitlines())
        return text

