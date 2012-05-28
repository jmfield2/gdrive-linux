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

# Based in part on pytrie, https://bitbucket.org/gsakkis/pytrie/
# Copyright (c) 2009, George Sakkis


from UserDict import DictMixin


# Singleton sentinel.
class _Null(object): 
    pass

class _Node(dict):
    """A class representing a node in the directory tree.

    >>> n = _Node()
    >>> n[1] = 1
    >>> n[1]
    1
    >>> n = { 1: 1, 2: 2, 3: 3 }
    >>> n
    {1: 1, 2: 2, 3: 3}
    >>> 1 in n
    True
    >>> 4 in n
    False
    >>> n[5]
    Traceback (most recent call last):
      File "/usr/lib64/python2.7/doctest.py", line 1289, in __run
        compileflags, 1) in test.globs
      File "<doctest __main__._Node[7]>", line 1, in <module>
        n[5]
    KeyError: 5
    """

    def __init__(self, value=_Null):
        super(_Node, self).__init__()    # The base dictionary object.
        self.path = None                # Stores the path to this node.
        self.value = value
        self.children = {}

    def numkeys(self):
        '''Return the number of keys in the subtree rooted at this node.'''
        numk = 0
        if self.value is not _Null:
            numk = sum(child.numkeys() for child in self.children.itervalues())
        return numk

    def __repr__(self):
        valstr = '_Null'
        if self.value is not _Null:
            valstr = repr(self.value)
        return '(%s, {%s})' % (valstr, ', '.join('%r: %r' % cstr for cstr in self.children.iteritems()))

    def __getstate__(self):
        return (self.value, self.children)

    def __setstate__(self, state):
        self.value, self.children = state


class DirectoryTree(DictMixin, object):
    """A prefix tree (Trie) implementation to represent a directory tree.

    >>> t = DirectoryTree()
    >>> t.add("/a/b/c/d")
    >>> t.add("/a/b/c/d/e")
    >>> t.add("/foo/bar")
    >>> print t
    DirectoryTree({'/': '/', '/a': '/a', '/a/b': /a/b', '/a/b/c': /a/b/c', /a/b/c/d': '/a/b/c/d', '/a/b/c/d/e': '/a/b/c/d/e', '/foo/bar': '/foo/bar'})
    >>> t.keys()
    ['/', '/a', '/a/b', '/a/b/c', /a/b/c/d', '/a/b/c/d/e', '/foo', /foo/bar']
    >>> t.values()
    ['/', '/a', '/a/b', '/a/b/c', /a/b/c/d', '/a/b/c/d/e', '/foo', /foo/bar']
    >>> t.items()
    [('/', '/'), ('/a', '/a'), ('/a/b', '/a/b'), ('/a/b/c', '/a/b/c'), ('/a/b/c/d', '/a/b/c/d'), ('/a/b/c/d/e', '/a/b/c/d/e'), ('/foo/bar', '/foo/bar')]
    >>> t.search("/a/b/c")
    ['/a/b/c', '/a/b/c/d', '/a/b/c/d/e']
    """

    def __init__(self, seq=None, **kwargs):
        self._root = _Node('/')
        self.update(seq, **kwargs)
    
    def __len__(self):
        return self._root.numkeys()

    def __iter__(self):
        return self.iterkeys()

    def __contains__(self, key):
        node = self._find(key)
        return node is not None and node.value is not _Null

    def __getitem__(self, key):
        node = self._find(key)
        if node is None or node.value is _Null:
            raise KeyError
        return node.value

    def __setitem__(self, key, value):
        node = self._root
        for part in key.split('/'):
            #print '*** part:', part
            parent = node
            #print '*** node:', node
            next_node = node.children.get(part)
            if next_node is None:
                # Create the intermediate nodes.
                node = node.children.setdefault(part, _Node())
                if part == '/':
                    node.value = '/'
                else:
                    if parent.value is _Null:
                        node.value = '/' + part
                    else:
                        node.value = '/'.join(parent.value.split('/') + [part])
            else:
                node = next_node
        node.value = value

    def __delitem__(self, key):
        parts = []
        node = self._root
        for part in key.split('/'):
            parts.append(node, part)
            node = node.children.get(part)
            if node is None:
                break
        if node is None or node.value is _Null:
            raise KeyError
        node.value = _Null
        while node.value is _Null and not node.children and parts:
            node, part = parts.pop()
            del node.children[part]

    def __repr__(self):
        return '%s({%s})' % (self.__class__.__name__, ', '.join('%r: %r' % t for t in self.iteritems()))

    def _find(self, key):
        node = self._root
        for part in key.split('/'):
            node = node.children.get(part)
            if node is None:
                break
        return node

    def keys(self, prefix=None):
        "Return a list of the trie keys."
        return list(self.iterkeys(prefix))

    def values(self, prefix=None):
        "Return a list of the trie values."
        return list(self.itervalues(prefix))

    def items(self, prefix=None):
        "Return a list of the trie (key, value) tuples."
        return list(self.iteritems(prefix))

    def iteritems(self, prefix=None):
        "Return an iterator over the trie (key, value) tuples."
        
        parts = []
        
        def generator(node, parts=parts):
            if node.value is not _Null:
                #print "*** parts:", parts
                yield ('/'.join(parts), node.value)
            for part, child in node.children.iteritems():
                parts.append(part)
                for subresult in generator(child):
                    yield subresult
                del parts[-1]
        
        node = self._root
        if prefix is not None:
            for part in prefix.split('/'):
                parts.append(part)
                node = node.children.get(part)
                if node is None:
                    node = _Node()
                    break
        
        return generator(node)

    def iterkeys(self, prefix=None):
        "Return an iterator over the trie keys."
        return (key for key, value in self.iteritems(prefix))

    def itervalues(self, prefix=None):
        "Return an iterator over the trie values."
        return (value for key, value in self.iteritems(prefix))

    def add(self, path, value=None):
        "Add a path to the trie."
        if value is not None:
            self[path] = value
        else:
            self[path] = path

    def search(self, prefix=None):
        "Return a list of keys in the trie matching the supplied prefix."
        return list(self.iterkeys(prefix))
        
if __name__ == "__main__":
    import doctest
    doctest.testmod()
