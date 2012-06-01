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
import ConfigParser
import csv
import pprint

import gdata.gauth
import gdata.docs.client

from dirtree import DirectoryTree
import progressbar


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
    # Configuration file name.
    CONFIG_FILE = 'gdrive.cfg'

    # Maximum results to return per request.
    MAX_RESULTS = 500
    
    # URI to get the root feed. Can also be used to check if a resource is in the 
    # root collection, i.e. its parent is this.
    ROOT_FEED_URI = "/feeds/default/private/full/folder%3Aroot/contents"

    # Default configuration values, for user-configurable options. 
    CONFIG_DEFAULTS = { 
        "localstore": { 
            "path": ""      # The path to the root of the local copy of the folder tree.
        }, 
        "general": { 
            "excludes": ""  # A comma-delimited list of strings specifying paths to be ignored.
        }
    }

class DocsSession(object):
    
    def __init__(self, verbose=False, debug=False):
        "Class constructor."
        self._debug = debug
        self._verbose = verbose
        if verbose or debug:
            if debug:
                formatter = logging.Formatter('%(levelname)-7s %(filename)-16s %(lineno)-5d %(funcName)-16s  %(message)s')
            else:
                formatter = logging.Formatter('%(levelname)-7s %(message)s')
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(formatter)
            logger = logging.getLogger()
            logger.addHandler(handler)
            if debug:
                logger.setLevel(logging.DEBUG)
            else:
                logger.setLevel(logging.INFO)
        else:
            logging.basicConfig(format='%(levelname)-7s %(message)s', level=logging.WARNING)

        self._config = {}       ## Configuration dict.
        
        self._token = None      ## OAuth 2,0 token object.
        self._client = None     ## Google Docs API client object.
        
        self._metadata = {}                                 ## Metadata dict.
        self._metadata["changestamp"] = 0                   ## Stores the last changestamp, if any.
        self._metadata["map"] = {}
        self._metadata["map"]["bypath"] = DirectoryTree()   ## Maps paths to resource IDs.
        self._metadata["map"]["byid"] = {}                  ## Maps resource IDs to paths. 
        
        self._folder_count = 0
        self._file_count = 0
        self._bar = None

        # Load configuration (if any), or initialise to default.
        self._loadConfig()
        
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
        
        # Ensure local storage tree is available.
        self._checkLocalRoot()

    def _getHomeDir(self):
        "Get the users home directory."
        home = os.getenv("XDG_CONFIG_HOME") 
        if home == None:
            home = os.getenv("HOME")
            if home == None:
                sys.exit("Error: user home directory is not defined!")
        return home

    def _getConfigDir(self):
        "Find (create if necessary) the configuration directory."
        cfgdir = os.path.join(self._getHomeDir(), _Config.CONFIG_DIR)
        if os.path.exists(cfgdir):
            if not os.path.isdir(cfgdir):
                sys.exit("Error: \"%s\" exists but is not a directory!" % cfgdir)
        else:
            os.makedirs(cfgdir, 0775)
        return cfgdir

    def _getConfigFile(self, name):
        "Get the path to a file in the configuration directory."
        path = os.path.join(self._getConfigDir(), name)
        if os.path.exists(path):
            if not os.path.isfile(path):
                sys.exit("Error: path \"%s\" exists but is not a file!" % path)
        return path

    def _defaultConfig(self):
        logging.debug("Using default configuration...")
        self._config = _Config.CONFIG_DEFAULTS.copy()
        
    def _loadConfig(self):
        """Load a dictionary of configuration data, from the configuration, 
           file if it exists, or initialise with default values otherwise."""
        self._config = {}
        config = ConfigParser.RawConfigParser()
        cfgfile = self._getConfigFile(_Config.CONFIG_FILE)
        if os.path.exists(cfgfile):
            logging.debug("Reading configuration...")
            config.read(cfgfile)
            sections = config.sections()
            sections.sort()
            for section in sections:
                self._config[section] = {}
                options = config.options(section)
                for option in options:
                    if option == "excludes":
                        exclist = []
                        # Need to handle the comma-delimited quoted strings.
                        parser = csv.reader(config.get(section, option), skipinitialspace=True)
                        for fields in parser:
                            for index, field in enumerate(fields):
                                if field == '':
                                    continue
                                exclist.append(field)
                        self._config[section][option] = exclist
                    else:
                        self._config[section][option] = config.get(section, option)
                    logging.debug("Configuration: section=%s option=%s value=%s" % (section, option, self._config[section][option]))
        else:
            self._defaultConfig()
            self._saveConfig()

    def _saveConfig(self):
        "Save the current configuration data to the configuration file." 
        config = ConfigParser.RawConfigParser()
        cfgfile = self._getConfigFile(_Config.CONFIG_FILE)
        if not self._checkLocalFile(cfgfile):
            for section in self._config:
                config.add_section(section)
                for option in self._config[section]:
                    if option == "excludes":
                        if self._config[section][option]:
                            # Need to handle the comma-delimited quoted strings.
                            excstr = ', '.join(self._config[section][option])
                            config.set(section, option, excstr)
                        else:
                            config.set(section, option, "")
                    else:
                        config.set(section, option, self._config[section][option])
            logging.debug("Writing configuration...")
            f = open(cfgfile, 'w')
            config.write(f)
            f.close()
        else:
            logging.error("Could not write configuration!")

    def _getLocalRoot(self):
        "Get the path to the root of the local storage tree."
        return self._config["localstore"]["path"]

    def _setLocalRoot(self, path):
        "Set the path to the root of the local storage tree."
        logging.error("Setting local root is not yet implemented!")
        #self._config["localstore"]["path"] = path
        # TODO check for existing tree at new path.
        # TODO move existing local tree to new path.
        self._saveConfig()

    def _checkLocalRoot(self):
        "Check if the local storage folder exists, if not create it."
        path = self._getLocalRoot()
        if path:
            if not os.path.exists(path):
                logging.debug("Creating local storage tree at %s" % path)
                os.mkdir(path)
                return path
            if not os.path.isdir(path):
                # TODO: handle this?
                logging.error("Local path \"%s\" exists, but is not a folder!" % path)
                return None
        else:
            logging.warn("Local storage path is not specified!")
        return path

    def _getLocalPath(self, path):
        "Return the local path corresponding to the specified remote path."
        if path.startswith(self._config["localstore"]["path"]) is True:
            return path
        else:
            if os.path.isabs(path):
                # Strip the leading slash, otherwise os.path.join throws away any preceding paths in the list.
                path = path[1:]
            return os.path.join(self._config["localstore"]["path"], path)

    def _getExcludes(self):
        "Get the list of folders/files to be excluded."
        return self._config["general"]["excludes"]

    def _setExcludes(self, exclist):
        "Set the list of folders/files to be excluded."
        logging.error("Setting local root is not yet implemented!")
        #self._config["general"]["excludes"] = exclist
        # TODO check for existing tree at new path.
        # TODO move existing local tree to new path.
        self._saveConfig()

    def reset(self):
        "Reset local cached metadata."
        self._metadata = {}
        self._metadata["changestamp"] = 0
        self._metadata["map"] = {}
        self._metadata["map"]["bypath"] = DirectoryTree()
        self._metadata["map"]["byid"] = {} 
        self._walk()
        self._save()
        self._folder_count = 0
        self._file_count = 0
        self._num_folders = 0
        self._num_files = 0
        self._bar = None

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
    
    def getMetadata(self):
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
        for child in metadata.children:
            if child.tag == "largestChangestamp":
                metadict["changestamp"] = int(child.attributes["value"])
                break
        return metadict

    def _printresource(self, resource):
        "Print debugging information about a resource."
        logging.debug("Resource: id=%s type=%s updated=%s name=%s" % (resource.id.text, resource.content.type, resource.updated.text, resource.title.text))

    def _resourceToUri(self, resource):
        "Get the URI for a resource."
        return resource.content.src
    
    def _resourceIdToPath(self, resource_id):
        "Get the path for a resource ID."
        try:
            path = self._metadata["map"]["byid"][resource_id]
        except KeyError:
            path = None
        return path
    
    def _pathToUri(self, path):
        "Get the URI for a path."
        if path == '/':
            uri = _Config.ROOT_FEED_URI
        else:
            if path in self._metadata["map"]["bypath"]:
                uri = self._metadata["map"]["bypath"][path]["uri"]
            else:
                # TODO: try to handle this better.
                logging.error("Path \"%s\" is unknown!" % path)
                raise KeyError
        #logging.debug("path \"%s\" -> URI \"%s\"" % (path, uri))
        return uri
    
    def _pathToResourceId(self, path):
        "Get the resource ID for a path."
        if path in self._metadata["map"]["bypath"]:
            res_id = self._metadata["map"]["bypath"][path]["resource_id"]
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
            self._metadata["map"]["bypath"].add(itempath, item)
            self._metadata["map"]["byid"][itemid] = itempath
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
            self._metadata = pickle.load(f)
            f.close()
            return True
        return False
    
    def _save(self):
        "Save metadata to local file."
        metafile = self._getConfigFile(_Config.METADATA_FILE)
        logging.debug("Saving metadata...")
        f = open(metafile, 'wb')
        pickle.dump(self._metadata, f)
        f.close()
    
    def isFolder(self, path):
        "Return true if the specified path is a folder."
        if path in self._metadata["map"]["bypath"]:
            if self._metadata["map"]["bypath"][path]["type"] == "folder":
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
            if path in self._metadata["map"]["bypath"]:
                size = int(self._metadata["map"]["bypath"][path]["size"])
        return size

    def _getLargestChangestamp(self):
        "Returns the largest changestamp."
        metadict = self.getMetadata()
        logging.debug("Max changestamp: %d" % metadict["changestamp"])
        return metadict["changestamp"]

    def _getChanges(self, changestamp=0):
        "Get a list of resource IDs that have changed since the specified changestamp."
        changes = []
        resource_ids = []
        if changestamp == 0:
            logging.debug("Getting all changes...")
            feed = self._client.GetChanges(max_results=_Config.MAX_RESULTS, show_root=True)
        else:
            logging.debug("Getting changes since changestamp=%s..." % changestamp)
            feed = self._client.GetChanges(changestamp=str(changestamp), max_results=_Config.MAX_RESULTS, show_root=True)
        if feed:
            changes.extend(feed.entry)
        while feed and len(feed.entry) == _Config.MAX_RESULTS:
            feed = self._client.GetNext(feed)
            changes.extend(feed.entry)
        if len(changes) > 0:
            # Save a changestamp of one beyond the last.
            self._metadata["changestamp"] = int(changes[-1].changestamp.value) + 1
            logging.debug("Got %d changes, last changestamp is %d" % (len(changes), self._metadata["changestamp"]))
            for change in changes:
                resource_ids.append(change.resource_id.text)
        return resource_ids

    def update(self, path='/'):
        "Update the local tree at the specified path to match the server."
        logging.debug("Updating %s..." % path)
        # Request change feed from the last changestamp. 
        # If no stored changestamp, then start at the beginning.
        self._metadata["changestamp"] = 203713
        if self._metadata["changestamp"] == 0:
            #self._metadata["changestamp"] = self._getLargestChangestamp() + 1
            self._walk(root=path)
            self.download(path, self._getLocalPath(path), overwrite=True)
        # Now check for changes again, since before we walked.
        resource_ids = self._getChanges(self._metadata["changestamp"])
        if len(resource_ids) > 0:
            # Iterate over the changes, downloading each resource.
            for res_id in resource_ids:
                res_path = self._resourceIdToPath(res_id) 
                if res_path == None:
                    logging.debug("No local path for resource ID %s" % res_id)
                    # The resource is not in our cache.
                    resource = self._client.GetResourceById(res_id, show_root=True)
                    if not resource:
                        # TODO: This should never fail.
                        logging.error("Failed to get resource \"%s\"" % res_id)
                        break
                    self._printresource(resource)
                    # Repeatedly get the parent until we find one in our cache, or else reach the root, 
                    # which should always exist. If it has no parent, and is not in root, then it must 
                    # be shared. 
                    # TODO: support shared resources somehow.
                    parents = resource.InCollections()
                    for parent in parents:
                        parent_resid = parent.resource_id.text
                        logging.debug("Parent resource ID %s" % parent_resid)
                        parent_resids = [parent_resid]
                        while parent_resid not in self._metadata["map"]["byid"]:
                            logging.debug("Parent resource ID %s not in cache" % parent_resid)
                            parent = parent.InCollections()
                            parent_resid = parent.resource_id.text
                            parent_resids.insert(0, parent_resid)
                        logging.debug("Found parent resource ID %s in cache" % parent_resid)
                        top_path = self._resourceIdToPath(parent_resid)
                        logging.debug("Found parent path %s in cache" % top_path)
                        self._walk(top_path)
                    res_path = self._resourceIdToPath(res_id)
                    if res_path == None:
                        logging.warn("No parent path found, must be a shared resource, skipping...")
                        continue
                logging.debug("TODO: get resource %s (%s)" % (res_id, res_path))
                # Download the top_path subtree here. 
                self.download(top_path, self._getLocalPath(top_path), overwrite=True)
        self._save()

    def _checkLocalFile(self, path, overwrite=False):
        "Check if the specified file already exists, if so prompt for overwrite."
        # TODO Eventually, allow overwrites to be controlled by a config setting.
        # For now, play safe.
        if not os.path.exists(path):
            return False
        if not os.path.isfile(path):
            # TODO: handle this?
            logging.error("Local path \"%s\" exists, but is not a file!" % path)
            return True
        if not overwrite:
            answer = raw_input("Local file \"%s\" already exists, overwrite? (y/N):")
            if answer.upper() != 'Y':
                return True
        logging.debug("Removing \"%s\"..." % path)
        os.remove(path)
        return False
        
    def _checkLocalFolder(self, path, overwrite=False):
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
        if not overwrite:
            answer = raw_input("Local folder \"%s\" already exists, overwrite? (y/N):")
            if answer.upper() != 'Y':
                return True
            logging.debug("Removing \"%s\"..." % path)
            shutil.rmtree(path)
            os.mkdir(path)
        return False

    def getNumResources(self, path=None):
        "Returns the total number of resources (files, folders) in the specified path, and all subtrees."
        return len(self._metadata["map"]["bypath"].keys(path))                 
        
    def getNumRemoteFolders(self, path=None):
        "Returns the total number of folders in the specified remote path, and all subtrees."
        count = 0
        for value in self._metadata["map"]["bypath"].itervalues(path):
            if value["type"] == "folder":
                count += 1
        return count
        
    def getNumRemoteFiles(self, path=None):
        "Returns the total number of files in the specified remote path, and all subtrees."
        count = 0
        for value in self._metadata["map"]["bypath"].itervalues(path):
            if value["type"] != "folder":
                count += 1
        return count
        
    def getNumLocalFolders(self, path):
        "Returns the total number of folders in the specified local path, and all subtrees."
        count = 0
        for root, dirs, files in os.walk(path):
            count += len(dirs)
        return count
        
    def getNumLocalFiles(self, path):
        "Returns the total number of files in the specified local path, and all subtrees."
        count = 0
        for root, dirs, files in os.walk(path):
            count += len(files)
        return count

    def _download(self, path, localpath, overwrite=False):
        "Download a file."
        res_id = self._pathToResourceId(path)
        entry = self._client.GetResourceById(res_id)
        if not entry:
            logging.error("Failed to download path \"%s\"" % path)
            return False
        if self.isFolder(path):
            if self._checkLocalFolder(localpath, overwrite=overwrite):
                logging.error("Cannot overwrite local path \"%s\", exiting!" % localpath)
                return 
            logging.info("Downloading folder %s (%d of %d)..." % (localpath, self._folder_count, self._num_folders))
            (folders, files) = self._readFolder(path)
            for fname in files:
                lpath = os.path.join(localpath, os.path.basename(fname))
                self._download(fname, lpath)
                self._file_count += 1
            for folder in folders:
                lpath = os.path.join(localpath, os.path.basename(folder))
                self._download(folder, lpath)
            self._folder_count += 1
        else:
            logging.info("Downloading file %s (%d bytes) (%d of %d)..." % (localpath, self.getFileSize(path), self._file_count, self._num_files))
            if self._bar:
                self._bar.render(self._file_count * 100 / self._num_files, localpath)
            if self._checkLocalFile(localpath, overwrite=overwrite):
                return False
            self._client.DownloadResource(entry, localpath)
        return True

    def download(self, path, localpath=None, overwrite=False):
        "Download a file or a folder tree."
        self._folder_count = 1
        self._num_folders = self.getNumRemoteFolders(path)
        self._file_count = 1
        self._num_files = self.getNumRemoteFiles(path)
        if not self._verbose and not self._debug:
            if self._num_folders + self._num_files > 2:
                self._bar = progressbar.ProgressBar(width=80)
        if localpath is None:
            localpath = os.path.join(self._getLocalRoot(), path)
        self._download(path, localpath, overwrite=overwrite)
        self._folder_count = 0
        self._file_count = 0
        
    def _upload(self, localpath, path):
        "Download a file."
        logging.error("Upload is not yet implemented!")
        return False

    def upload(self, localpath, path=None):
        "Upload a file or a folder tree."
        if path is None:
            if localpath.startswith(self._getLocalRoot()):
                path = localpath[len(self._getLocalRoot()):]
            else:
                path = '/'
        self._folder_count = 1
        self._num_folders = self.getNumLocalFolders(path)
        self._file_count = 1
        self._num_files = self.getNumLocalFiles(path)
        if not self._verbose and not self._debug:
            if self._num_folders + self._num_files > 2:
                self._bar = progressbar.ProgressBar(width=80)
        self._upload(localpath, path)
        self._folder_count = 0
        self._file_count = 0
        
    def getInfo(self):
        "Return general information."
        userdata = self.getMetadata()
        userdata["Total resources"] = self.getNumResources()
        return userdata
