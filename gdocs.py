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
import optparse
import re
import pprint

import gdata.gauth
import gdata.docs.client


class _Config(object):
    "Class to hold configuration data."
    
    # OAuth 2.0 configuration.
    APP_NAME = "GDocs-Sample-v1"
    CLIENT_ID = '601991085534.apps.googleusercontent.com'
    CLIENT_SECRET = 'HEGv8uk4mXZ41nLmOlGMbGGu'
    REDIRECT_URI = 'urn:ietf:wg:oauth:2.0:oob'
    SCOPES = ["https://www.googleapis.com/auth/userinfo.email", 
              "https://www.googleapis.com/auth/userinfo.profile", 
              "https://docs.google.com/feeds/", 
              "https://docs.googleusercontent.com/", 
              "https://spreadsheets.google.com/feeds/"]
    USER_AGENT = 'gdocs-sample/1.0'

    # Configuration directory.
    CONFIG_DIR = '.config/%s' % CLIENT_ID
    # Token blob file name.
    TOKEN_FILE = 'token.txt' 
    # URI to get the root feed. Can also be used to check if a resource is in the 
    # root collection, i.e. its parent is this.
    ROOT_FEED_URI = "/feeds/default/private/full/folder%3Aroot/contents"


class DocsSession(object):
    
    def __init__(self):
        "Class constructor."

        self._token = None      ## OAuth 2,0 token object.
        self._client = None     ## Google Docs API client object.
        self._pathmap = {}      ## Maps paths to resource IDs.
        self._hashmap = {}      ## Maps resource IDs to paths.
        
        self._authorise()
        if self._token == None:
            # TODO: throw exception.
            sys.exit("Error: failed to authorise with service!")
        self._setup()
        if self._client == None:
            # TODO: throw exception.
            sys.exit("Error: failed to create Docs client!")

        # Initialise metadata.
        self._walk()
        
    def _authorise(self):
        "Perform OAuth 2.0 authorisation."
        
        saved_auth = False
        
        # Try to read saved auth blob.
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
        tokenfile = os.path.join(cfgdir, _Config.TOKEN_FILE)
        if os.path.exists(tokenfile):
            if not os.path.isfile(tokenfile):
                sys.exit("Error: path \"%s\" exists but is not a file!" % tokenfile)
            logging.info("Reading token...")
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
            logging.info("Saving token...")
            f = open(tokenfile, 'w')
            blob = gdata.gauth.token_to_blob(self._token)
            f.write(blob)
            f.close()
    
    def _setup(self):
        # Create the Google Documents List API client.
        logging.info("Creating the Docs client...")
        self._client = gdata.docs.client.DocsClient(source=_Config.APP_NAME)
        #client.ssl = True  # Force HTTPS use.
        #client.http_client.debug = True  # Turn on HTTP debugging.
        
        # Authorise the client.
        logging.info("Authorising the Docs client API...")
        self._client = self._token.authorize(self._client)
    
    def getMetadata(self):
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
        return resource.content.src
    
    def _pathToUri(self, path):
        if path == '/':
            uri = _Config.ROOT_FEED_URI
        else:
            if path in self._pathmap:
                uri = self._pathmap[path]["uri"]
            else:
                # TODO: try to handle this better.
                logging.error("Path \"%s\" is unknown!" % path)
                raise KeyError
        logging.debug("path \"%s\" -> URI \"%s\"" % (path, uri))
        return uri
    
    def _readFolder(self, path):
        logging.debug("Reading folder \"%s\"" % path)
        uri = self._pathToUri(path)
        #items = self._client.GetAllResources(uri=uri, show_root='true')
        logging.debug("Getting resources from %s" % uri)
        items = self._client.GetAllResources(uri=uri)
        folders = []
        files = []
        for entry in items:
            if entry.get_resource_type() == 'folder':
                folders.append(os.path.join(path, entry.title.text))
            else:
                files.append(os.path.join(path, entry.title.text))
            # Chomp the URI, get rid of the scheme and hostname, leave only the path.
            self._pathmap[os.path.join(path, entry.title.text)] = { "resource_id": entry.resource_id.text, 
                                                                    "uri": entry.content.src }
            self._hashmap[entry.resource_id.text] = os.path.join(path, entry.title.text)
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


def _parseArgs():
    helpStr = """
%prog [options] 

Utility to access Google Drive on Linux.

"""
    parser = optparse.OptionParser(description=helpStr)
    parser.add_option('-v', '--verbose', dest='verbose', action='store_true', default=False, help='Turn on extra logging')
    parser.add_option('-d', '--debug',   dest='debug',   action='store_true', default=False, help='Turn on debug logging')
    (options, args) = parser.parse_args()
    return options


def main():
    global opts
    opts = _parseArgs()

    if opts.debug:
        logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.DEBUG)
    elif opts.verbose:
        logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.INFO)
    else:
        logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.WARNING)


    docs = DocsSession()
    if docs == None:
        sys.exit(1)

    if opts.verbose:
        print docs.getMetadata()
    
    # Now, we can do client operations.
    
    # Examples:
    # 1. Create a folder:
    # >>> folder = gdata.docs.data.Resource(type='folder', title='Folder Name')
    # >>> folder = client.CreateResource(folder)
    #
    # 2. Create a file:
    # >>> doc = gdata.docs.data.Resource(type='document', title='I did this')
    # >>> doc = client.CreateResource(doc, collection=folder)

    #rootfolders, rootfiles = docs.readRoot()
    #for folder in rootfolders:
    #    folders, files = docs.readFolder("/" + folder)

if __name__ == "__main__":
    main()
