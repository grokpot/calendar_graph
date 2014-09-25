#http://virantha.com/2013/11/14/starting-a-simple-flask-app-with-heroku/

import os
import re
from datetime import datetime, timedelta
from flask import Flask
from flask.templating import render_template
import gflags
import httplib2
from apiclient.discovery import build
from oauth2client.client import OAuth2WebServerFlow
from oauth2client.file import Storage
from oauth2client.tools import run

app = Flask(__name__)

# pip install python-gflags
FLAGS = gflags.FLAGS

# loaded from local .env file via foreman or Heroku env vars
CLIENT_ID = os.environ.get('CLIENT_ID', None)
CLIENT_SECRET = os.environ.get('CLIENT_SECRET', None)
API_KEY = os.environ.get('API_KEY', None)

FLOW = OAuth2WebServerFlow(
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    scope="https://www.googleapis.com/auth/calendar",
    redirect_uri='urn:ietf:wg:oauth:2.0:oob',
    access_type='offline', # get an access token
    approval_prompt='force'
)

# If the Credentials don't exist or are invalid, run through the native client
# flow. The Storage object will ensure that if successful the good
# Credentials will get written back to a file.
AUTH_FILE = os.path.join(os.path.dirname(__file__), 'auth.dat')
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
       developerKey=API_KEY)

## Map data structure
# date_map =
# {
#   date_object:
#     {
#       'total_time':
#         all_event_times_combined,
#       'calendars':
#         {
#           calendar_name:
#             [
#               total_calendar_event_time,
#               %_of_day
#             ]
#         }
#     }
# }
# Build date map from events then go back and average it
# BigO((calendar * event) + (calendar * average)) = O(x(y+z))

dates_map = {}
CALENDARS = ['Productive', 'Fun', 'Important', 'Other', 'Exercise', 'rprater@thinktiv.com']

def add_duration_to_date(date, duration, calendar_name):
    # Get the date for this event
    current_date_data = dates_map.get(date, {})
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
    dates_map.update({date: current_date_data})


# TODO: skip processing if date_map is cached

num_events = 0
calendars = service.calendarList().list().execute()['items'] # Read in all calendars for user
for calendar in calendars:
    calendar_name = calendar['summary']
    if calendar_name in CALENDARS:
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
                        event_start_string = re.match('(\d{4}-\d{2}-\d{2})', event.get('start').get('date')).group()
                        event_start = datetime.strptime(event_start_string, '%Y-%m-%d')
                        add_duration_to_date(event_start.date(), timedelta(hours=24), calendar_name)
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
                            add_duration_to_date(event_start.date(), event_duration, calendar_name)
                        # Events that span multiple days
                        # TODO: Don't think this is working
                        else:
                            day_count = (event_end.date() - event_start.date()).days + 1
                            for single_date in (event_start + timedelta(n) for n in range(day_count)):
                                duration = timedelta(hours=12)
                                # if it's the first day, take the difference from 12:00am tomorrow and the event start
                                if single_date.date() == event_start.date():
                                    duration = datetime.combine(event_start.date() + timedelta(days=1), datetime.min.time()) - event_start
                                # if it's the last day, take the difference from the event end and 12:am that day
                                if single_date.date() == event_end.date():
                                    duration = event_end - datetime.combine(event_end.date(), datetime.min.time())
                                add_duration_to_date(single_date.date(), duration, calendar_name)
            page_token = events.get('nextPageToken')
            if not page_token:
                break

# Iterate through calendar map and calculate percent composition of each day for each calendar
for key, current_date_data in dates_map.items():
    total_time = current_date_data['total_time']
    for cal, cal_data in current_date_data['calendars'].items():
        if total_time.total_seconds() > 0:
            # percent_of_day = (cal_data[0].total_seconds() / total_time.total_seconds()) * 100
            percent_of_day = (cal_data[0].total_seconds() / timedelta(days=1).total_seconds()) * 100
            current_date_data['calendars'][cal] = [cal_data[0], round(percent_of_day, 2)]



print "%s events were processed" % num_events

# TODO: cache date_map

# # http://stackoverflow.com/questions/5022447/converting-date-from-python-to-javascript
# @app.template_filter('date_to_millis')
# def date_to_millis(d):
#     """Converts a datetime object to the number of milliseconds since the unix epoch."""
#     return int(time.mktime(d.timetuple())) * 1000

@app.route("/")
def hello():
    return render_template('index.html', calendars=CALENDARS, dates_map=dates_map, today=datetime.today())

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
