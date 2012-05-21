#!/usr/bin/env python

import os
import sys
import gdata.gauth
import gdata.docs.client

# OAuth 2.0 Lifecycle:
# 
# >>> token = gdata.gauth.OAuth2Token(client_id=CLIENT_ID, client_secret=CLIENT_SECRET, scope=SCOPES, user_agent=USER_AGENT)
# >>> token.generate_authorize_url(redirect_url=REDIRECT_URI)
# 'https://accounts.google.com/o/oauth2/auth?<removed>'
# >>> token.get_access_token(<access_code>)
# <gdata.gauth.OAuth2Token object at 0x109ba2510>
# >>> client = gdata.docs.client.DocsClient(source=APP_NAME)
# >>> token.authorize(client)
# <gdata.docs.client.DocsClient object at 0x109ba2710>
# >>> client.GetAllResources()
#
# Refresh Token:
# 
# >>> refresh_token = token.refresh_token
# >>> new_token = gdata.gauth.OAuth2Token(client_id=CLIENT_ID, client_secret=CLIENT_SECRET, scope=SCOPES, user_agent=USER_AGENT, refresh_token=refresh_token)
# >>> new_client = gdata.docs.client.DocsClient(source=APP_NAME)
# >>> new_token.authorize(new_client)

# Configure OAuth 2.0 data.
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

CONFIG_DIR = '.config/%s' % CLIENT_ID
TOKEN_FILE = 'token.txt' 

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
        #print "Read blob:", blob
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
    #print "Write blob:", blob
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

#col = gdata.docs.data.Resource(type='folder', title='Folder Name')
#col = client.CreateResource(col)
#doc = gdata.docs.data.Resource(type='document', title='I did this')
#doc = client.CreateResource(doc, collection=col)

# Create a query matching exactly a title, and include collections
q = gdata.docs.client.DocsQuery(show_root='true', show_collections='true')

# Execute the query and get the first entry (if there are name clashes with
# other folders or files, you will have to handle this).
#folder = client.GetResources(q=q).entry[0]
folder = client.GetResources(q=q, show_root='true')
print folder

sys.exit(0)

# Get the resources in the folder
for folder_entry in folder.entry:
    contents = client.GetResources(uri=folder_entry.content.src, show_root='true')

    # Print out the title.
    for entry in contents.entry:
        print entry.title.text
    
#entries = client.GetAllResources(uri='/feeds/default/private/full?showfolders=true')
#entries = client.GetAllResources(show_root=True)
#for entry in entries:
#    print entry.title.text, entry.get_resource_type()
#    if entry.get_resource_type() == "folder":
#        print entry.title.text

