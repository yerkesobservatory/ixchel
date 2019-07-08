import logging
import re
import urllib2
import StringIO
from zipfile import ZipFile
import ephem
from astropy.coordinates import SkyCoord
import astropy.units as u
import datetime
import math
import collections

# defines a sky object data structure
SkyObject = collections.namedtuple(
    'SkyObject', 'id name type ra dec vmag tle1 tle2')
SkyObject.__new__.__defaults__ = (None,) * len(SkyObject._fields)


class Satellite:

    def __init__(self, ixchel):
        self.logger = logging.getLogger('Satellite')
        self.ixchel = ixchel
        self.config = ixchel.config
        self.db = self.buildSatelliteDatabase()
        # config the pyephem observer
        self.observer = ephem.Observer()
        self.observer.lat, self.observer.lon = '%s' % self.config.get(
            'telescope', 'latitude', '0.0'), '%s' % self.config.get('telescope', 'longitude', '0.0')
        #self.logger.debug(self.find('SBIRS GEO-4 (USA 282)'))

    def buildSatelliteDatabase(self):
        self.logger.debug('Loading satellite TLE into database...')
        norad_sats_urls = self.config.get('misc', 'norad_sat_urls').split('\n')
        db = []
        for url in norad_sats_urls:
            # grab NORAD geosat data
            # if it's a zipped file, unzip first!
            if re.search('zip$', url):
                zipfile = ZipFile(StringIO.StringIO(
                    urllib2.urlopen(url).read()))
                sats = zipfile.open(zipfile.namelist()[0]).readlines()
            else:
                try:
                    sats = urllib2.urlopen(url).readlines()
                except Exception as e:
                    self.logger.error(
                        'Failed to open satellite database (%s). Exception (%s).' % (url, e.message))
                    continue
            # clean it up
            sats = [item.strip() for item in sats]
            # create an array of name, tle1, and tle2
            sats = [(str.upper(sats[i]), sats[i+1], sats[i+2])
                    for i in xrange(0, len(sats)-2, 3)]
            # add sats to norad database
            db += sats
        self.logger.debug(
            'Loaded %d satellite TLE(s) into the database.' % len(db))
        return db

    def find(self, search_string):
        satellites = []
        for sat in self.db:
            if re.search(r'\*$', search_string):
                got_match = (sat[0].find(search_string.upper().replace('*', '')) >= 0)
            else:
                got_match = (sat[0] == search_string.upper())
            if got_match:
                name = sat[0]
                tle1 = sat[1]
                tle2 = sat[2]
                sat_ephem = ephem.readtle(name, tle1, tle2)
                self.observer.date = datetime.datetime.utcnow()
                sat_ephem.compute(self.observer)
                satellite = SkyObject(id = name, name = name, type = 'Satellite', tle1 = tle1, tle2 = tle2, ra = '%s'%sat_ephem.ra, dec = '%s'%sat_ephem.dec)
                satellites.append(satellite)
        return satellites

class Sky:
    # current object list
    sky_objects = []

    def __init__(self, ixchel):
        self.logger = logging.getLogger('Sky')
        self.ixchel = ixchel
        self.config = ixchel.config
