# Copyright 2018 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# [START calendar_quickstart]
from __future__ import print_function
import datetime
import pickle
import os.path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']


def main():
    """Shows basic usage of the Google Calendar API.
    Prints the start and name of the next 10 events on the user's calendar.
    """
    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'client_secret_google_calendar.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    service = build('calendar', 'v3', credentials=creds)

    # Call the Calendar API
    beginning = "2020-01-01T00:00:00.000000Z"
    now = datetime.datetime.utcnow().isoformat() + 'Z' # 'Z' indicates UTC time
    events_result = service.events().list(calendarId='primary', timeMin=beginning, timeMax=now,
                                        singleEvents=True, orderBy='startTime').execute()
    events = events_result.get('items', [])

    id2grade = {}
    id2dinner = {}

    if not events:
        print('No events found.')
    for event in events:
        start = event['start'].get('dateTime', event['start'].get('date'))
        if 'ExcusesToEat' in event['summary']:
            # print(start, "\n".join([event['id'], event['summary'], event['description']]))
            country = event['summary'].split(' ')[0]
            flag = event['summary'].split(' ')[1]
            dinner = { 'country': country, 'flag': flag, 'date': start }
            for d in event['description'].split('\n'):
                d2 = d.split(':')
                dinner[d2[0].lower()] = float(d2[1].strip())
            id2dinner[event['id']] = dinner
            id2grade[event['id']] = dinner['score']
            # print(dinner)

    results = []
    for k in sorted(id2grade, key=id2grade.get, reverse=True):
        print(id2dinner[k])
        results.append(id2dinner[k])

    return results

if __name__ == '__main__':
    main()
# [END calendar_quickstart]
