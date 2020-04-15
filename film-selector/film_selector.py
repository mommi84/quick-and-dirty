#!/usr/bin/env python
from __future__ import print_function
import pickle
import os.path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import json
import urllib.request
from urllib.parse import urlencode, quote_plus

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/documents.readonly']

# The ID of a sample document.
DOCUMENT_ID = '1l8FMANMlJoQo4busb9Jw3Vi9xECmdtObehuJCeliwdk'


THRESHOLD = 80

with open('omdb_api.txt') as f:
    OMDB_API = f.read().strip()


def get_ratings(title, year):

    obj = { 'apikey': OMDB_API, 't': title, 'y': year }

    url = "http://www.omdbapi.com/?" + urlencode(obj, quote_via=quote_plus)
    # print(url)

    response = urllib.request.urlopen(url)
    data = response.read()      # a `bytes` object
    details = json.loads(data.decode('utf-8'))

    imdb = None
    rt = None

    if 'Ratings' in details:
        for rat in details['Ratings']:
            if rat['Source'] == 'Internet Movie Database':
                 imdb = int(rat['Value'][:-3].replace('.', ''))

            if rat['Source'] == 'Rotten Tomatoes':
                 rt = int(rat['Value'].replace('%', ''))

    return [details['Title'], details['Year'], imdb, rt]


def main():
    """Shows basic usage of the Docs API.
    Prints the title of a sample document.
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
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    service = build('docs', 'v1', credentials=creds)

    # Retrieve the documents contents from the Docs service.
    document = service.documents().get(documentId=DOCUMENT_ID).execute()

    # print('The title of the document is: {}'.format(document.get('title')))

    body = document.get('body')
    for r in body['content']:
        if 'paragraph' in r:
            row = r['paragraph']['elements'][0]['textRun']['content'].strip()
            if row[0] == '☐':
                end = -7 if row.endswith(')') else -9
                title = row[2:end].strip()
                year = row[row.rindex('(')+1:row.rindex('(')+5]

                ratings = get_ratings(title, year)
                if ratings[3]:
                    if ratings[3] >= THRESHOLD:
                        print("\t".join([str(x) for x in ratings]))


if __name__ == '__main__':
    main()
    # print(get_ratings('War of the Worlds', 1953))
