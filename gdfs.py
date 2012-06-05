#!/usr/bin/env python
#
# Copyright 2012 Duncan Palmer. All Rights Reserved.
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

import stat
import errno
import os
import time

import fuse
from fuse import Fuse

import gdocs

fuse.fuse_python_api = (0, 2)

class Resource(object):
    """GDrive object (file/dir)."""

    def __init__(self, mode):
        self.mode = mode


class Drive(object):
    "Class representing users GDrive."

    def __init__(self):
        "Class constructor."
        self._session = gdocs.Session()
        self._root = {'/': self._readDir('/')}

    def _readDir(self, dirname):
        """Recursively read contents of dirname, return dict mapping
           object names to Resources."""
        dirs, files = self._session.readFolder(dirname)

        items = {}
        for f in files:
            items[f] = Resource(stat.S_IFREG)
        for d in dirs:
            items[d] = Resource(stat.S_IFDIR)
            items.update(self._readDir(d))

        return items

    def resource(self, path):
        """ Return resource at path, None if it doesn't exist. """
        # eh, this is wrong... but it works if you only have the root dir
        res = None
        try:
            res = self._root[path]
        except KeyError:
            pass
        return res


class MyStat(fuse.Stat):
    def __init__(self):
        self.st_mode = 0
        self.st_ino = 0
        self.st_dev = 0
        self.st_nlink = 0
        self.st_uid = os.getuid()
        self.st_gid = os.getgid()
        self.st_size = 0
        self.st_atime = self.st_mtime = self.st_ctime = time.time()


class GDriveFs(Fuse):
    "Google Drive FUSE filesystem class."

    def __init__(self, *args, **kwargs):
        "Class constructor."
        Fuse.__init__(self, *args, **kwargs)
        self._uid = os.getuid()
        self._gid = os.getgid()
        #self._drive = Drive()
        self._session = gdocs.Session(verbose=True, debug=True)

    def getattr(self, path):
        "Get path attributes."
        print "getattr(%s)" % (path)
        st = MyStat()
        st.st_uid = self._uid
        st.st_gid = self._gid
        if path == '/':
            st.st_mode = stat.S_IFDIR | 0755
            st.st_nlink = 2
        else:
            if self._session.isFolder(path):
                st.st_mode = stat.S_IFDIR | 0755
                st.st_nlink = 2
            else:
                st.st_mode = stat.S_IFREG | 0444
                st.st_nlink = 1
                st.st_size = 0  ## TODO!
        return st

    def readdir(self, path, offset):
        "Generator for the contents of a directory."
        print "readdir(%s,%s)" % (path, offset)
        folders, files = self._session.readFolder(path)
        items = [ '.', '..' ]
        items.extend(folders)
        items.extend(files)
        for r in  items:
            print "Yielding", r
            yield fuse.Direntry(r)

    def open(self, path, flags):    
        "Open file."
        print "open(%s,%s)" % (path, flags)
        accmode = os.O_RDONLY | os.O_WRONLY | os.O_RDWR
        if (flags & accmode) != os.O_RDONLY:
            return -errno.EACCES

    def read(self, path, size, offset):
        "Read file."
        print "read(%s,%s,%s)" % (path, size, offset)
        return -errno.ENOENT

def main():
    usage="""
GDriveFs - Google Drive Filesystem

""" + fuse.Fuse.fusage

    fs = GDriveFs(version="%prog " + fuse.__version__, usage=usage, dash_s_do='setsingle')

    fs.flags = 0
    fs.multithreaded = 0
    fs.parse(errex=1)
    fs.main()

if __name__ == '__main__':
    main()
