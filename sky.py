import logging
import re
import urllib2
import StringIO
from zipfile import ZipFile
import ephem
from astropy.coordinates import SkyCoord, Angle
from astroquery.simbad import Simbad
import astropy.units as u
import datetime
import math
import collections
import ch  # callhorizons module customized

# defines a sky object data structure
SkyObject = collections.namedtuple(
    'SkyObject', 'id name type ra dec vmag tle1 tle2')
SkyObject.__new__.__defaults__ = (None,) * len(SkyObject._fields)

class SolarSystem:

    def __init__(self, ixchel):
        self.logger = logging.getLogger('SolarSystem')
        self.ixchel = ixchel
        self.config = ixchel.config

    def find(self, search_string): #this is a terrible scraping hack, but it's proven and comprehensive
        solarSystems = []
        suffix = '' # set to * to make the searches wider by default
        # two passes, one for major (and maybe small) and one for (only) small bodies
        search_strings = [search_string + suffix, search_string + suffix + ';']
        # list of matches
        objects = []
        for repeat in range(0, 2):
            # user JPL Horizons batch to find matches
            f = urllib2.urlopen('https://ssd.jpl.nasa.gov/horizons_batch.cgi?batch=l&COMMAND="%s"' %
                                urllib2.quote(search_strings[repeat].upper()))
            output = f.read()  # the whole enchilada
            lines = output.splitlines()  # line by line
            # no matches? go home
            if re.search('No matches found', output):
                self.logger.debug('No matches found in JPL Horizons for %s.' %
                    search_strings[repeat].upper())
            elif re.search('Target body name:', output):
                self.logger.debug('Single match found in JPL Horizons for %s.' %
                    search_strings[repeat].upper().replace(suffix, ''))
                # just one match?
                # if major body search (repeat = 0), ignore small body results
                # if major body search, grab integer id
                if repeat == 0:
                    if re.search('Small-body perts:', output):
                        continue
                    match = re.search(
                        r'Target body name:\s[a-zA-Z]+\s\((\d+)\)', output)
                    if match:
                        objects.append(match.group(1))
                    else:
                        self.logger.debug('Error. Could not parse id for single match major body (%s).' %
                            search_strings[repeat].upper().replace(suffix, ''))
                else:
                    # user search term is unique, so use it!
                    objects.append(
                        search_strings[repeat].upper().replace(suffix, ''))
            elif repeat == 1 and re.search('Matching small-bodies', output):
                self.logger.debug('Multiple small bodies found in JPL Horizons for %s.' %
                    search_strings[repeat].upper())
                # Matching small-bodies:
                #
                #    Record #  Epoch-yr  Primary Desig  >MATCH NAME<
                #    --------  --------  -------------  -------------------------
                #          4             (undefined)     Vesta
                #      34366             2000 RP36       Rosavestal
                match_count = 0
                for line in lines:
                    # look for small body list
                    match = re.search(r'^-?\d+', line.strip())
                    # parse out the small body parameters
                    if match:
                        match_count += 1
                        record_number = line[0:12].strip()
                        epoch_yr = line[12:22].strip()
                        primary_desig = line[22:37].strip()
                        match_name = line[37:len(line)].strip()
                        # add semicolon for small body search_strings
                        objects.append(record_number + ';')
                # check our parse job
                match = re.search(r'(\d+) matches\.', output)
                if match:
                    if int(match.group(1)) != match_count:
                        self.logger.debug('Multiple JPL small body parsing error!')
                    else:
                        self.logger.debug('Multiple JPL small body parsing successful!')
            elif repeat == 0 and re.search('Multiple major-bodies', output):
                self.logger.debug('Multiple major bodies found in JPL Horizons for %s.' %
                    search_strings[repeat].upper())
                # Multiple major-bodies match string "50*"
                #
                #  ID#      Name                               Designation  IAU/aliases/other
                #  -------  ---------------------------------- -----------  -------------------
                #      501  Io                                              JI
                #      502  Europa                                          JII
                match_count = 0
                for line in lines:
                    search_string = line.strip()
                    # look for major body list
                    match = re.search(r'^-?\d+', search_string)
                    # parse out the major body parameters
                    if match:
                        match_count += 1
                        record_number = line[0:9].strip()
                        # negative major bodies are spacecraft,etc. Skip those!
                        if int(record_number) >= 0:
                            name = line[9:45].strip()
                            designation = line[45:57].strip()
                            other = line[57:len(line)].strip()
                            # NO semicolon for major body search_strings
                            objects.append(record_number)
                # check our parse job
                match = re.search(r'Number of matches =([\s\d]+).', output)
                if match:
                    if int(match.group(1)) != match_count:
                        self.logger.debug('Multiple JPL major body parsing error!')
                    else:
                        self.logger.debug('Multiple JPL major body parsing successful!')
        #calculate RA/DEC
        start = datetime.datetime.utcnow()
        end = start+datetime.timedelta(seconds=60)
        for obj in objects:
            self.logger.debug(obj.upper())
            try:
                result = ch.query(obj.upper(), smallbody=False)
                result.set_epochrange(start.strftime(
                    "%Y/%m/%d %H:%M"), end.strftime("%Y/%m/%d %H:%M"), '1m')
                result.get_ephemerides(self.config.get('telescope', 'code'))
                ra = Angle('%fd' % result['RA'][0]).to_string(unit=u.hour, sep=':')
                dec = Angle('%fd' % result['DEC'][0]).to_string(
                    unit=u.degree, sep=':')
                solarSystem = SkyObject(id = obj.upper(), name = result['targetname'][0], type = 'Solar System', ra = ra, dec = dec, vmag = '%.1f'%result['V'][0])
                solarSystems.append(solarSystem) 
            except Exception as e:
                pass      
        return solarSystems

class Celestial:

    def __init__(self, ixchel):
        self.logger = logging.getLogger('Celestial')
        self.ixchel = ixchel
        self.config = ixchel.config
        Simbad.add_votable_fields('fluxdata(V)')

    def find(self, search_string):
        celestials = []
        results = Simbad.query_object(search_string.upper().replace('*', ''))
        if results != None:
            for row in range(0, len(results)):
                celestial = SkyObject(id = results['MAIN_ID'][row], name = results['MAIN_ID'][row].replace(' ', ''), type = 'Celestial', ra = results['RA'][row].replace(' ', ':'), dec = results['DEC'][row].replace(' ', ':'), vmag = '%.1f'%results['FLUX_V'][row])
                celestials.append(celestial)     
        return celestials

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
                        'Failed to open satellite database (%s). Exception (%s).' % (url, e))
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
