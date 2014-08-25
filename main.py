import logging
import os

from oauth2client.appengine import oauth2decorator_from_clientsecrets
import webapp2

import bqclient
from gviz_data_table import encode
from gviz_data_table import Table

from google.appengine.api import memcache
from google.appengine.ext.webapp.template import render


CLIENT_SECRETS = os.path.join(os.path.dirname(__file__), 'client_secrets.json')
SCOPES = [
    'https://www.googleapis.com/auth/bigquery'
]
decorator = oauth2decorator_from_clientsecrets(
    filename=CLIENT_SECRETS,
    scope=SCOPES) #,
#    cache=memcache)

# Project ID for a project where you and your users
# are viewing members.  This is where the bill will be sent.
# During the limited availability preview, there is no bill.
# Replace this value with the Client ID value from your project,
# the same numeric value you used in client_secrets.json
BILLING_PROJECT_ID = "898382522207"
QUERY = (
    "SELECT "
        "INTEGER(UTC_USEC_TO_MONTH(PARSE_UTC_USEC(DateTime))/1000) AS date, "
        "City AS city, "
        "COUNT(*) AS cnt, "
        "COUNT(DISTINCT IPAddress) AS numIPs "
     "FROM "
        "[p2p_tsv_clean.2012_12],"
        "[p2p_tsv_clean.2013_01],"
        "[p2p_tsv_clean.2013_02],"
        "[p2p_tsv_clean.2013_03],"
        "[p2p_tsv_clean.2013_04],"
        "[p2p_tsv_clean.2013_05],"
        "[p2p_tsv_clean.2013_06],"
        "[p2p_tsv_clean.2013_07],"
        "[p2p_tsv_clean.2013_08],"
        "[p2p_tsv_clean.2013_09],"
        "[p2p_tsv_clean.2013_10],"
        "[p2p_tsv_clean.2013_11],"
        "[p2p_tsv_clean.2013_12]"
    "WHERE "
        "IS_EXPLICITLY_DEFINED(City) "
        "AND DateTime != 'DateTime' "
        "%s "
    "GROUP BY date, city "
    "HAVING cnt > 5 "
    "ORDER BY cnt DESC "
    "LIMIT 250")
mem = memcache.Client()

class MainPage(webapp2.RequestHandler):
    # [START bq2geo]
    def _bq2geo(self, bqdata, location):
        table = Table()
        NameDate = bqdata["schema"]["fields"][0]["name"]
        NameGeo = bqdata["schema"]["fields"][1]["name"]
        NumDownloads = bqdata["schema"]["fields"][2]["name"]
        NumIPs = bqdata["schema"]["fields"][3]["name"]
        table.add_column(NameDate, int, NameDate)
        table.add_column(NameGeo, unicode, NameGeo)
        table.add_column(NumDownloads, int, NumDownloads)
        table.add_column(NumIPs, int, NumIPs)
        for row in bqdata["rows"]:
            table.append([
                int(row["f"][0]["v"]),
                row["f"][1]["v"],
                int(row["f"][2]["v"]),
                int(row["f"][3]["v"]),
            ])
        return encode(table)
    # [END bq2geo]

    def renderPage(self, location):
        bq = bqclient.BigQueryClient(decorator)
        logging.info("l: " + location)
        extraParam = ""
        if (location != "world"):
            if '-' in location: 
                (country, region) = location.split('-')
                extraParam = (
                    "AND IS_EXPLICITLY_DEFINED(CountryCode) "
                    "AND CountryCode = '%s' "
                    "AND IS_EXPLICITLY_DEFINED(RegionCode) "
                    "AND RegionCode = '%s' "
                ) % (country, region)
            else:
                extraParam = (
                    "AND IS_EXPLICITLY_DEFINED(CountryCode) "
                    "AND CountryCode = '%s' "
                ) % (location)

        values = self._bq2geo(bq.Query(QUERY % extraParam, BILLING_PROJECT_ID), location)
        data = {'data': values,
                'locationCode': location}
        template = os.path.join(os.path.dirname(__file__), 'index.html')
        self.response.out.write(render(template, data))
    
    @decorator.oauth_required
    def get(self):
      self.renderPage("US")
      
    @decorator.oauth_required
    def post(self):
      location = self.request.get("location")
      self.renderPage(location)

application = webapp2.WSGIApplication(
    [
        ('/', MainPage),
        ('/search', MainPage),
        (decorator.callback_path, decorator.callback_handler())
    ],
    debug=True
)
