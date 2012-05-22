#!/usr/bin/env python

import os
import sys
import gdata.gauth
import gdata.docs.client

# OAuth 2.0 configuration data.
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

saved_auth = False
token = None

# Try to read saved auth blob.
home = os.getenv("XDG_CONFIG_HOME") 
if home == None:
    home = os.getenv("HOME")
    if home == None:
        sys.exit("Error: user home directory is not defined!")
cfgdir = os.path.join(home, CONFIG_DIR)
if os.path.exists(cfgdir):
    if not os.path.isdir(cfgdir):
        sys.exit("Error: \"%s\" exists but is not a directory!" % cfgdir)
else:
    os.makedirs(cfgdir, 0775)
tokenfile = os.path.join(cfgdir, TOKEN_FILE)
if os.path.exists(tokenfile):
    if not os.path.isfile(tokenfile):
        sys.exit("Error: path \"%s\" exists but is not a file!" % tokenfile)
    f = open(tokenfile, 'r')
    blob = f.read()
    f.close()
    if blob:
        token = gdata.gauth.token_from_blob(blob)
        if token:
            saved_auth = True

# Generate the OAuth 2.0 request token.
print "Generating the request token..."
if saved_auth:
    token = gdata.gauth.OAuth2Token(client_id=CLIENT_ID, client_secret=CLIENT_SECRET, scope=" ".join(SCOPES), user_agent=USER_AGENT, refresh_token=token.refresh_token)
else:
    token = gdata.gauth.OAuth2Token(client_id=CLIENT_ID, client_secret=CLIENT_SECRET, scope=" ".join(SCOPES), user_agent=USER_AGENT)
    
    # Authorise the OAuth 2.0 request token.
    print 'Visit the following URL in your browser to authorise this app:'
    print str(token.generate_authorize_url(redirect_url=REDIRECT_URI))
    print 'After agreeing to authorise the app, copy the verification code from the browser.'
    access_code = raw_input('Please enter the verification code: ')
    
    # Get the OAuth 2.0 Access Token.
    token.get_access_token(access_code)
    
# Save the refresh token.
if token.refresh_token and not saved_auth:
    print "Saving token..."
    f = open(tokenfile, 'w')
    blob = gdata.gauth.token_to_blob(token)
    f.write(blob)
    f.close()

# Create the Google Documents List API client.
print "Creating the Docs client..."
client = gdata.docs.client.DocsClient(source=APP_NAME)
#client.ssl = True  # Force HTTPS use.
#client.http_client.debug = True  # Turn on HTTP debugging.

# Authorise the client.
print "Authorising the Docs client API..."
client = token.authorize(client)

# Now, we can do client operations.

# Examples:
# 1. Create a folder:
# >>> folder = gdata.docs.data.Resource(type='folder', title='Folder Name')
# >>> folder = client.CreateResource(folder)
#
# 2. Create a file:
# >>> doc = gdata.docs.data.Resource(type='document', title='I did this')
# >>> doc = client.CreateResource(doc, collection=folder)

# Get the list of items in the root folder.
items = client.GetResources(uri=ROOT_FEED_URI, show_root='true')
folders = []
foldernames = []
files = []
filenames = []
for entry in items.entry:
    if entry.get_resource_type() == 'folder':
        folders.append(entry)
        foldernames.append(entry.title.text)
    else:
        files.append(entry)
        filenames.append(entry.title.text)
foldernames.sort()
for folder_name in foldernames:
    print folder_name
filenames.sort()
for filename in filenames:
    print filename
