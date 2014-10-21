#http://virantha.com/2013/11/14/starting-a-simple-flask-app-with-heroku/
import json

import os
import re
from datetime import datetime, timedelta, date
from flask import Flask
from flask.templating import render_template
import gflags
import httplib2
from apiclient.discovery import build
from oauth2client.client import OAuth2WebServerFlow, OAuth2Credentials
from oauth2client.file import Storage
from oauth2client.tools import run

app = Flask(__name__)

# Read foreman environment variables into context (only really needed for dev environment)
def read_env():
    """Pulled from Honcho code with minor updates, reads local default
    environment variables from a .env file located in the project root
    directory.
    http://www.wellfireinteractive.com/blog/easier-12-factor-django/
    """
    try:
        with open(os.path.join(os.path.dirname(__file__), '.env')) as f:
            content = f.read()
    except IOError:
        content = ''

    for line in content.splitlines():
        m1 = re.match(r'\A([A-Za-z_0-9]+)=(.*)\Z', line)
        if m1:
            key, val = m1.group(1), m1.group(2)
            m2 = re.match(r"\A'(.*)'\Z", val)
            if m2:
                val = m2.group(1)
            m3 = re.match(r'\A"(.*)"\Z', val)
            if m3:
                val = re.sub(r'\\(.)', r'\1', m3.group(1))
            os.environ.setdefault(key, val)

# pip install python-gflags
FLAGS = gflags.FLAGS

read_env()
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
credentials_json = json.loads(os.environ.get('CREDENTIALS'))
if credentials_json:
    # build OAuth credentials from environment vars
    credentials = OAuth2Credentials(credentials_json['access_token'],
                                credentials_json['client_id'], # Client ID
                                credentials_json['client_secret'],
                                credentials_json['refresh_token'],
                                credentials_json['token_expiry'], # token expiry
                                credentials_json['token_uri'],
                                'bullshit_user_agent')
else:
    AUTH_FILE = os.path.join(os.path.dirname(__file__), 'auth.dat')
    auth_storage = Storage(AUTH_FILE)
    credentials = run(FLOW, auth_storage)

# Create an httplib2.Http object to handle our HTTP requests and authorize it
# with our good Credentials.
http = httplib2.Http()
http = credentials.authorize(http)

# Build a service object for interacting with the API. Visit
# the Google Developers Console
# to get a developerKey for your own application.
service = build(serviceName='calendar', version='v3', http=http, developerKey=API_KEY)

## Map data structure
# date_map =
# {
#   date_object:
#     {
#       'total_time': all_event_times_combined_in_seconds,
#       'calendars':
#         {
#           calendar_name: total_calendar_event_time_in_seconds,
#         }
#     }
# }
dates_map = {}
CALENDARS = ['Productive', 'Fun', 'Important', 'Exercise', 'rprater@thinktiv.com']

def add_duration_to_date(current_date, duration, calendar_name):
    # Get the date for this event
    current_date_data = dates_map.get(current_date, {})
    total_time = duration.total_seconds()
    calendar_time = duration.total_seconds()
    # If this date already has data
    if current_date_data:
        # Increase the total date's duration
        total_time += current_date_data.get('total_time', 0)
        # Get the time spent on this day for this calendar and add the duration of the current event
        calendar_time += current_date_data.get('calendars').get(calendar_name, 0)
    if not current_date_data.get('calendars'):
        current_date_data['calendars'] = {}
    current_date_data['total_time'] = total_time
    current_date_data['calendars'][calendar_name] = calendar_time
    dates_map.update({current_date: current_date_data})

num_events = 0
calendars = service.calendarList().list().execute()['items']  # Read in all calendars for user
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
                    # All day events (date objects)
                    if event.get('start').get('date') and event.get('end').get('date'):
                        event_start_string = re.match('(\d{4}-\d{2}-\d{2})', event.get('start').get('date')).group()
                        event_start = datetime.strptime(event_start_string, '%Y-%m-%d')
                        event_end_string = re.match('(\d{4}-\d{2}-\d{2})', event.get('end').get('date')).group()
                        # subtract a day because if an all day event ends at midnight, google returns the following date
                        event_end = datetime.strptime(event_end_string, '%Y-%m-%d') - timedelta(days=1)
                    # Events with times (datetime objects)
                    else:
                        # Google may or may not append milliseconds or timezones, so split that off and return the match
                        event_start_string = re.match('(\d{4}-\d{2}-\w{5}:\d{2}:\d{2})', event.get('start').get('dateTime')).group()
                        event_end_string = re.match('(\d{4}-\d{2}-\w{5}:\d{2}:\d{2})', event.get('end').get('dateTime')).group()
                        # Now format it to a stable format
                        event_start = datetime.strptime(event_start_string, '%Y-%m-%dT%H:%M:%S')
                        event_end = datetime.strptime(event_end_string, '%Y-%m-%dT%H:%M:%S')
                    # # Debug tool for watching specific events
                    if event_start.date() == date(2013, 10, 29) and calendar_name == "Fun":
                        pass
                    # Event is contained in a single day
                    if event_end.day == event_start.day:
                        event_duration = event_end - event_start
                        add_duration_to_date(event_start.date(), event_duration, calendar_name)
                    # Events that span multiple days
                    else:
                        day_count = (event_end.date() - event_start.date()).days + 1
                        for single_date in (event_start + timedelta(n) for n in range(day_count)):
                            event_duration = timedelta(hours=12)
                            # if it's the first day, take the difference from 12:00am tomorrow and the event start
                            if single_date.date() == event_start.date():
                                event_duration = datetime.combine(event_start.date() + timedelta(days=1), datetime.min.time()) - event_start
                            # if it's the last day, take the difference from the event end and 12:am that day
                            elif single_date.date() == event_end.date():
                                event_duration = event_end - datetime.combine(event_end.date(), datetime.min.time())
                            # We only want to record 12 hours for events that last all day
                            if event_duration == timedelta(days=1):
                                event_duration = timedelta(hours=12)
                            add_duration_to_date(single_date.date(), event_duration, calendar_name)
            page_token = events.get('nextPageToken')
            if not page_token:
                break
print "%s events were processed" % num_events

@app.route("/")
def hello():
    return render_template('index.html', calendars=CALENDARS, dates_map=dates_map, today=datetime.today())

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
