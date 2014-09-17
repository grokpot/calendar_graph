#http://virantha.com/2013/11/14/starting-a-simple-flask-app-with-heroku/

import os
import re
from datetime import datetime, timedelta
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

## Map data structure
# date_map =
# {
#   date:
#     {
#       total_time:
#         all_event_times_combined,
#       calendars:
#         {
#           calendar_id:
#             [
#               total_calendar_event_time,
#               %_of_day
#             ]
#         }
#     }
# }
# Build date map from events then go back and average it
# BigO((calendar * event) + (calendar * average)) = O(x(y+z))

date_map = {}

def add_duration_to_date(date, duration, calendar_name):
    # Get the date for this event
    current_date_data = date_map.get(event_start.date, {})
    total_time = event_duration
    current_date_calendar_data = [event_duration, None]
    # If this date already has data
    if current_date_data:
        # Increase the total date's duration
        total_time = current_date_data.get('total_time', timedelta(0)) + event_duration
        # Get the calendar data for the current date, set calendar event time and % to zero and None if creating
        current_date_calendar_data = current_date_data.get('calendars').get(calendar_name, current_date_calendar_data)
        # Add this current event's duration to the calendar duration for that day
        current_date_calendar_data = [current_date_calendar_data[0] + event_duration, None]
    if not current_date_data.get('calendars'):
        current_date_data['calendars'] = {}
    current_date_data['calendars'][calendar_name] = current_date_calendar_data
    current_date_data['total_time'] = total_time
    date_map.update({event_start.date: current_date_data})


# TODO: skip processing if date_map is cached

num_events = 0
calendars = service.calendarList().list().execute()['items'] # Read in all calendars for user
for calendar in calendars:
    calendar_name = calendar['summary']
    print "Processing calendar %s" % calendar_name
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
                    # If it's an event contained in a single day, add its time to the map
                    if event_end.day == event_start.day:
                        event_duration = event_end - event_start
                        add_duration_to_date(event_start.date, event_duration, calendar_name)

                    # Events that span multiple days
                    else:
                        print "TODO: handle events that span days"
        page_token = events.get('nextPageToken')
        if not page_token:
            break
    print date_map
print "%s events were processed" % num_events

# TODO: cache date_map



@app.route("/")
def hello():
    return "Hello world!"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
