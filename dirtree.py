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

import os
import os.path


class Node(object):
    "A class representing a node in the directory tree."

    def __init__(self):
        self._dict = {}
        self._path = None
        self._data = None

    def get_dict(self):
        return self.__dict

    def get_path(self):
        return self.__path

    def get_data(self):
        return self.__data

    def set_dict(self, value):
        self.__dict = value

    def set_path(self, value):
        self.__path = value

    def set_data(self, value):
        self.__data = value

    path = property(get_path, set_path)
    data = property(get_data, set_data)
    dict = property(get_dict, set_dict)


class DirectoryTree(object):
    "A prefix tree (Trie) implementation to represent a directory tree, storing an arbitrary object at each node."

    def __init__(self):
        self._root = {}
        self._objstore = {}

    def __contains__(self, path):
        "True if the tree contains the specified path."
        node = self._root
        for pathcomp in os.path.split(path):
            try:
                node = node[pathcomp]
            except KeyError:
                return False
        return True

    def add(self, path, obj):
        "Add a path to the tree, storing the object."
        node = self._root
        for pathcomp in os.path.split(path):
            try: 
                node = node[pathcomp]
            except KeyError:
                node[pathcomp] = {}
                self._objstore[path] = obj
                node = node[pathcomp]

    def remove(self, path):
        "Remove a path from the tree, removing the associated object."
        node = self._root
        for pathcomp in os.path.split(path):
            try:
                node = node[pathcomp]
            except KeyError:
                return
        del node[pathcomp]
        del self._objstore[path]

    def update(self, paths, objs):
        "Add a list of paths and a list of corresponding objects to the tree."
        if len(paths) != len(objs):
            raise Exception("Paths and objects iterables must be the same length!")
        for i in range(len(paths)):
            self.add(paths[i], objs[i])

    def _walk(self, node):
        "Walk a subtree."
        for pathcomp in node:
            yield self._walk(node[pathcomp])

    def _path(self, node):
        "Get the path from the root to the supplied node."
        # TODO: hmmm, no clue yet how to do this.
        pass
    
    def search(self, prefix):
        "Returns a list of keys matching the prefix in the tree."
        node = self._root
        for pathcomp in os.path.split(prefix):
            try:
                node = node[pathcomp]
            except KeyError: 
                return []
        slist = []
        for node in self._walk(node):
            slist.append(self._path(node))
        return slist

    def get(self, path):
        if self.__contains__(path):
            return self._objstore[path]
        else:
            return None
