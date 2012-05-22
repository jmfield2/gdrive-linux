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

import fuse
import gdocs
import stat
import errno
import os
import time

fuse.fuse_python_api = (0, 2)

class Resource(object):
    """ gdrive object (file/dir). """

    def __init__(self, mode):
        self.mode = mode


class Drive(object):

    def _readDir(self, dirname):
        """ Recursively read contents of dirname, return dict mapping
            object names to Resources. """

        dirs, files = self._session.readFolder(dirname)

        items = {}
        for f in files:
            items[f] = Resource(stat.S_IFREG)
        for d in dirs:
            items[d] = Resource(stat.S_IFDIR)
            items.update(self._readDir(d))

        return items

    def __init__(self):

        self._session = gdocs.DocsSession()
        self._root = {'/': self._readDir('/')}

    def resource(self, path):
        """ Return resource at path, None if it doesn't exist. """

        # eh, this is wrong... but it works if you only have the root dir
        res = None
        try:
            res = self._root[path]
        except KeyError:
            pass

        return res

class GDFS(fuse.Fuse):

    def __init__(self, *args, **kwargs):

        fuse.Fuse.__init__(self, *args, **kwargs)

        self._drive = Drive()

    def getattr(self, path):

        res = self._drive.resource(path)
        if res == None:
            return -errno.ENOENT

        # Fill in a stat struct
        st = zstat(fuse.Stat())
        st.st_mode = res.mode
        st.st_uid = os.getuid()
        st.st_gid = os.getgid()
        st.st_atime = time.time()
        st.st_mtime = time.time()
        st.st_ctime = time.time()
        st.st_size = 0

        return st

    def readdir(self, path, offset):
        yield fuse.DirEntry('.')
        yield fuse.DirEntry('..')

        res = self._drive.resource(path)
        for dir_entry in res:
            yield fuse.DirEntry(dir_entry)

if __name__ == '__main__':
    fs = GDFS()
    fs.parse()
    fs.main()


