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

# This code is part of gdrive-linux (https://code.google.com/p/gdrive-linux/).

import os, sys, logging, pickle, pprint, stat, hashlib, random, time

import gdata.gauth
import gdata.client
import gdata.docs.client

from drive_config import DriveConfig
from dirtree import DirectoryTree
import progressbar


class Session(object):

    def __init__(self, verbose=False, debug=False, logger=None):
        "Class constructor."
        self._debug = debug
        self._verbose = verbose
        self._config = DriveConfig(verbose, debug, logger)

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
        self._config.checkLocalRoot()

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
        tokenfile = self._config.getTokenFile()
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
            self._token = gdata.gauth.OAuth2Token(client_id=self._config.CLIENT_ID,
                                                  client_secret=self._config.CLIENT_SECRET,
                                                  scope=" ".join(self._config.SCOPES),
                                                  user_agent=self._config.USER_AGENT,
                                                  refresh_token=self._token.refresh_token)
        else:
            self._token = gdata.gauth.OAuth2Token(client_id=self._config.CLIENT_ID,
                                                  client_secret=self._config.CLIENT_SECRET,
                                                  scope=" ".join(self._config.SCOPES),
                                                  user_agent=self._config.USER_AGENT)

            # Authorise the OAuth 2.0 request token.
            print 'Visit the following URL in your browser to authorise this app:'
            print str(self._token.generate_authorize_url(redirect_url=self._config.REDIRECT_URI))
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
        self._client = gdata.docs.client.DocsClient(source=self._config.APP_NAME)
        #client.ssl = True  # Force HTTPS use.
        #client.http_client.debug = True  # Turn on HTTP debugging.

        # Authorise the client.
        logging.info("Authorising the Docs client API...")
        self._client = self._token.authorize(self._client)

    # Wrapper for gdata.docs.client.GetAllResources.
    def _getAllResources(self, uri):
        "Get all resources, with exponential backoff and retry." 
        for n in range(0, 5):
            try:
                items = self._client.GetAllResources(uri=uri)
                return items
            except:
                time.sleep((2 ** n) + (random.randint(0, 1000) / 1000))
        logging.fatal("An error occurred contacting the Google servers, the request never succeeded, aborting.")
        return None
    
    # Wrapper for gdata.docs.client.GetResourceById.
    def _getResourceById(self, res_id, show_root=True):
        "Get resource by ID, with exponential backoff and retry." 
        for n in range(0, 5):
            try:
                resource = self._client.GetResourceById(res_id, show_root=show_root)
                return resource
            except:
                time.sleep((2 ** n) + (random.randint(0, 1000) / 1000))
        logging.fatal("An error occurred contacting the Google servers, the request never succeeded, aborting.")
        return None
    
    # Wrapper for gdata.docs.client.GetResourceBySelfLink.
    def _getResourceBySelfLink(self, href, show_root=True):
        "Get resource by self link, with exponential backoff and retry." 
        for n in range(0, 5):
            try:
                resource = self._client.GetResourceBySelfLink(href, show_root=show_root)
                return resource
            except:
                time.sleep((2 ** n) + (random.randint(0, 1000) / 1000))
        logging.fatal("An error occurred contacting the Google servers, the request never succeeded, aborting.")
        return None
    
    # Wrapper for gdata.docs.client.GetChanges.
    def _getChanges(self, changestamp=None, max_results=100, show_root=True):
        "Get a change feed, with exponential backoff and retry." 
        for n in range(0, 5):
            try:
                feed = self._client.GetChanges(changestamp, max_results, show_root)
                return feed
            except:
                time.sleep((2 ** n) + (random.randint(0, 1000) / 1000))
        logging.fatal("An error occurred contacting the Google servers, the request never succeeded, aborting.")
        return None

    # Wrapper for gdata.docs.client.GetNext.
    def _getNext(self, feed):
        "Get next chink of entries from feed, with exponential backoff and retry." 
        for n in range(0, 5):
            try:
                feed = self._client.GetNext(feed)
                return feed
            except:
                time.sleep((2 ** n) + (random.randint(0, 1000) / 1000))
        logging.fatal("An error occurred contacting the Google servers, the request never succeeded, aborting.")
        return None

    # Wrapper for gdata.docs.client.GetRevisions.
    def _getRevisions(self, resource):
        "Get a revisions feed, with exponential backoff and retry." 
        for n in range(0, 5):
            try:
                revisions = self._client.GetRevisions(resource)
                return revisions
            except gdata.client.Unauthorized:
                logging.warn("Unauthorised error on resource")
                return None
            except:
                time.sleep((2 ** n) + (random.randint(0, 1000) / 1000))
        logging.fatal("An error occurred contacting the Google servers, the request never succeeded, aborting.")
        return None

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
            uri = self._config.ROOT_FEED_URI
        else:
            if path in self._metadata["map"]["bypath"]:
                uri = self._metadata["map"]["bypath"][path]["uri"]
            else:
                # TODO: try to handle this better.
                logging.error("Path \"%s\" is unknown!" % path)
                raise KeyError
        return uri

    def _pathToResourceId(self, path):
        "Get the resource ID for a path."
        root = self._config.getLocalRoot()
        if path.startswith(root):
            path = path[len(root):]
        if path == '/':
            res_id = "folder:root"
        else:
            if path in self._metadata["map"]["bypath"]:
                res_id = self._metadata["map"]["bypath"][path]["resource_id"]
            else:
                # TODO: try to handle this better.
                logging.error("Path \"%s\" is unknown!" % path)
                raise KeyError
        return res_id

    def _readFolder(self, path):
        "Read the contents of a folder."
        logging.debug("Reading folder \"%s\"" % path)
        uri = self._pathToUri(path)
        items = self._getAllResources(uri)
        folders = []
        files = []
        for entry in items:
            itempath = os.path.join(path, entry.title.text)
            itemid = entry.resource_id.text
            item = { "path": itempath,
                     "resource_id": itemid,
                     "uri": entry.content.src,
                     "size": entry.quota_bytes_used.text }
            item["shared"] = "false"
            if entry.get_resource_type() == 'folder':
                item["type"] = "folder"
                folders.append(itempath)
            else:
                files.append(itempath)
                item["type"] = "file"
                logging.debug("Getting metadata for path %s" % itempath)
                metadata = self._getResourceMetadata(entry)
                if metadata:
                    item.update(metadata)
                else:
                    logging.warn("No metadata found for path %s, assuming shared resource" % itempath)
                    item["shared"] = "true"
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
        metafile = self._config.getMetadataFile()
        if os.path.exists(metafile):
            logging.debug("Reading cached metadata...")
            f = open(metafile, 'rb')
            self._metadata = pickle.load(f)
            f.close()
            return True
        return False

    def _save(self):
        "Save metadata to local file."
        metafile = self._config.getMetadataFile()
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
        elif path == '/':
            return True
        else:
            # TODO: Handle this better. Raise an exception?
            return False
            #sys.exit("Error: path \"%s\" is unknown!" % path)

    def isFile(self, path):
        "Return true if the specified path is a file."
        return not self.isFolder(path)

    def _getResourceMetadata(self, resource):
        metadata = {}
        revisions = self._getRevisions(resource)
        if revisions == None or len(revisions.entry) == 0:
            logging.warn("No revisions found for resource!")
            return None
        revision = revisions.entry[0]
        metadata["author"] = ""
        metadata["email"] = ""
        if len(revision.author) > 0:
            metadata["author-name"] = revision.author[0].name.text
            metadata["author-email"] = revision.author[0].email.text
        metadata["updated"] = revision.updated.text
        for child in revision.children:
            if child.tag == "edited":
                metadata["edited"] = child.text
            if child.tag == "md5Checksum":
                metadata["md5checksum"] = child.text
        return metadata

    def getRemoteFileAuthor(self, path):
        "Return the author of the specified remote path, if it is a file."
        author = {}
        if not self.isFolder(path):
            if path.startswith(self._config.getLocalRoot()):
                path = self._config.getRemotePath(path)
            try:
                author["name"] = self._metadata["map"]["bypath"][path]["author-name"]
                author["email"] = self._metadata["map"]["bypath"][path]["author-email"]
            except KeyError:
                author["name"] = None
                author["email"] = None
        return author

    def getLocalFileDate(self, path):
        "Return the last modified date of the specified local path, if it is a file."
        date = None
        if os.path.exists(path) and not os.path.isdir(path):
            size = os.path.getmtime(path)
        return date

    def getRemoteFileDate(self, path):
        "Return the last modified date of the specified remote path, if it is a file."
        date = None
        if not self.isFolder(path):
            if path.startswith(self._config.getLocalRoot()):
                path = self._config.getRemotePath(path)
            try:
                date = self._metadata["map"]["bypath"][path]["updated"]
            except KeyError:
                pass
        return date

    def getFileDate(self, path):
        "Return the last modified date of the specified local or remote path, if it is a file."
        date = None
        if os.path.exists(path):
            date = self.getLocalFileDate(path)
        else:
            date = self.getRemoteFileDate(path)
        return date

    def getLocalFileSize(self, path):
        "Return the size in bytes of the specified local path, if it is a file."
        size = 0
        if os.path.exists(path) and not os.path.isdir(path):
            size = os.path.getsize(path)
        return size

    def getRemoteFileSize(self, path):
        "Return the size in bytes of the specified remote path, if it is a file."
        size = 0
        if not self.isFolder(path):
            if path.startswith(self._config.getLocalRoot()):
                path = self._config.getRemotePath(path)
            try:
                size = int(self._metadata["map"]["bypath"][path]["size"])
            except KeyError:
                pass
        return size

    def getFileSize(self, path):
        "Return the size in bytes of the specified local or remote path, if it is a file."
        size = 0
        if os.path.exists(path):
            size = self.getLocalFileSize(path)
        else:
            size = self.getRemoteFileSize(path)
        return size

    def getLocalFileChecksum(self, path):
        "Return the MD5 checksum of the specified local path, if it is a file."
        checksum = None
        logging.debug("Getting MD5 for %s..." % path)
        if os.path.exists(path) and not os.path.isdir(path):
            f = open(path, 'rb')
            m = hashlib.md5()
            while True:
                data = f.read(64 * 1024)
                if not data:
                    break
                m.update(data)
            checksum = m.hexdigest()
        return checksum

    def getRemoteFileChecksum(self, path):
        "Return the MD5 checksum of the specified remote path, if it is a file."
        checksum = None
        logging.debug("Getting MD5 for %s..." % path)
        if not self.isFolder(path):
            if path.startswith(self._config.getLocalRoot()):
                path = self._config.getRemotePath(path)
            if path not in self._metadata["map"]["bypath"] or "md5checksum" not in self._metadata["map"]["bypath"][path]:
                shared = None
                try:
                    shared = self._metadata["map"]["bypath"][path]["shared"]
                except KeyError:
                    # This will really only happen if the metadata is from an old version of the app.
                    pass
                if shared:
                    return None
                parent = '/' + '/'.join(path.split('/')[:-2])
                self._readFolder(parent)
            try:
                checksum = self._metadata["map"]["bypath"][path]["md5checksum"]
            except KeyError:
                logging.error("Path \"%s\" is not recognised!" % path)
        return checksum

    def getFileChecksum(self, path):
        "Return the MD5 checksum of the specified local or remote path, if it is a file."
        checksum = None
        if os.path.exists(path):
            checksum = self.getLocalFileChecksum(path)
        else:
            checksum = self.getRemoteFileChecksum(path)
        return checksum

    def _getLargestChangestamp(self):
        "Returns the largest changestamp."
        metadict = self.getMetadata()
        logging.debug("Max changestamp: %d" % metadict["changestamp"])
        return metadict["changestamp"]

    def _getChangeList(self, changestamp=0):
        "Get a list of resource IDs that have changed since the specified changestamp."
        changes = []
        resource_ids = []
        if changestamp == 0:
            logging.debug("Getting all changes...")
            feed = self._getChanges(max_results=self._config.MAX_RESULTS, show_root=True)
        else:
            logging.debug("Getting changes since changestamp=%s..." % changestamp)
            feed = self._getChanges(changestamp=str(changestamp), max_results=self._config.MAX_RESULTS, show_root=True)
        if feed:
            changes.extend(feed.entry)
        while feed and len(feed.entry) == self._config.MAX_RESULTS:
            feed = self._getNext(feed)
            changes.extend(feed.entry)
        if len(changes) > 0:
            # Save a changestamp of one beyond the last.
            self._metadata["changestamp"] = int(changes[-1].changestamp.value) + 1
            logging.debug("Got %d changes, last changestamp is %d" % (len(changes), self._metadata["changestamp"]))
            for change in changes:
                resource_ids.append(change.resource_id.text)
        else:
            logging.debug("No changes found")
        return resource_ids

    def update(self, path='/', download=False, interactive=True):
        "Update the local tree at the specified path to match the server."
        logging.debug("Updating %s ..." % path)
        localpath = self._config.getLocalPath(path)
        if path == '/' or not os.path.exists(localpath):
            logging.debug("Local copy does not exist, fetching...")
            self.download(path, localpath, overwrite=True, interactive=interactive)
        else:
            # Request change feed from the last changestamp.
            # If no stored changestamp, then start at the beginning.
            if self._metadata["changestamp"] == 0:
                logging.debug("Stored changestamp is zero, walking the tree...")
                self._metadata["changestamp"] = self._getLargestChangestamp() + 1
                self._walk(root=path)
                if download:
                    self.download(path, localpath, overwrite=True, interactive=interactive)
            # Now check for changes again, since before we walked.
            resource_ids = self._getChangeList(self._metadata["changestamp"])
            if len(resource_ids) > 0:
                # Iterate over the changes, downloading each resource.
                for res_id in resource_ids:
                    res_path = self._resourceIdToPath(res_id)
                    if res_path == None:
                        logging.debug("No local path for resource ID %s" % res_id)
                        # The resource is not in our cache.
                        resource = self._getResourceById(res_id, show_root=True)
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
                            logging.debug("parent: %s" % parent.href)
                            if parent.href == self._config.ROOT_FOLDER_HREF:
                                logging.debug("Parent is root folder")
                                top_path = '/'
                            else:
                                parent_resource = self._getResourceBySelfLink(parent.href, show_root=True)
                                parent_resid = parent_resource.resource_id.text
                                logging.debug("Parent resource ID %s" % parent_resid)
                                parent_resids = [parent_resid]
                                while parent_resid not in self._metadata["map"]["byid"]:
                                    logging.debug("Parent resource ID %s not in cache" % parent_resid)
                                    parent = parent.InCollections()
                                    parent_resource = self._getResourceBySelfLink(parent.href, show_root=True)
                                    parent_resid = parent_resource.resource_id.text
                                    parent_resids.insert(0, parent_resid)
                                top_path = self._resourceIdToPath(parent_resid)
                                logging.debug("Found parent path %s in cache for resource ID %s" % (top_path, parent_resid))
                            self._walk(top_path)
                            # Download the top_path subtree here.
                            if download:
                                self.download(top_path, self._config.getLocalPath(top_path), overwrite=True, interactive=interactive)
                        res_path = self._resourceIdToPath(res_id)
                        if res_path == None:
                            logging.warn("No parent path found, must be a shared resource, skipping...")
                            continue
                    # Check if resource path is in the path specified.
                    if res_path.startswith(path):
                        logging.debug("Get resource %s (%s)" % (res_id, res_path))
                        if download:
                            self.download(res_path, self._config.getLocalPath(res_path), overwrite=True, interactive=interactive)
                    else:
                        logging.debug("Ignoring change to path %s, not in target path %s" % (res_path, path))
        self._save()

    def getNumResources(self, path=None):
        "Returns the total number of resources (files, folders) in the specified path, and all subtrees."
        return len(self._metadata["map"]["bypath"].keys(path))

    def getNumRemoteFolders(self, path=None):
        "Returns the total number of folders in the specified remote path, and all subtrees."
        count = 0
        if path == '/':
            values = self._metadata["map"]["bypath"].itervalues()
        else:
            values = self._metadata["map"]["bypath"].itervalues(path)
        for value in values:
            if value["type"] == "folder":
                count += 1
        return count

    def getNumRemoteFiles(self, path=None):
        "Returns the total number of files in the specified remote path, and all subtrees."
        count = 0
        if path == '/':
            values = self._metadata["map"]["bypath"].itervalues()
        else:
            values = self._metadata["map"]["bypath"].itervalues(path)
        for value in values:
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
        entry = None
        if path != '/':
            entry = self._getResourceById(self._pathToResourceId(path))
            if not entry:
                logging.error("Failed to download path \"%s\"" % path)
                return False
        if self.isFolder(path):
            if not self._config.checkLocalFolder(localpath, overwrite):
                logging.error("Cannot overwrite local path \"%s\", exiting!" % localpath)
                return
            logging.info("Downloading folder %s (%d of %d)..." % (localpath, self._folder_count, self._num_folders))
            (folders, files) = self._readFolder(path)
            for fname in files:
                lpath = os.path.join(localpath, os.path.basename(fname))
                self._download(fname, lpath, overwrite)
                self._file_count += 1
            for folder in folders:
                lpath = os.path.join(localpath, os.path.basename(folder))
                self._download(folder, lpath, overwrite)
            self._folder_count += 1
        else:
            logging.info("Downloading file %s (%d bytes) (%d of %d)..." % (localpath, self.getRemoteFileSize(path), self._file_count, self._num_files))
            if self._bar:
                self._bar.render(self._file_count * 100 / self._num_files, localpath)
            if not self._config.checkLocalFile(localpath, overwrite):
                return False
            self._client.DownloadResource(entry, localpath)
            os.chmod(localpath, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
        return True

    def download(self, path, localpath=None, overwrite=False, interactive=False):
        "Download a file or a folder tree."
        self._folder_count = 1
        self._num_folders = self.getNumRemoteFolders(path)
        self._file_count = 1
        self._num_files = self.getNumRemoteFiles(path)
        if interactive:
            if self._num_folders + self._num_files > 2:
                self._bar = progressbar.ProgressBar(width=80)
        if localpath is None:
            localpath = self._config.getLocalPath(path)
            logging.debug("Using local path %s" % localpath)
        for exclude in self._config.getExcludes():
            if path == '/' + exclude:
                logging.debug("Skipping folder on exclude list")
                return
        self._download(path, localpath, overwrite)
        self._folder_count = 0
        self._file_count = 0

    def _upload(self, localpath, path):
        "Upload a file."

	# http://planzero.org/blog/2012/04/13/uploading_any_file_to_google_docs_with_python

	# The default root collection URI
	uri = 'https://docs.google.com/feeds/upload/create-session/default/private/full'

	# if collection path is set
	if path <> "/":
		resources = self._client.GetAllResources(uri='https://docs.google.com/feeds/default/private/full/-/folder?title=' + path + '&title-exact=true')

		uri = resources[0].get_resumable_create_media_link().href
	
	# Make sure Google doesn't try to do any conversion on the upload (e.g. convert images to documents)
	uri += '?convert=false'

	# Create an uploader and upload the file
	# Hint: it should be possible to use UploadChunk() to allow display of upload statistics for large uploads
	t1 = time.time()

	fh = open(localpath)
	import magic
	import atom
	file_type = magic.Magic(mime=True).from_file(fh.name)
	file_size = os.path.getsize(fh.name)

	logging.info("Uploading...")
	uploader = gdata.client.ResumableUploader(self._client, fh, file_type, file_size, chunk_size=1048576, desired_class=gdata.data.GDEntry)
	res = uploader.UploadFile(uri, entry=gdata.data.GDEntry(title=atom.data.Title(text=os.path.basename(fh.name))))

	logging.info('Uploaded', '{0:.2f}'.format(file_size / 1024 / 1024) + ' MiB in ' + str(round(time.time() - t1, 2)) + ' seconds')
	logging.info("Created: %s" % res)

        #logging.error("Upload is not yet implemented!")

    def upload(self, localpath, path=None, interactive=False):
        "Upload a file or a folder tree."
        if path is None:
            if localpath.startswith(self._config.getLocalRoot()):
                path = localpath[len(self._config.getLocalRoot()):]
            else:
                path = '/'
        self._folder_count = 1
        self._num_folders = self.getNumLocalFolders(path)
        self._file_count = 1
        self._num_files = self.getNumLocalFiles(path)
        if interactive:
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

    def dump(self):
        "Dump metadata."
        pprint.pprint(self._metadata, indent=2)

    def filestatus(self, path, interactive=False):
        "Get the status of a file."
        res_id = self._pathToResourceId(path)
        resource = self._getResourceById(res_id, show_root=True)
        if not resource:
            logging.error("Failed to get resource \"%s\"" % res_id)
        return self._getResourceMetadata(resource)
