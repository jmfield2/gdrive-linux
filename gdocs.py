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
import sys
import logging
import shutil
import pickle
import pprint

import gdata.gauth
import gdata.docs.client

from dirtree import DirectoryTree

class _Config(object):
    "Class to hold configuration data."
    
    # OAuth 2.0 configuration.
    APP_NAME = "GDrive-Sync-v1"
    CLIENT_ID = '601991085534.apps.googleusercontent.com'
    CLIENT_SECRET = 'HEGv8uk4mXZ41nLmOlGMbGGu'
    REDIRECT_URI = 'urn:ietf:wg:oauth:2.0:oob'
    SCOPES = ["https://www.googleapis.com/auth/userinfo.email", 
              "https://www.googleapis.com/auth/userinfo.profile", 
              "https://docs.google.com/feeds/", 
              "https://docs.googleusercontent.com/", 
              "https://spreadsheets.google.com/feeds/"]
    USER_AGENT = 'gdrive-sync/1.0'

    # Configuration directory.
    CONFIG_DIR = '.config/%s' % CLIENT_ID
    # Token blob file name.
    TOKEN_FILE = 'token.txt' 
    # Metadata file name.
    METADATA_FILE = 'metadata.dat'
     
    # URI to get the root feed. Can also be used to check if a resource is in the 
    # root collection, i.e. its parent is this.
    ROOT_FEED_URI = "/feeds/default/private/full/folder%3Aroot/contents"


class DocsSession(object):
    
    def __init__(self, verbose=False, debug=False):
        "Class constructor."
        if debug:
            logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.DEBUG)
        elif verbose:
            logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.INFO)

        self._token = None          ## OAuth 2,0 token object.
        self._client = None         ## Google Docs API client object.
        self._map = {}              ## Metadata dict.
        self._map["bypath"] = DirectoryTree()    ## Maps paths to resource IDs.
        self._map["byhash"] = {}    ## Maps resource IDs to paths. 
        
        self._authorise()
        if self._token == None:
            # TODO: throw exception.
            sys.exit("Error: failed to authorise with service!")
        self._setup()
        if self._client == None:
            # TODO: throw exception.
            sys.exit("Error: failed to create Docs client!")

        # Load cached metadata, if any.
        loaded = self._load()
        
        if not loaded:
            # Initialise metadata.
            self._walk()
        
        # Save metadata to cache.
        self._save()

    def _getConfigDir(self):
        "Find (create if necessary) the configuration directory."
        home = os.getenv("XDG_CONFIG_HOME") 
        if home == None:
            home = os.getenv("HOME")
            if home == None:
                sys.exit("Error: user home directory is not defined!")
        cfgdir = os.path.join(home, _Config.CONFIG_DIR)
        if os.path.exists(cfgdir):
            if not os.path.isdir(cfgdir):
                sys.exit("Error: \"%s\" exists but is not a directory!" % cfgdir)
        else:
            os.makedirs(cfgdir, 0775)
        return cfgdir

    def getConfigDir(self):
        return self._getConfigDir()

    def _getConfigFile(self, name):
        "Get the path to a file in the configuration directory."
        path = os.path.join(self._getConfigDir(), name)
        if os.path.exists(path):
            if not os.path.isfile(path):
                sys.exit("Error: path \"%s\" exists but is not a file!" % path)
        return path

    def getConfigFile(self, name):
        return self._getConfigFile(name)

    def reset(self):
        self._map = {}
        self._map["bypath"] = DirectoryTree()
        self._map["byhash"] = {} 
        self._walk()
        self._save()

    def _authorise(self):
        "Perform OAuth 2.0 authorisation."
        saved_auth = False
        
        # Try to read saved auth blob.
        tokenfile = self._getConfigFile(_Config.TOKEN_FILE)
        if os.path.exists(tokenfile):
            logging.debug("Reading token...")
            f = open(tokenfile, 'r')
            blob = f.read()
            f.close()
            if blob:
                self._token = gdata.gauth.token_from_blob(blob)
                if self._token:
                    saved_auth = True
        
        # Generate the OAuth 2.0 request token.
        logging.info("Generating the request token...")
        if saved_auth:
            self._token = gdata.gauth.OAuth2Token(client_id=_Config.CLIENT_ID, 
                                                  client_secret=_Config.CLIENT_SECRET, 
                                                  scope=" ".join(_Config.SCOPES), 
                                                  user_agent=_Config.USER_AGENT, 
                                                  refresh_token=self._token.refresh_token)
        else:
            self._token = gdata.gauth.OAuth2Token(client_id=_Config.CLIENT_ID, 
                                                  client_secret=_Config.CLIENT_SECRET, 
                                                  scope=" ".join(_Config.SCOPES), 
                                                  user_agent=_Config.USER_AGENT)
            
            # Authorise the OAuth 2.0 request token.
            print 'Visit the following URL in your browser to authorise this app:'
            print str(self._token.generate_authorize_url(redirect_url=_Config.REDIRECT_URI))
            print 'After agreeing to authorise the app, copy the verification code from the browser.'
            access_code = raw_input('Please enter the verification code: ')
            
            # Get the OAuth 2.0 Access Token.
            self._token.get_access_token(access_code)
            
        # Save the refresh token.
        if self._token.refresh_token and not saved_auth:
            logging.debug("Saving token...")
            f = open(tokenfile, 'w')
            blob = gdata.gauth.token_to_blob(self._token)
            f.write(blob)
            f.close()
    
    def _setup(self):
        "Setup Google Docs session."
        # Create the Google Documents List API client.
        logging.info("Creating the Docs client...")
        self._client = gdata.docs.client.DocsClient(source=_Config.APP_NAME)
        #client.ssl = True  # Force HTTPS use.
        #client.http_client.debug = True  # Turn on HTTP debugging.
        
        # Authorise the client.
        logging.info("Authorising the Docs client API...")
        self._client = self._token.authorize(self._client)
    
    def getUserData(self):
        "Return Google Docs user metadata."
        metadata = self._client.GetMetadata()
        metadict = { 'quota': { 'total':   metadata.quota_bytes_total.text,
                                'used':    metadata.quota_bytes_used.text,
                                'trashed': metadata.quota_bytes_used_in_trash.text },
                     'import': [ "%s to %s" % (input_format.source, input_format.target) for input_format in metadata.import_formats ],
                     'export': [ "%s to %s" % (export_format.source, export_format.target) for export_format in metadata.export_formats ],
                     'features': [ feature.name.text for feature in metadata.features ] 
        } 
        metadict["upload_sizes"] = {}
        for upload_size in metadata.max_upload_sizes:
            metadict["upload_sizes"][upload_size.kind] = upload_size.text
        return metadict

    def _resourceToUri(self, resource):
        "Get the URI for a resource."
        return resource.content.src
    
    def _pathToUri(self, path):
        "Get the URI for a path."
        if path == '/':
            uri = _Config.ROOT_FEED_URI
        else:
            if path in self._map["bypath"]:
                uri = self._map["bypath"][path]["uri"]
            else:
                # TODO: try to handle this better.
                logging.error("Path \"%s\" is unknown!" % path)
                raise KeyError
        #logging.debug("path \"%s\" -> URI \"%s\"" % (path, uri))
        return uri
    
    def _pathToResourceId(self, path):
        "Get the resource ID for a path."
        if path in self._map["bypath"]:
            res_id = self._map["bypath"][path]["resource_id"]
        else:
            # TODO: try to handle this better.
            logging.error("Path \"%s\" is unknown!" % path)
            raise KeyError
        #logging.debug("path \"%s\" -> ID \"%s\"" % (path, res_id))
        return res_id
    
    def _readFolder(self, path):
        "Read the contents of a folder."
        logging.debug("Reading folder \"%s\"" % path)
        uri = self._pathToUri(path)
        #logging.debug("Getting resources from %s" % uri)
        items = self._client.GetAllResources(uri=uri)
        folders = []
        files = []
        for entry in items:
            itempath = os.path.join(path, entry.title.text)
            itemid = entry.resource_id.text
            item = { "path": itempath,
                     "resource_id": itemid, 
                     "uri": entry.content.src, 
                     "size": entry.quota_bytes_used.text }
            if entry.get_resource_type() == 'folder':
                item["type"] = "folder"
                folders.append(itempath)
            else:
                files.append(itempath)
                item["type"] = "file"
            self._map["bypath"].add(itempath, item)
            self._map["byhash"][itemid] = itempath
        folders.sort()
        files.sort()
        return folders, files

    def readFolder(self, path):
        "Get the list of items in the specified folder."
        return self._readFolder(path)
    
    def readRoot(self):
        "Get the list of items in the root folder."
        return self._readFolder('/')
    
    def _walk(self, root='/'):
        "Walk the server-side tree, populating the local maps."
        folders, files = self._readFolder(root)
        for folder in folders:
            self._walk(root=folder)

    def _load(self):
        "Load metadata from local file, if it exists."
        metafile = self._getConfigFile(_Config.METADATA_FILE)
        if os.path.exists(metafile):
            logging.debug("Reading cached metadata...")
            f = open(metafile, 'rb')
            self._map = pickle.load(f)
            f.close()
            return True
        return False
    
    def _save(self):
        "Save metadata to local file."
        metafile = self._getConfigFile(_Config.METADATA_FILE)
        logging.debug("Saving metadata...")
        f = open(metafile, 'wb')
        pickle.dump(self._map, f)
        f.close()
    
    def isFolder(self, path):
        "Return true if the specified path is a folder."
        if path in self._map["bypath"]:
            if self._map["bypath"][path]["type"] == "folder":
                return True
            else:
                return False
        else:
            # TODO: Handle this better. Raise an exception?
            sys.exit("Error: path \"%s\" is unknown!" % path)
    
    def isFile(self, path):
        "Return true if the specified path is a file."
        return not self.isFolder(path)
    
    def getFileSize(self, path):
        "Return the size in bytes of the specified path, if it is a file."
        size = 0
        if not self.isFolder(path):
            if path in self._map["bypath"]:
                size = self._map["bypath"][path]["size"]
        return size

    def update(self, path='/'):
        self._walk(root=path)
        self._save()

    def _checkLocalFile(self, path):
        "Check if the specified file already exists, if so prompt for overwrite."
        # TODO Eventually, allow overwrites to be controlled by a config setting.
        # For now, play safe.
        if not os.path.exists(path):
            return False
        if not os.path.isfile(path):
            # TODO: handle this?
            logging.error("Local path \"%s\" exists, but is not a file!" % path)
            return True
        answer = raw_input("Local file \"%s\" already exists, overwrite? (y/N):")
        if answer.upper() != 'Y':
            return True
        logging.debug("Removing \"%s\"..." % path)
        os.remove(path)
        return False
        
    def _checkLocalFolder(self, path):
        "Check if the specified folder already exists, if so prompt for overwrite."
        # TODO Eventually, allow overwrites to be controlled by a config setting.
        # For now, play safe.
        if not os.path.exists(path):
            os.mkdir(path)
            return False
        if not os.path.isdir(path):
            # TODO: handle this?
            logging.error("Local path \"%s\" exists, but is not a folder!" % path)
            return True
        answer = raw_input("Local folder \"%s\" already exists, overwrite? (y/N):")
        if answer.upper() != 'Y':
            return True
        logging.debug("Removing \"%s\"..." % path)
        shutil.rmtree(path)
        os.mkdir(path)
        return False

    def getNumResources(self, path=None):
        "Returns the total number of resources (files, folders) in the specified path, and all subtrees."
        return len(self._map["bypath"].keys(path))                 
        
    def _download(self, path, localpath):
        "Download a file."
        res_id = self._pathToResourceId(path)
        entry = self._client.GetResourceById(res_id)
        if not entry:
            logging.error("Failed to download path \"%s\"" % path)
            return False
        if entry.get_resource_type() == 'folder':
            logging.error("Path \"%s\" is a folder!" % path)
            return False
        if self._checkLocalFile(localpath):
            return False
        logging.debug("Downloading \"%s\" to \"%s\"..." % (path, localpath))
        self._client.DownloadResource(entry, localpath)
        return True

    def download(self, path, localpath):
        "Download a file or a folder tree."
        if self.isFolder(path):
            logging.debug("Downloading folder \"%s\" to \"%s\"..." % (path, localpath))
            if self._checkLocalFolder(localpath):
                logging.error("Cannot overwrite local path \"%s\", exiting!" % localpath)
                return 
            (folders, files) = self._readFolder(path)
            for fname in files:
                lpath = os.path.join(localpath, os.path.basename(fname))
                self._download(fname, lpath)
            for folder in folders:
                lpath = os.path.join(localpath, os.path.basename(folder))
                self.download(folder, lpath)
        else:
            self._download(path, localpath)

    def getInfo(self):
        "Return general information."
        userdata = self.getUserData()
        userdata["Total resources"] = self.getNumResources()
        return userdata
