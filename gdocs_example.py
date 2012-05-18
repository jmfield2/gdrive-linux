#!/usr/bin/env python

import sys
import httplib2
import gdata.docs.client
import gdata.gauth

# OAuth 2.0 Lifecycle:
# 
# >>> token = gdata.gauth.OAuth2Token(client_id="351782124357.apps.googleusercontent.com", client_secret="xC3varEAS9pq--71p22oFoye", scope="https://docs.google.com/feeds/", user_agent="GDataCopier")
# >>> token.generate_authorize_url(redirect_url="urn:ietf:wg:oauth:2.0:oob")
# 'https://accounts.google.com/o/oauth2/auth?redirect_url=urn%3Aietf%3Awg%3Aoauth%3A2.0%3Aoob&scope=https%3A%2F%2Fdocs.google.com%2Ffeeds%2F&redirect_uri=oob&response_type=code&client_id=351782124357.apps.googleusercontent.com'
# >>> token.get_access_token("4/rs66xrzTNHkPsHj_0fi0ykH4Hxze")
# <gdata.gauth.OAuth2Token object at 0x109ba2510>
# >>> gd_client = gdata.docs.client.DocsClient(source='GDataCopier-v3')
# >>> token.authorize(gd_client)
# <gdata.docs.client.DocsClient object at 0x109ba2710>
# >>> gd_client.GetAllResources()
#
# Refresh Token:
# 
# >>> my_refresh_token = token.refresh_token
# >>> token2 = gdata.gauth.OAuth2Token(client_id="351782124357.apps.googleusercontent.com", client_secret="xC3varEAS9pq--71p22oFoye", scope="https://docs.google.com/feeds/", user_agent="GDataCopier", refresh_token=my_refresh_token)
# >>> gd_client2 = gdata.docs.client.DocsClient(source='GDataCopier-v3')
# >>> token2.authorize(gd_client2)

# STEP 1: Configure OAuth 2.0 data.
print "Initialising..."
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

# STEP 2: Generate the OAuth 2.0 request token.
print "Generating the request token..."
token = gdata.gauth.OAuth2Token(client_id=CLIENT_ID, client_secret=CLIENT_SECRET, scope=" ".join(SCOPES), user_agent=USER_AGENT)
print "Request token:", token

# STEP 3: Authorise the OAuth 2.0 request token.
print "Authorising the request token..."
print 'Visit the following URL in your browser to authorize this app:'
print str(token.generate_authorize_url(redirect_url=REDIRECT_URI))
print 'After agreeing to authorise the app, copy the verification code from the browser.'
access_code = raw_input('Please enter the verification code: ')

# STEP 4: Get the OAuth 2.0 Access Token.
print "Getting the access token..."
token.get_access_token(access_code)
print "Access token:", token

# STEP 5: Create the Google Documents List API client.
print "Creating the Docs client..."
client = gdata.docs.client.DocsClient(source=APP_NAME)
client.ssl = True  # Force HTTPS use.
client.http_client.debug = True  # Turn on HTTP debugging.
client.auth_token = token

# STEP 6: Authorise the client.
print "Authorising the Docs client API..."
client = token.authorize(client)

if client.auth_token:
    client_access_token = gdata.gauth.token_to_blob(client.auth_token)
    # TODO Store it somewhere.
    print "Client access token:", client_access_token

#col = gdata.docs.data.Resource(type='folder', title='Folder Name')
#col = client.CreateResource(col)

#doc = gdata.docs.data.Resource(type='document', title='I did this')
#doc = client.CreateResource(doc, collection=col)

# Create a query matching exactly a title, and include collections
q = gdata.docs.client.DocsQuery(
    title='Travel',
    title_exact='true',
    show_collections='true'
)

# Execute the query and get the first entry (if there are name clashes with
# other folders or files, you will have to handle this).
folder = client.GetResources(q=q).entry[0]

# Get the resources in the folder
contents = client.GetResources(uri=folder.content.src)

# Print out the title and the absolute link
for entry in contents.entry:
    print entry.title.text, entry.GetSelfLink().href

