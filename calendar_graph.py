#http://virantha.com/2013/11/14/starting-a-simple-flask-app-with-heroku/

import os
import re
from datetime import datetime
from flask import Flask
import gflags
import httplib2
from apiclient.discovery import build
from oauth2client.client import flow_from_clientsecrets
from oauth2client.file import Storage
from oauth2client.tools import run

app = Flask(__name__)

# pip install python-gflags
FLAGS = gflags.FLAGS

#https://developers.google.com/api-client-library/python/guide/aaa_oauth#flow_from_clientsecrets
# CLIENT_SECRETS is name of a file containing the OAuth 2.0 information for this
# application, including client_id and client_secret.
CLIENT_SECRETS = os.path.join(os.path.dirname(__file__), 'client_secrets.json')
AUTH_FILE = os.path.join(os.path.dirname(__file__), 'auth.dat')
FLOW = flow_from_clientsecrets(CLIENT_SECRETS, scope='https://www.googleapis.com/auth/calendar')

# If the Credentials don't exist or are invalid, run through the native client
# flow. The Storage object will ensure that if successful the good
# Credentials will get written back to a file.
storage = Storage(AUTH_FILE)
credentials = storage.get()

if credentials is None or credentials.invalid:
    credentials = run(FLOW, storage)

# Create an httplib2.Http object to handle our HTTP requests and authorize it
# with our good Credentials.
http = httplib2.Http()
http = credentials.authorize(http)

# Build a service object for interacting with the API. Visit
# the Google Developers Console
# to get a developerKey for your own application.
service = build(serviceName='calendar', version='v3', http=http,
       developerKey='AIzaSyABUruIM32B_0fRE0LtSZCRK4AxIXDcFrg')

num_events = 0
calendars = service.calendarList().list().execute()['items'] # Read in all calendars for user
for calendar in calendars:
    print "Processing calendar %s" % calendar['summary']
    page_token = None
    # Read all events per calendar
    while True:
        events = service.events().list(calendarId=calendar['id'], pageToken=page_token).execute()
        for event in events['items']:
            num_events += 1
            # Some events are cancelled, etc. and do not have times
            if event.get('start') and event.get('end'):
                # All day events
                if event.get('start').get('date') and event.get('end').get('date'):
                    print "TODO: All day events"
                else :
                    # Google may or may not append milliseconds or timezones, so split that off and return the match
                    event_start_string = re.match('(\d{4}-\d{2}-\w{5}:\d{2}:\d{2})', event.get('start').get('dateTime')).group()
                    event_end_string = re.match('(\d{4}-\d{2}-\w{5}:\d{2}:\d{2})', event.get('end').get('dateTime')).group()
                    # Now format it to a stable format
                    event_start = datetime.strptime(event_start_string, '%Y-%m-%dT%H:%M:%S')
                    event_end = datetime.strptime(event_end_string, '%Y-%m-%dT%H:%M:%S')
                    if event_end.day != event_start.day:
                        print "TODO: handle events that span days"
                    else:
                        event_duration = event_end - event_start
        page_token = events.get('nextPageToken')
        if not page_token:
            break
print "%s events were processed" % num_events

@app.route("/")
def hello():
    return "Hello world!"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
