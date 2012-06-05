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

"Draws a progress bar on an ANSI terminal, using Curses."

import sys
import curses

_CONTROLS = {
    'BOL':          'cr', 
    'UP':           'cuu1', 
    'CLEAR_EOL':    'el', 
    'NORMAL':       'sgr0',
}

_VALUES = {
    'COLUMNS':      'cols',
    'LINES':        'lines',
    'MAX_COLORS':   'colors',
}

class ProgressBar(object):
    "Progress bar class."
    
    def __init__(self, width=None):
        "Constructor."

        self._progress = None
        self._lines = 0
        self._PADDING = 7

        curses.setupterm()

        fgColorSeq = curses.tigetstr('setaf') or curses.tigetstr('setf') or ''
        colorIndex = getattr(curses, 'COLOR_WHITE')
        self._fgcolour = curses.tparm(fgColorSeq, colorIndex)
        
        bgColorSeq = curses.tigetstr('setab') or curses.tigetstr('setb') or ''
        colorIndex = getattr(curses, 'COLOR_BLACK')
        self._bgcolour = curses.tparm(bgColorSeq, colorIndex)

        self._control = {}
        for control in _CONTROLS:
            # Set the control escape sequence
            self._control[control] = curses.tigetstr(_CONTROLS[control]) or ''

        self._value = {}
        for value in _VALUES:
            # Set terminal related values
            self._value[value] = curses.tigetnum(_VALUES[value])

        if width and width < self._value["COLUMNS"] - self._PADDING:
            self._width = width
        else:
            self._width = self._value["COLUMNS"] - self._PADDING

    def render(self, percent, msg=''):
        "Print the _progress bar."
        msglen = 0
        if msg:
            msglen = len(msg.splitlines()[0])
        if msglen + self._width + self._PADDING > self._value["COLUMNS"]:
            width = self._value["COLUMNS"] - msglen -self._PADDING
        else:
            width = self._width
        if self._progress != None:
            self.clear()
        self._progress = (width * percent) / 100
        data = "%s%s%s%s %3s%% %s\n" % (self._fgcolour, '#' * self._progress, self._control["NORMAL"], ' ' * (width - self._progress), percent, msg)
        sys.stdout.write(data)
        sys.stdout.flush()
        self._lines = len(data.splitlines())

    def clear(self):
        """Clear all printed _lines"""
        sys.stdout.write(self._lines * (self._control["UP"] + self._control["BOL"] + self._control["CLEAR_EOL"]))

if __name__ == "__main__":
    import time
    p = ProgressBar(width=80)
    for i in range(101):
        p.render(i, 'step %3s' % i)
        time.sleep(0.05)
