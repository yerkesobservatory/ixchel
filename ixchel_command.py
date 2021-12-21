# -*- coding: utf-8 -*-

import threading
import os
import pathlib2
from matplotlib.colors import LogNorm
import matplotlib.pyplot as plt
import logging
import re
import requests
import time
import datetime
import pytz
from globals import doAbort
from telescope_interface import TelescopeInterface
from astropy.coordinates import SkyCoord, Angle, AltAz
import astropy.units as u
from astropy.time import Time
from astropy.utils.data import get_pkg_data_filename
from astropy.io import fits
from sky import Satellite, Celestial, SolarSystem, Coordinate
import json
import random
import string
from pathlib import PurePosixPath
import numpy as np
import matplotlib
matplotlib.use('Agg')  # don't need display

find_format_string = \
    """[
	{{
		"type": "section",
		"fields": [
     		{{
				"type": "mrkdwn",
				"text": "*{Index}*. `Name`: {Name}"
            }},
            {{
				"type": "mrkdwn",
				"text": "`Type:` {Type}"
			}},
			{{
				"type": "mrkdwn",
				"text": "`RA/DEC:` {RA}/{DEC}"
			}},
  			{{
				"type": "mrkdwn",
				"text": "`Altitude:` {Altitude}"
			}},
    		{{
				"type": "mrkdwn",
				"text": "`Azimuth:` {Azimuth}"
			}},
            {{
				"type": "mrkdwn",
				"text": "`Magnitude (V):` {V}"
			}}
		]
	}}
]"""


class CommandThread:

    def __init__(self, thread, command, user):
        self.thread = thread
        self.command = command
        self.user = user


class IxchelCommand:

    commands = []
    skyObjects = []
    threads = []

    def __init__(self, ixchel):
        self.logger = logging.getLogger('IxchelCommand')
        self.ixchel = ixchel
        self.config = ixchel.config
        self.lock = ixchel.lock
        self.channel = self.config.get('slack', 'channel_name')
        self.bot_name = self.config.get('slack', 'bot_name')
        self.slack = ixchel.slack
        self.telescope = ixchel.telescope
        self.image_dir = self.config.get(
            'telescope', 'image_dir')
        # session states to save
        self.hdr = False
        self.share = False
        self.target = 'unknown'
        self.preview = True
        # build list of backslash commands
        self.init_commands()
        # init the Sky interface
        self.satellite = Satellite(ixchel)
        self.celestial = Celestial(ixchel)
        self.solarSystem = SolarSystem(ixchel)
        self.coordinate = Coordinate(ixchel)

    def resetSession(self):
        self.hdr = False
        self.share = False
        self.target = 'unknown'
        self.preview = True

    def set_target(self, target='unknown'):
        self.target = target.strip().lower()  # lower case
        # replace non-alphanumerics
        self.target = re.sub('[^A-Za-z0-9\+\-]', '_', self.target)

    def parse(self, message):
        text = message['text'].strip()
        for cmd in self.commands:
            command = re.search(cmd['regex'], text, re.IGNORECASE)
            if command:
                user = self.slack.get_user_by_id(message.get('user'))
                self.logger.info('Received the command: %s from %s.' % (
                    command.group(0), user.get('name')))
                try:
                    if 'lock' in cmd and cmd['lock'] == True and not self.is_locked_by(user) and not self.share:
                        self.slack.send_message(
                            'Please lock the telescope before calling this command.')
                        return
                    # clean up threads
                    self.threads = [
                        t for t in self.threads if t.thread.is_alive()]
                    # is this an abort command?
                    if cmd['function'] == self.abort:
                        # are there any threads to abort?
                        if len(self.threads) <= 0:
                            self.slack.send_message(
                                'No commands to abort.')
                            self.setDoAbort(False)
                            return
                        self.slack.send_message(
                            'Aborting current command (%s). Please wait...' % (self.threads[0].command))
                        self.setDoAbort(True)  # signal the abort
                        return
                    if len(self.threads) > 0:  # not an /abort, but there is another command running
                        self.slack.send_message(
                            'Please wait for the current command (%s) to complete.' % (self.threads[0].command))
                        return
                    # run this command in a thread
                    thread = threading.Thread(
                        target=cmd['function'], args=(command, user,), daemon=True)
                    commandThread = CommandThread(
                        thread, command.group(0), user.get('name'))
                    self.threads.append(commandThread)
                    thread.start()
                    # cmd['function'](command, user)
                except Exception as e:
                    self.handle_error(command.group(0), 'Exception (%s).' % e)
                return
        self.slack.send_message(
            '%s does not recognize your command (%s).' % (self.bot_name, text))

    def handle_error(self, command, error):
        self.logger.error('Command failed (%s). %s' % (command, error))
        self.slack.send_message('Error. Command (%s) failed.' % command)

    def track(self, command, user):
        try:
            telescope_interface = TelescopeInterface('track')
            # assign values
            on_off = command.group(1)
            telescope_interface.set_input_value('on_off', on_off)
            # create a command that applies the specified values
            self.telescope.track(telescope_interface)
            self.slack.send_message(
                'Telescope tracking is %s.' % on_off.strip().lower())
        except Exception as e:
            self.handle_error(command.group(0), 'Exception (%s).' % e)

    def offset(self, command, user):
        try:
            dRA = command.group(1).strip()
            dDEC = command.group(2).strip()
            self.slack.send_message('%s is offsetting the telescope by dRA=%s/dDEC=%s. Please wait...' %
                                    (self.config.get('slack', 'bot_name'), dRA, dDEC))
            telescope_interface = TelescopeInterface('offset')
            # assign values
            telescope_interface.set_input_value('dRA', dRA)
            telescope_interface.set_input_value('dDEC', dDEC)
            # create a command that applies the specified values
            self.telescope.point(telescope_interface)
            # send output to Slack
            self.slack.send_message(
                'Telescope successfully offset by dRA=%s/dDEC=%s.' % (dRA, dDEC))
        except Exception as e:
            self.handle_error(command.group(0), 'Exception (%s).' % e)

    def point_ra_dec(self, command, user):
        try:
            self.set_target()
            ra = command.group(1).strip()
            dec = command.group(2).strip()
            self.slack.send_message('%s is pointing the telescope to RA=%s/DEC=%s. Please wait...' %
                                    (self.config.get('slack', 'bot_name'), ra, dec))
            # turn on telescope tracking
            telescope_interface = TelescopeInterface('track')
            telescope_interface.set_input_value('on_off', 'on')
            self.telescope.track(telescope_interface)
            # point the telescope
            telescope_interface = TelescopeInterface('point')
            # assign values
            telescope_interface.set_input_value('ra', ra)
            telescope_interface.set_input_value('dec', dec)
            # create a command that applies the specified values
            self.telescope.point(telescope_interface)
            # send output to Slack
            self.slack.send_message(
                'Telescope successfully pointed to RA=%s/DEC=%s.' % (ra, dec))
            # regex to format RA/dec for filename
            _ra = re.sub('^(\d{1,2}):(\d{2}):(\d{2}).+', r'\1h\2m\3s', ra)
            _dec = re.sub('(\d{1,2}):(\d{2}):(\d{2}).+', r'\1d\2m\3s', dec)
            self.set_target('%s%s' % (_ra, _dec))
        except Exception as e:
            self.handle_error(command.group(0), 'Exception (%s).' % e)

    def point(self, command, user):
        try:
            # get object id; assume 1 if none
            if command.group(1):
                id = int(command.group(1).strip())
            else:
                id = 1
            # ensure object id is valid
            if id < 1 or id > len(self.skyObjects):
                self.slack.send_message('%s does not recognize the object id (%d). Run \\find first!' % (
                    self.config.get('slack', 'bot_name'), id))
                return
            self.set_target()
            # find corresponding object
            skyObject = self.skyObjects[id-1]
            self.slack.send_message('%s is pointing the telescope to "%s". Please wait...' % (
                self.config.get('slack', 'bot_name'), skyObject.name))
            # turn on telescope tracking
            telescope_interface = TelescopeInterface('track')
            telescope_interface.set_input_value('on_off', 'on')
            self.telescope.track(telescope_interface)
            # point the telescope
            telescope_interface = TelescopeInterface('point')
            # assign values
            telescope_interface.set_input_value('ra', skyObject.ra)
            telescope_interface.set_input_value('dec', skyObject.dec)
            # create a command that applies the specified values
            self.telescope.point(telescope_interface)
            # send output to Slack
            self.slack.send_message(
                'Telescope successfully pointed to %s.' % skyObject.name)
            self.set_target(skyObject.name)
        except Exception as e:
            self.handle_error(command.group(0), 'Exception (%s).' % e)

    def _pinpoint(self, _user, ra, dec):
        # astrometry parameters
        solve_field_path = self.config.get(
            'pinpoint', 'solve_field_path', '/home/chultun/astrometry/bin/solve-field')
        downsample = self.config.get('pinpoint', 'downsample', 2)
        scale_low = self.config.get('pinpoint', 'scale_low', 0.55)
        scale_high = self.config.get('pinpoint', 'scale_high', 2.00)
        radius = self.config.get('pinpoint', 'radius', 50.0)
        cpulimit = self.config.get('pinpoint', 'cpu_limit', 30)
        max_ra_offset = float(self.config.get(
            'pinpoint', 'max_ra_offset', 50.0))
        max_dec_offset = float(self.config.get(
            'pinpoint', 'max_dec_offset', 50.0))
        min_ra_offset = float(self.config.get(
            'pinpoint', 'min_ra_offset', 0.05))
        min_dec_offset = float(self.config.get(
            'pinpoint', 'min_dec_offset', 0.05))
        max_tries = int(self.config.get('pinpoint', 'max_tries', 5))
        time = self.config.get('pinpoint', 'time', 10)
        bin = self.config.get('pinpoint', 'bin', 2)
        filter = self.config.get('pinpoint', 'filter', 'clear')
        user = self.slack.get_user_by_id(_user['id']).get('name', _user['id'])

        # name and path for pinpoint images
        fname = self.get_fitsFname(
            'pinpoint', filter, time, bin, user.lower(), 0, '')
        # path = self.image_dir + '/' + datetime.datetime.utcnow().strftime('%Y') + \
        #     '/' + datetime.datetime.utcnow().strftime('%Y-%m-%d') + '/' + \
        #     user + '/'
        path = self.get_fitsPath(user.lower())

        ra_target = Angle(ra.replace(' ', ':'), unit=u.hour).degree
        dec_target = Angle(dec.replace(' ', ':'), unit=u.deg).degree

        # turn tracking on - this is redundant, but sometimes helpful
        telescope_interface = TelescopeInterface('track')
        telescope_interface.set_input_value('on_off', 'on')
        self.telescope.track(telescope_interface)

        # center dome - this is redundant, but sometimes helpful
        telescope_interface = TelescopeInterface('center_dome')
        self.telescope.center_dome(telescope_interface)

        # point the telescope
        # self.logger.info('Pointing to RA=%s, DEC=%s.' %
        #                 (ra.replace(' ', ':'),  dec.replace(' ', ':')))
        self.slack.send_message('%s is pointing the telescope to RA=%s/DEC=%s. Please wait...' %
                                (self.config.get('slack', 'bot_name'), ra, dec))
        telescope_interface = TelescopeInterface('point')
        telescope_interface.set_input_value('ra', ra)
        telescope_interface.set_input_value('dec', dec)
        self.telescope.point(telescope_interface)
        self.slack.send_message(
            'Telescope successfully pointed to RA=%s/DEC=%s.' % (ra, dec))

        # get current filter setting
        telescope_interface = TelescopeInterface('get_filter')
        self.telescope.get_filter(telescope_interface)
        # assign values
        num = telescope_interface.get_output_value('num')
        filters = self.config.get('telescope', 'filters').split('\n')
        original_filter = filters[num-1]
        # change filter to 'filter_for_pinpoint' if not already set
        if(original_filter != filter):
            result = self._set_filter(filter)
            self.logger.info('Filter changed from %s to %s.' %
                             (original_filter, result))

        # turn off HDR mode
        hdr = self.hdr
        self.hdr = False

        # start pinpoint iterations
        iteration = 0
        while(iteration < max_tries):
            self.slack.send_message(
                'Obtaining intermediate image (#%d) for pinpoint astrometry...' % (iteration+1))
            success = self._get_image(time, bin, filter, path, fname)
            if success:
                self.slack_send_fits_file(path + fname, fname)
            else:
                self.logger.error('Error. Image command failed (%s).' % fname)
                return False

            telescope_interface = TelescopeInterface('pinpoint')
            # assign values
            telescope_interface.set_input_value(
                'solve_field_path', solve_field_path)
            telescope_interface.set_input_value('downsample', downsample)
            telescope_interface.set_input_value('scale_low', scale_low)
            telescope_interface.set_input_value('scale_high', scale_high)
            telescope_interface.set_input_value('ra_target', ra_target)
            telescope_interface.set_input_value('dec_target', dec_target)
            telescope_interface.set_input_value('radius', radius)
            telescope_interface.set_input_value('cpulimit', cpulimit)
            telescope_interface.set_input_value('path', path)
            telescope_interface.set_input_value('fname', fname)
            self.telescope.pinpoint(telescope_interface)
            # get field center for this image, if astrometry succeeded
            ra_image = telescope_interface.get_output_value('ra_image')
            dec_image = telescope_interface.get_output_value('dec_image')

            ra_offset = float(ra_target)-float(ra_image)
            if ra_offset > 350:
                ra_offset -= 360.0
            dec_offset = float(dec_target)-float(dec_image)

            if(abs(ra_offset) <= min_ra_offset and abs(dec_offset) <= min_dec_offset):
                self.hdr = hdr
                # change filter back to original_filter
                if(original_filter != filter):
                    result = self._set_filter(filter)
                    self.logger.info('Filter changed from %s to %s.' % (
                        original_filter, result))
                return True
            elif(abs(ra_offset) <= max_ra_offset and abs(dec_offset) <= max_dec_offset):
                self.slack.send_message(
                    "Adjusting telescope pointing (dRA=%f deg, dDEC=%f deg)..." % (ra_offset, dec_offset))
                telescope_interface = TelescopeInterface('offset')
                telescope_interface.set_input_value('dRA', ra_offset)
                telescope_interface.set_input_value('dDEC', dec_offset)
                self.telescope.pinpoint(telescope_interface)
            else:
                self.logger.error("Calculated offsets too large (dRA=%f deg, dDEC=%f deg)! Pinpoint aborted." % (
                    ra_offset, dec_offset))
                self.hdr = hdr
                # change filter back to original_filter
                if(original_filter != filter):
                    result = self._set_filter(filter)
                    self.logger.info('Filter changed from %s to %s.' % (
                        original_filter, result))
                return False

            iteration += 1

        self.logger.error(
            'Pinpoint exceeded maximum number of iterations (%d).' % max_tries)
        self.hdr = hdr  # restore HDR setting
        # change filter back to original_filter
        if(original_filter != filter):
            result = self._set_filter(filter)
            self.logger.info('Filter changed from %s to %s.' %
                             (original_filter, result))

        return False

    def pinpoint(self, command, user):
        try:
            # get object id; assume 1 if none
            if command.group(1):
                id = int(command.group(1).strip())
            else:
                id = 1
            # ensure object id is valid
            if id < 1 or id > len(self.skyObjects):
                self.slack.send_message('%s does not recognize the object id (%d). Run \\find first!' % (
                    self.config.get('slack', 'bot_name'), id))
                return
            self.set_target()
            # find corresponding object
            skyObject = self.skyObjects[id-1]
            self.slack.send_message('%s is pinpointing the telescope to "%s". Please wait...' % (
                self.config.get('slack', 'bot_name'), skyObject.name))
            success = self._pinpoint(user, skyObject.ra, skyObject.dec)
            if success:
                self.slack.send_message(
                    'Telescope successfully pinpointed to %s.' % skyObject.name)
                self.set_target(skyObject.name)
            else:
                self.slack.send_message(
                    'Telescope failed to pinpoint to %s.' % skyObject.name)
        except Exception as e:
            self.handle_error(command.group(0), 'Exception (%s).' % e)

    def pinpoint_ra_dec(self, command, user):
        try:
            self.set_target()
            ra = command.group(1).strip()
            dec = command.group(2).strip()
            self.slack.send_message('%s is pinpointing the telescope to RA=%s/DEC=%s. Please wait...' %
                                    (self.config.get('slack', 'bot_name'), ra, dec))
            success = self._pinpoint(user, ra, dec)
            if success:
                self.slack.send_message(
                    'Telescope successfully pinpointed to RA=%s/DEC=%s.' % (ra, dec))
                # regex to format RA/dec for filename
                _ra = re.sub('^(\d{1,2}):(\d{2}):(\d{2}).+', r'\1h\2m\3s', ra)
                _dec = re.sub('(\d{1,2}):(\d{2}):(\d{2}).+', r'\1d\2m\3s', dec)
                self.set_target('%s%s' % (_ra, _dec))
            else:
                self.slack.send_message(
                    'Telescope successfully pinpointed to RA=%s/DEC=%s.' % (ra, dec))
        except Exception as e:
            self.handle_error(command.group(0), 'Exception (%s).' % e)

    def plot_ra_dec(self, command, user):
        ra = command.group(1)
        dec = command.group(2)
        self.slack.send_message('%s is calculating when RA=%s/DEC=%s is observable from your location. Please wait...' %
                                (self.config.get('slack', 'bot_name'), ra, dec))
        self.coordinate.plot(ra, dec)

    def plot(self, command, user):
        # get object id; assume 1 if none
        if command.group(1):
            id = int(command.group(1).strip())
        else:
            id = 1
        # ensure object id is valid
        if id < 1 or id > len(self.skyObjects):
            self.slack.send_message('%s does not recognize the object id (%d). Run \\find first!' % (
                self.config.get('slack', 'bot_name'), id))
            return
        # find corresponding object
        skyObject = self.skyObjects[id-1]
        self.slack.send_message('%s is calculating when "%s" is observable from your location. Please wait...' % (
            self.config.get('slack', 'bot_name'), skyObject.name))
        if skyObject.type == 'Solar System':
            self.solarSystem.plot(skyObject)
        elif skyObject.type == "Celestial":
            self.celestial.plot(skyObject)
        elif skyObject.type == "Satellite":
            self.satellite.plot(skyObject)
        # self.slack.send_message('Name of object is %s.'%skyObject.name)

    def find(self, command, user):
        try:
            search_string = command.group(1)
            self.slack.send_message('%s is searching the cosmos for "%s". Please wait...' % (
                self.config.get('slack', 'bot_name'), search_string))
            satellites = self.satellite.find(search_string)
            celestials = self.celestial.find(search_string)
            solarSystems = self.solarSystem.find(search_string)
            # process total search restults
            self.skyObjects = satellites + celestials + solarSystems
            telescope = self.ixchel.telescope.earthLocation
            if len(self.skyObjects) > 0:
                report = ''
                index = 1
                # calculate local time of observatory
                telescope_now = Time(datetime.datetime.utcnow(), scale='utc')
                self.slack.send_message('%s found %d match(es):' % (
                    self.config.get('slack', 'bot_name'), len(self.skyObjects)))
                for skyObject in self.skyObjects:
                    # create SkyCoord instance from RA and DEC
                    c = SkyCoord(skyObject.ra, skyObject.dec,
                                 unit=(u.hour, u.deg))
                    # transform RA,DEC to alt, az for this object from the observatory
                    altaz = c.transform_to(
                        AltAz(obstime=telescope_now, location=telescope))
                    # report += '%d.\t%s object (%s) found at RA=%s, DEC=%s, ALT=%f, AZ=%f, VMAG=%s.\n' % (
                    #    index, skyObject.type, skyObject.name, skyObject.ra, skyObject.dec, altaz.alt.degree, altaz.az.degree, skyObject.vmag)
                    report = find_format_string.format(Index=str(index), Name=skyObject.name, Type=skyObject.type, RA=skyObject.ra,
                                                       DEC=skyObject.dec, Altitude='%.1f°' % altaz.alt.degree, Azimuth='%.1f°' % altaz.az.degree, V=skyObject.vmag)
                    self.slack.send_block_message(report)
                    index += 1
                    # don't trigger the Slack bandwidth threshold
                    time.sleep(1)
            else:
                self.slack.send_message(
                    'Sorry, %s knows all but *still* could not find "%s".' % (self.config.get('slack', 'bot_name'), search_string))
        except Exception as e:
            self.handle_error(command.group(0), 'Exception (%s).' % e)

    def get_help(self, command, user):
        slack_user = self.slack.get_user_by_id(
            user['id']).get('name', user['id'])
        help_message = self.config.get('slack', 'help_message').format(
            bot_name=self.bot_name, user=slack_user) + '\n'
        for cmd in sorted(self.commands, key=lambda i: i['regex']):
            if not cmd['hide']:
                help_message += '>%s\n' % cmd['description']
        self.slack.send_message(help_message)

    def get_where(self, command, user):
        try:
            telescope_interface = TelescopeInterface('get_where')
            # query telescope
            self.telescope.get_precipitation(telescope_interface)
            # assign values
            ra = telescope_interface.get_output_value('ra')
            dec = telescope_interface.get_output_value('dec')
            alt = telescope_interface.get_output_value('alt')
            az = telescope_interface.get_output_value('az')
            slewing = telescope_interface.get_output_value('slewing')
            # send output to Slack
            self.slack.send_message('Telescope Pointing:')
            self.slack.send_message('>RA: %s' % ra)
            self.slack.send_message('>DEC: %s' % dec)
            self.slack.send_message(u'>Alt: %.1f°' % alt)
            self.slack.send_message(u'>Az: %.1f°' % az)
            if slewing == 1:
                self.slack.send_message('>Slewing? Yes')
            else:
                self.slack.send_message('>Slewing? No')
            # get a DSS image of this part of the sky
            ra_decimal = Angle(ra + '  hours').hour
            dec_decimal = Angle(dec + '  degrees').degree
            url = self.config.get('misc', 'dss_url').format(
                ra=ra_decimal, dec=dec_decimal)
            self.slack.send_message(
                "", [{"image_url": "%s" % url, "title": "Sky Position (DSS2):"}])
        except Exception as e:
            self.handle_error(command.group(0), 'Exception (%s).' % e)

    def get_clouds(self, command, user):
        try:
            telescope_interface = TelescopeInterface('get_precipitation')
            # query telescope
            self.telescope.get_precipitation(telescope_interface)
            # assign values
            clouds = telescope_interface.get_output_value('clouds')
            # send output to Slack
            self.slack.send_message('Cloud cover is %d%%.' % int(clouds*100))
        except Exception as e:
            self.handle_error(command.group(0), 'Exception (%s).' % e)

    def get_sun(self, command, user):
        try:
            telescope_interface = TelescopeInterface('get_sun')
            # query telescope
            self.telescope.get_precipitation(telescope_interface)
            # assign values
            alt = telescope_interface.get_output_value('alt')
            # send output to Slack
            self.slack.send_message('Sun:')
            self.slack.send_message('>Altitude: %.1f°' % alt)
        except Exception as e:
            self.handle_error(command.group(0), 'Exception (%s).' % e)

    def get_dome(self, command, user):
        try:
            telescope_interface = TelescopeInterface('get_dome')
            # query telescope
            self.telescope.get_dome(telescope_interface)
            # assign values
            az = telescope_interface.get_output_value('az')
            # send output to Slack
            self.slack.send_message(
                'The dome slit azimuth is %s°.' % az.strip())
        except Exception as e:
            self.handle_error(command.group(0), 'Exception (%s).' % e)

    def center_dome(self, command, user):
        try:
            self.slack.send_message(
                'Centering dome. Please wait...')
            telescope_interface = TelescopeInterface('center_dome')
            # query telescope
            self.telescope.center_dome(telescope_interface)
            # assign values
            az = telescope_interface.get_output_value('az')
            # send output to Slack
            self.slack.send_message(
                'The dome slit is centered (az=%s°).' % az.strip())
        except Exception as e:
            self.handle_error(command.group(0), 'Exception (%s).' % e)

    def abort(self, command, user):
        try:
            self.logger.debug("You should never get here.")
        except Exception as e:
            self.handle_error(command.group(0), 'Exception (%s).' % e)

    def home_dome(self, command, user):
        try:
            self.slack.send_message(
                'Homing dome. Please wait...')
            # right
            telescope_interface = TelescopeInterface('home_domer')
            # query telescope
            self.telescope.home_domer(telescope_interface)
            # assign values
            az_hit = telescope_interface.get_output_value('az_hit')
            rem = telescope_interface.get_output_value('rem')
            # left
            telescope_interface = TelescopeInterface('home_domel')
            # query telescope
            self.telescope.home_domel(telescope_interface)
            # assign values
            az_hit = telescope_interface.get_output_value('az_hit')
            rem = telescope_interface.get_output_value('rem')
            # send output to Slack
            self.slack.send_message(
                'The dome is calibrated.')
        except Exception as e:
            self.handle_error(command.group(0), 'Exception (%s).' % e)

    def get_slit(self, command, user):
        try:
            telescope_interface = TelescopeInterface('get_slit')
            # query telescope
            self.telescope.get_slit(telescope_interface)
            # assign values
            open_close = telescope_interface.get_output_value('open_close')
            # send output to Slack
            self.slack.send_message('The slit is %s.' % open_close.strip())
        except Exception as e:
            self.handle_error(command.group(0), 'Exception (%s).' % e)

    def set_slit(self, command, user):
        try:
            telescope_interface = TelescopeInterface('set_slit')
            # assign input values
            open_close = command.group(1).strip()
            telescope_interface.set_input_value('open_close', open_close)
            # query telescope
            self.telescope.set_slit(telescope_interface)
            # assign output values
            open_closed = telescope_interface.get_output_value(
                'open_close').strip()
            success = (open_closed.find(open_close) >= 0)
            # send output to Slack
            if success:
                self.slack.send_message('The slit is %s.' % open_closed)
            else:
                self.slack.send_message(
                    'Failed to %s slit.' % open_close)
        except Exception as e:
            self.handle_error(command.group(0), 'Exception (%s).' % e)

    def get_preview(self, command, user):
        try:
            if (self.preview):
                self.slack.send_message('FITS preview is on.')
            else:
                self.slack.send_message('FITS preview is off.')
        except Exception as e:
            self.handle_error(command.group(0), 'Exception (%s).' % e)

    def set_preview(self, command, user):
        try:
            on_off = command.group(1)
            if (on_off == 'on'):
                self.preview = True
            else:
                self.preview = False
            self.get_preview(command, user)
        except Exception as e:
            self.handle_error(command.group(0), 'Exception (%s).' % e)

    def get_hdr(self, command, user):
        try:
            if (self.hdr):
                self.slack.send_message('HDR mode is on.')
            else:
                self.slack.send_message('HDR mode is off.')
        except Exception as e:
            self.handle_error(command.group(0), 'Exception (%s).' % e)

    def set_hdr(self, command, user):
        try:
            on_off = command.group(1)
            if (on_off == 'on'):
                self.hdr = True
            else:
                self.hdr = False
            self.get_hdr(command, user)
        except Exception as e:
            self.handle_error(command.group(0), 'Exception (%s).' % e)

    def share_lock(self, command, user):
        try:
            on_off = command.group(1)
            if (on_off == 'on'):
                self.share = True
            else:
                self.share = False
            self.slack.send_message('Lock sharing is %s.' % on_off)
        except Exception as e:
            self.handle_error(command.group(0), 'Exception (%s).' % e)

    def get_ccd(self, command, user):
        try:
            telescope_interface = TelescopeInterface('get_ccd')
            # query telescope
            self.telescope.get_ccd(telescope_interface)
            # assign values
            ncol = telescope_interface.get_output_value('ncol')
            nrow = telescope_interface.get_output_value('nrow')
            name = telescope_interface.get_output_value('name')
            tchip = telescope_interface.get_output_value('tchip')
            setpoint = telescope_interface.get_output_value('setpoint')
            drive = telescope_interface.get_output_value('drive')
            # send output to Slack
            self.slack.send_message('CCD:')
            self.slack.send_message('>Type: %s' % name)
            self.slack.send_message('>Pixels: %d x %d' % (nrow, ncol))
            self.slack.send_message('>Temperature: %.1f° C' % tchip)
            self.slack.send_message('>Set Point: %.1f° C' % setpoint)
            self.slack.send_message('>Cooler Drive: %d%%' % drive)
        except Exception as e:
            self.handle_error(command.group(0), 'Exception (%s).' % e)

    def set_ccd(self, command, user):
        try:
            telescope_interface = TelescopeInterface('set_ccd')
            # assign input values
            cool_warm = command.group(1)
            telescope_interface.set_input_value('cool_warm', cool_warm)
            setpoint = command.group(2)
            telescope_interface.set_input_value('setpoint', setpoint)
            # query telescope
            self.telescope.set_ccd(telescope_interface)
            # assign output values
            success = telescope_interface.get_output_value('success')
            # send output to Slack
            if success:
                self.slack.send_message(
                    'CCD is %sing (setpoint is %s°C). Use \ccd to monitor.' % (cool_warm, setpoint))
            else:
                self.slack.send_message(
                    'Failed to adjust CCD cooling settings.')
        except Exception as e:
            self.handle_error(command.group(0), 'Exception (%s).' % e)

    def get_moon(self, command, user):
        try:
            telescope_interface = TelescopeInterface('get_moon')
            # query telescope
            self.telescope.get_precipitation(telescope_interface)
            # assign values
            alt = telescope_interface.get_output_value('alt')
            phase = int(telescope_interface.get_output_value('phase')*100)
            # send output to Slack
            self.slack.send_message('Moon:')
            self.slack.send_message('>Altitude: %.1f°' % alt)
            self.slack.send_message('>Phase: %d%%' % phase)
        except Exception as e:
            self.handle_error(command.group(0), 'Exception (%s).' % e)

    def get_filter(self, command, user):
        try:
            telescope_interface = TelescopeInterface('get_filter')
            # query telescope
            self.telescope.get_filter(telescope_interface)
            # assign values
            num = telescope_interface.get_output_value('num')
            filters = self.config.get('telescope', 'filters').split('\n')
            name = filters[num-1]
            # send output to Slack
            self.slack.send_message('Filter is %s.' % name)
        except Exception as e:
            self.handle_error(command.group(0), 'Exception (%s).' % e)

    def _set_filter(self, filter):
        try:
            telescope_interface = TelescopeInterface('set_filter')
            filters = self.config.get('telescope', 'filters').split('\n')
            num = filters.index(filter) + 1
            # assign values
            telescope_interface.set_input_value('num', num)
            self.telescope.set_filter(telescope_interface)
            num = telescope_interface.get_output_value('num')
            return filters[num-1]
        except Exception as e:
            self.logger.error('Failed to set the filter to %s.' % filter)
            raise

    def set_filter(self, command, user):
        try:
            name = self._set_filter(command.group(1))
            # send output to Slack
            self.slack.send_message('Filter is %s.' % name)
        except Exception as e:
            self.handle_error(command.group(0), 'Exception (%s).' % e)

    def _get_focus(self):
        try:
            telescope_interface = TelescopeInterface('get_focus')
            # query telescope
            self.telescope.get_focus(telescope_interface)
            # assign values
            pos = telescope_interface.get_output_value('pos')
            return pos
        except Exception as e:
            self.logger.error('Failed to get the focus to %s.' % _pos)
            raise

    def get_focus(self, command, user):
        try:
            pos = self._get_focus()
            # send output to Slack
            self.slack.send_message('Focus position is %d.' % pos)
        except Exception as e:
            self.handle_error(command.group(0), 'Exception (%s).' % e)

    def keepopen(self, command, user):
        try:
            telescope_interface = TelescopeInterface('keepopen')
            # assign values
            maxtime = int(command.group(1))
            telescope_interface.set_input_value('maxtime', maxtime)
            # create a command that applies the specified values
            self.telescope.keepopen(telescope_interface)
            # send output to Slack
            self.slack.send_message(
                'Keepopen slit timer is set to %d s.' % maxtime)
        except Exception as e:
            self.handle_error(command.group(0), 'Exception (%s).' % e)

    def _set_focus(self, _pos):
        try:
            telescope_interface = TelescopeInterface('set_focus')
            # assign values
            pos = _pos
            telescope_interface.set_input_value('pos', pos)
            # create a command that applies the specified values
            self.telescope.set_focus(telescope_interface)
            # send output to Slack
            pos = telescope_interface.get_output_value('pos')
            return pos
        except Exception as e:
            self.logger.error('Failed to set the focus to %s.' % _pos)
            raise

    def set_focus(self, command, user):
        try:
            pos = self._set_focus(int(command.group(1)))
            # send output to Slack
            self.slack.send_message('Focus position is %d.' % pos)
        except Exception as e:
            self.handle_error(command.group(0), 'Exception (%s).' % e)

    def slack_send_fits_file(self, fits_file, comment):
        if self.preview == False:
            self.logger.info("FITS preview in Slack is OFF.")
            return
        try:
            telescope_interface = TelescopeInterface('convert_fits_to_jpg')
            telescope_interface.set_input_value('fits_file', fits_file)
            telescope_interface.set_input_value('tiff_file', self.config.get(
                'telescope', 'convert_tiff_remote_file_path'))
            telescope_interface.set_input_value('jpg_file', self.config.get(
                'telescope', 'convert_jpg_remote_file_path'))
            self.telescope.convert_fits_to_jpg(telescope_interface)
            success = self.telescope.get_file(self.config.get(
                'telescope', 'convert_jpg_remote_file_path'), self.config.get('telescope', 'convert_jpg_local_file_path'))
            if success:
                self.slack.send_file(self.config.get(
                    'telescope', 'convert_jpg_local_file_path'), comment)
            else:
                self.logger.error(
                    'Failed to get telescope image from remote server.')
        except Exception as e:
            raise ValueError(
                'Failed to send the fits file (%s) to Slack.' % fits_file)

    def _get_image(self, exposure, bin, filter, path, fname, dark=False, low_fname=''):
        # set filter
        self._set_filter(filter)
        # take image
        if self.hdr:
            telescope_interface = TelescopeInterface('get_image_hdr')
            telescope_interface.set_input_value('low_fname', low_fname)
        else:
            telescope_interface = TelescopeInterface('get_image')
        telescope_interface.set_input_value('exposure', exposure)
        telescope_interface.set_input_value('bin', bin)
        telescope_interface.set_input_value('path', path)
        telescope_interface.set_input_value('fname', fname)
        if dark:
            telescope_interface.set_input_value('dark', 'dark')
        self.telescope.get_image(telescope_interface)
        return (telescope_interface.get_output_value('error') == '')

    def get_image(self, command, user):
        try:
            filter = command.group(3)
            exposure = float(command.group(1))
            bin = int(command.group(2))
            count = 1
            if command.group(4) is not None:
                count = int(command.group(4))
            slack_user = self.slack.get_user_by_id(
                user['id']).get('name', user['id'])
            # get <count> frames
            index = 0
            while(index < count):
                # check for abort
                if self.getDoAbort():
                    self.slack.send_message('Image sequence aborted.')
                    self.setDoAbort(False)
                    return
                self.slack.send_message(
                    'Obtaining image (%d of %d). Please wait...' % (index+1, count))
                if self.hdr:
                    # fname = '%s_%s_%ss_bin%sH_%s_%s_seo_%03d_RAW.fits.gz' % (
                    #     self.target, filter, exposure, bin, datetime.datetime.utcnow().strftime('%y%m%d_%H%M%S'), slack_user.lower(), index)
                    fname = self.get_fitsFname(
                        self.target, filter, exposure, bin, slack_user, index, 'H')
                else:
                    # fname = '%s_%s_%ss_bin%s_%s_%s_seo_%03d_RAW.fits.gz' % (
                    #     self.target, filter, exposure, bin, datetime.datetime.utcnow().strftime('%y%m%d_%H%M%S'), slack_user.lower(), index)
                    fname = self.get_fitsFname(
                        self.target, filter, exposure, bin, slack_user, index, '')
                # only gets used if self.hdr == True
                # low_fname = '%s_%s_%ss_bin%sL_%s_%s_seo_%03d.gz' % (
                #     self.target, filter, exposure, bin, datetime.datetime.utcnow().strftime('%y%m%d_%H%M%S'), slack_user.lower(), index)
                low_fname = self.get_fitsFname(
                    self.target, filter, exposure, bin, slack_user, index, 'L')
                # path = self.image_dir + '/' + datetime.datetime.utcnow().strftime('%Y') + \
                #     '/' + datetime.datetime.utcnow().strftime('%Y-%m-%d') + '/' + \
                #     slack_user + '/'
                path = self.get_fitsPath(slack_user)
                error = self._get_image(
                    exposure, bin, filter, path, fname, False, low_fname)
                if error:
                    self.slack.send_message(
                        'Image command completed successfully.')
                    self.slack_send_fits_file(path + fname, fname)
                    if self.hdr:
                        self.slack_send_fits_file(path + low_fname, low_fname)
                else:
                    self.handle_error(command.group(0), 'Error (%s).' % error)
                index = index + 1
        except Exception as e:
            self.handle_error(command.group(0), 'Exception (%s).' % e)

    def get_dark(self, command, user):
        try:
            filter = self.config.get('telescope', 'filter_for_darks')
            exposure = float(command.group(1))
            bin = int(command.group(2))
            count = 1
            if command.group(3) is not None:
                count = int(command.group(3))
            slack_user = self.slack.get_user_by_id(
                user['id']).get('name', user['id'])
            # get <count> frames
            index = 0
            while(index < count):
                # check for abort
                if self.getDoAbort():
                    self.slack.send_message('Image sequence aborted.')
                    self.setDoAbort(False)
                    return
                self.slack.send_message(
                    'Obtaining dark image (%d of %d). Please wait...' % (index+1, count))
                if self.hdr:
                    # fname = '%s_%s_%ss_bin%sH_%s_%s_seo_%03d_RAW.fits.gz' % (
                    #     'dark', filter, exposure, bin, datetime.datetime.utcnow().strftime('%y%m%d_%H%M%S'), slack_user.lower(), index)
                    fname = self.get_fitsFname(
                        'dark', filter, exposure, bin, slack_user, index, 'H')
                else:
                    # fname = '%s_%s_%ss_bin%s_%s_%s_seo_%03d_RAW.fits.gz' % (
                    #     'dark', filter, exposure, bin, datetime.datetime.utcnow().strftime('%y%m%d_%H%M%S'), slack_user.lower(), index)
                    fname = self.get_fitsFname(
                        'dark', filter, exposure, bin, slack_user, index, '')
                # only gets used if self.hdr == True
                # low_fname = '%s_%s_%ss_bin%sL_%s_%s_seo_%03d_RAW.fits.gz' % (
                #     'dark', filter, exposure, bin, datetime.datetime.utcnow().strftime('%y%m%d_%H%M%S'), slack_user.lower(), index)
                low_fname = self.get_fitsFname(
                    'dark', filter, exposure, bin, slack_user, index, 'L')
                # path = self.image_dir + '/' + datetime.datetime.utcnow().strftime('%Y') + \
                #     '/' + datetime.datetime.utcnow().strftime('%Y-%m-%d') + '/' + \
                #     slack_user + '/'
                path = self.get_fitsPath(slack_user)
                error = self._get_image(
                    exposure, bin, filter, path, fname, True, low_fname)
                if error:
                    self.slack.send_message(
                        'Image command completed successfully.')
                    self.slack_send_fits_file(path + fname, fname)
                    if self.hdr:
                        self.slack_send_fits_file(path + low_fname, low_fname)
                else:
                    self.handle_error(command.group(0), 'Error (%s).' % error)
                index = index + 1
        except Exception as e:
            self.handle_error(command.group(0), 'Exception (%s).' % e)

    def get_bias(self, command, user):
        try:
            filter = self.config.get('telescope', 'filter_for_darks')
            exposure = self.config.get('telescope', 'exposure_for_bias')
            bin = int(command.group(1))
            count = 1
            if command.group(2) is not None:
                count = int(command.group(2))
            slack_user = self.slack.get_user_by_id(
                user['id']).get('name', user['id'])
            # get <count> frames
            index = 0
            while(index < count):
                # check for abort
                if self.getDoAbort():
                    self.slack.send_message('Image sequence aborted.')
                    self.setDoAbort(False)
                    return
                self.slack.send_message(
                    'Obtaining bias image (%d of %d). Please wait...' % (index+1, count))
                if self.hdr:
                    # fname = '%s_%s_%ss_bin%sH_%s_%s_seo_%03d_RAW.fits.gz' % (
                    #     'bias', filter, exposure, bin, datetime.datetime.utcnow().strftime('%y%m%d_%H%M%S'), slack_user.lower(), index)
                    fname = self.get_fitsFname(
                        'bias', filter, exposure, bin, slack_user, index, 'H')
                else:
                    # fname = '%s_%s_%ss_bin%s_%s_%s_seo_%03d_RAW.fits.gz' % (
                    #     'bias', filter, exposure, bin, datetime.datetime.utcnow().strftime('%y%m%d_%H%M%S'), slack_user.lower(), index)
                    fname = self.get_fitsFname(
                        'bias', filter, exposure, bin, slack_user, index, '')
                # low_fname = '%s_%s_%ss_bin%sL_%s_%s_seo_%03d_RAW.fits.gz' % (
                #     'bias', filter, exposure, bin, datetime.datetime.utcnow().strftime('%y%m%d_%H%M%S'), slack_user.lower(), index)
                low_fname = self.get_fitsFname(
                    'bias', filter, exposure, bin, slack_user, index, 'L')
                # path = self.image_dir + '/' + datetime.datetime.utcnow().strftime('%Y') + \
                #     '/' + datetime.datetime.utcnow().strftime('%Y-%m-%d') + '/' + \
                #     slack_user + '/'
                path = self.get_fitsPath(slack_user)
                error = self._get_image(
                    exposure, bin, filter, path, fname, True, low_fname)
                if error:
                    self.slack.send_message(
                        'Image command completed successfully.')
                    self.slack_send_fits_file(path + fname, fname)
                    if self.hdr:
                        self.slack_send_fits_file(path + low_fname, low_fname)
                else:
                    self.handle_error(command.group(0), 'Error (%s).' % error)
                index = index + 1
        except Exception as e:
            self.handle_error(command.group(0), 'Exception (%s).' % e)

    def get_who(self, command, user):
        if not self.is_locked():
            self.slack.send_message('Telescope is not locked.')
            return
        try:
            self.slack.send_message(
                'Telescope is locked by %s.' % self.locked_by())
            return
        except Exception as e:
            self.handle_error(command.group(0), 'Exception (%s).' % e)

    def set_lock(self, command, user):
        if self.is_locked():
            self.slack.send_message(
                'Telescope is already locked by %s.' % self.locked_by())
            return
        try:
            telescope_interface = TelescopeInterface('set_lock')
            # assign values
            telescope_interface.set_input_value('user', user['id'])
            # query telescope
            self.telescope.set_lock(telescope_interface)
            # assign values
            _user = telescope_interface.get_output_value('user')
            # send output to Slack
            self.slack.send_message(
                'Telescope is locked.')
            slack_user = self.slack.get_user_by_id(
                user['id']).get('name', user['id'])
            welcome_message = self.config.get('slack', 'welcome_message').format(
                bot_name=self.bot_name, user=slack_user)
            self.slack.send_message(welcome_message)
            self.resetSession()
        except Exception as e:
            self.handle_error(command.group(0), 'Exception (%s).' % e)

    def unlock(self, command, user):
        if not self.is_locked():
            self.slack.send_message('Telescope is not locked.')
            return
        if not self.is_locked_by(user):
            self.slack.send_message(
                'Telescope is locked by %s.' % self.locked_by())
            return
        try:
            telescope_interface = TelescopeInterface('unlock')
            # assign values
            # query telescope
            self.telescope.unlock(telescope_interface)
            # send output to Slack
            self.slack.send_message(
                'Telescope is unlocked.')
            self.resetSession()
        except Exception as e:
            self.handle_error(command.group(0), 'Exception (%s).' % e)

    def open_observatory(self, command, user):
        try:
            self.slack.send_message(
                'Cracking observatory. Please wait...')
            telescope_interface = TelescopeInterface('open_observatory')
            # assign values
            # query telescope
            self.telescope.open_observatory(telescope_interface)
            # assign output values
            failure = telescope_interface.get_output_value('failure')
            # send output to Slack
            if(failure):
                self.slack.send_message('Telescope could not be opened.')
            else:
                self.slack.send_message('Telescope is cracked.')
        except Exception as e:
            self.handle_error(command.group(0), 'Exception (%s).' % e)

    def close_observatory(self, command, user):
        try:
            self.set_target()
            self.slack.send_message(
                'Squeezing observatory. Please wait...')
            telescope_interface = TelescopeInterface('close_observatory')
            # assign values
            # query telescope
            self.telescope.close_observatory(telescope_interface)
            # assign output values
            failure = telescope_interface.get_output_value('failure')
            # send output to Slack
            if(failure):
                self.slack.send_message('Telescope could not be closed.')
            else:
                self.slack.send_message('Telescope is squeezed.')
        except Exception as e:
            self.handle_error(command.group(0), 'Exception (%s).' % e)

    def clear_lock(self, command, user):
        try:
            telescope_interface = TelescopeInterface('clear_lock')
            # assign values
            # query telescope
            self.telescope.clear_lock(telescope_interface)
            # send output to Slack
            self.slack.send_message(
                'Telescope is unlocked.')
        except Exception as e:
            self.handle_error(command.group(0), 'Exception (%s).' % e)

    def locked_by(self):
        try:
            telescope_interface = TelescopeInterface('get_lock')
            # query telescope
            self.telescope.get_lock(telescope_interface)
            # assign values
            _user = telescope_interface.get_output_value('user')
            self.logger.info(
                'Telescope is locked by %s.' % _user)
            # assign values
            return self.slack.get_user_by_id(_user).get('name', _user)
        except Exception as e:
            self.logger.error(
                'Could not get telescope lock info. Exception (%s).' % e)
        return 'unknown'

    def is_locked_by(self, user):
        try:
            telescope_interface = TelescopeInterface('get_lock')
            # query telescope
            self.telescope.get_lock(telescope_interface)
            # assign values
            _user = telescope_interface.get_output_value('user')
            self.logger.info(
                'Telescope is locked by %s.' % _user)
            # assign values
            return _user == user['id']
        except Exception as e:
            self.logger.error(
                'Could not get telescope lock info. Exception (%s).' % e)
        return False

    def is_locked(self):
        try:
            telescope_interface = TelescopeInterface('get_lock')
            # query telescope
            self.telescope.get_lock(telescope_interface)
            # assign values
            _user = telescope_interface.get_output_value('user')
            self.logger.info(
                'Telescope is locked by %s.' % _user)
            # assign values
            return _user is not None
        except Exception as e:
            self.logger.error(
                'Could not get telescope lock info. Exception (%s).' % e)
        return True

    def get_clearsky(self, command, user):
        try:
            clearsky_links = self.config.get(
                'misc', 'clearsky_links').split('\n')
            for clearsky_link in clearsky_links:
                (title, url) = clearsky_link.split('|', 2)
                # hack to keep images up to date
                random_string = ''.join(random.choice(
                    string.ascii_uppercase + string.digits) for _ in range(5))
                self.slack.send_message('', [{'image_url': '%s?random_string=%s' % (
                    url, random_string), 'title': '%s' % title}])
                time.sleep(1)
        except Exception as e:
            self.handle_error(command.group(0), 'Exception (%s).' % (e))

    def get_skycam(self, command, user):
        # get sky image from SEO camera
        try:
            telescope_interface = TelescopeInterface('get_skycam')
            # assign input
            telescope_interface.set_input_value('skycam_remote_file_path', self.config.get(
                'telescope', 'skycam_remote_file_path'))
            telescope_interface.set_input_value('skycam_local_file_path', self.config.get(
                'telescope', 'skycam_local_file_path'))
            # create a command that applies the specified values
            self.telescope.get_skycam(telescope_interface)
            if telescope_interface.get_output_value('success'):
                success = self.telescope.get_file(self.config.get(
                    'telescope', 'skycam_remote_file_path'), self.config.get('telescope', 'skycam_local_file_path'))
                if success:
                    self.slack.send_file(self.config.get(
                        'telescope', 'skycam_local_file_path'), 'El Verano, CA (SEO Spa-Cam)')
                else:
                    self.logger.error(
                        'Failed to obtain image from observatory camera.')
            else:
                self.logger.error(
                    'Failed to obtain image from observatory camera.')
        except Exception as e:
            self.logger.error(
                'Failed to obtain image from observatory camera. Exception (%s).' % (e))
        # get sky images from Internet
        try:
            skycam_links = self.config.get('misc', 'skycam_links').split('\n')
            for skycam_link in skycam_links:
                (title, url) = skycam_link.split('|', 2)
                # hack to keep images up to date
                random_string = ''.join(random.choice(
                    string.ascii_uppercase + string.digits) for _ in range(5))
                self.slack.send_message('', [{'image_url': '%s?random_string=%s' % (
                    url, random_string), 'title': '%s' % title}])
                time.sleep(1)
        except Exception as e:
            self.handle_error(command.group(0), 'Exception (%s).' % (e))

    def hocus(self, command, user):
        try:
            # settings
            time = self.config.get('hocusfocus', 'time', 30)
            bin = self.config.get('hocusfocus', 'bin', 1)
            filter = self.config.get('hocusfocus', 'filter', 'clear')
            username = self.slack.get_user_by_id(
                user['id']).get('name', user['id'])
            telescope = self.ixchel.telescope.earthLocation
            telescope_now = Time(datetime.datetime.utcnow(), scale='utc')
            # psfex
            psfex_bin_path = self.config.get('psfex', 'bin_path')
            psfex_cfg_path = self.config.get('psfex', 'cfg_path')
            psfex_psf_remote_path = self.config.get('psfex', 'psf_remote_path')
            psfex_psf_local_path = self.config.get('psfex', 'psf_local_path')
            sextractor_cat_path = self.config.get('sextractor', 'cat_path')
            # sextractor
            sextractor_bin_path = self.config.get('sextractor', 'bin_path')
            sextractor_sex_path = self.config.get('sextractor', 'sex_path')
            sextractor_cat_path = self.config.get('sextractor', 'cat_path')
            sextractor_param_path = self.config.get(
                'sextractor', 'param_path')
            sextractor_conv_path = self.config.get(
                'sextractor', 'conv_path')

            # identify target from reference stars
            max_alt = -91.0
            target = ()  # hocusfocus target based on max altaz
            reference_stars = self.config.get(
                'hocusfocus', 'reference_stars').split('\n')
            for reference_star in reference_stars:
                (name, ra, dec) = reference_star.split('|', 3)
                # create SkyCoord instance from RA and DEC
                c = SkyCoord(ra, dec, unit=(u.hour, u.deg))
                # transform RA,DEC to alt, az for this object from the observatory
                altaz = c.transform_to(
                    AltAz(obstime=telescope_now, location=telescope))
                # track the reference star with max alt
                if(altaz.alt.degree > max_alt):
                    max_alt = altaz.alt.degree
                    target = (name, ra, dec)
            self.logger.info("The target star is %s (alt=%f deg)." %
                             (target[0], max_alt))

            # get current focus setting
            focus_pos_original = self._get_focus()
            self.logger.info("The current focus position is %d." %
                             focus_pos_original)

            # focus setting range
            focus_pos_start = int(self.config.get(
                'hocusfocus', 'focus_pos_start', 3700))
            focus_pos_end = int(self.config.get(
                'hocusfocus', 'focus_pos_end', 4000))
            focus_pos_increment = int(self.config.get(
                'hocusfocus', 'focus_pos_increment', 25))
            focus_range_len = (focus_pos_end-focus_pos_start) / \
                focus_pos_increment + 1
            # the psf vs focus data
            focus_psf_plot_data = np.zeros(
                (focus_pos_end-focus_pos_start)/focus_pos_increment + 1, 2)
            # main focus loop
            for focus_pos_index in range(0, focus_range_len):
                focus_pos = focus_pos_start + focus_pos_index*focus_pos_increment
                # check for abort
                if self.getDoAbort():
                    self.slack.send_message(
                        'Focus calibration sequence aborted.')
                    self.setDoAbort(False)
                    self._set_focus(focus_pos_original)
                    return

                # set focus setting
                self.slack.send_message(
                    'Setting focus position to %d...' % focus_pos)
                focus_pos = self._set_focus(focus_pos)

                # pinpoint to the target. this could get touchy if focus is too far out!
                self.slack.send_message(
                    'Pinpointing the telescope to %s. Please wait...' % target[0])
                success = self._pinpoint(user, target[1], target[2])
                if success:
                    self.slack.send_message(
                        'Telescope successfully pinpointed to %s.' % target[0])
                else:
                    self.slack.send_message(
                        'Telescope failed to pinpoint to %s.' % target[0])

                # get image
                # fname = self.get_fitsFname('hocusfocus', '%s_%s_%ss_bin%s_%s_%s_seo_%d_RAW.fits' % (
                #     'hocusfocus', filter, time, bin, datetime.datetime.utcnow().strftime('%y%m%d_%H%M%S'), username.lower(), 0)
                fname = self.get_fitsFname(
                    'hocusfocus', filter, time, bin, username, 0, '')
                # path = self.image_dir + '/' + datetime.datetime.utcnow().strftime('%Y') + \
                #     '/' + datetime.datetime.utcnow().strftime('%Y-%m-%d') + '/' + \
                #     username.lower() + '/'
                path = self.get_fitsPath(username)
                self.slack.send_message('Taking calibration image...')
                success = self._get_image(time, bin, filter, path, fname)
                if success:
                    self.slack_send_fits_file(path + fname, fname)
                else:
                    self.logger.error(
                        'Error. Image command failed (%s).' % fname)
                    continue

                # identify stars in image via sextractor
                self.slack.send_message(
                    'Extracting stars from calibration image...')
                telescope_interface = TelescopeInterface('sextractor')
                # assign values
                telescope_interface.set_input_value(
                    'sextractor_bin_path', sextractor_bin_path)
                telescope_interface.set_input_value(
                    'sextractor_sex_path', sextractor_sex_path)
                telescope_interface.set_input_value(
                    'sextractor_cat_path', sextractor_cat_path)
                telescope_interface.set_input_value(
                    'sextractor_param_path', sextractor_param_path)
                telescope_interface.set_input_value(
                    'sextractor_conv_path', sextractor_conv_path)
                telescope_interface.set_input_value('path', path)
                telescope_interface.set_input_value('fname', fname)
                self.telescope.sextractor(telescope_interface)
                # assign output values
                success = telescope_interface.get_output_value('success')
                if not success:
                    self.logger.error(
                        'Error. Star extraction process failed.')
                    continue

                # identify stars in image via sextractor
                self.slack.send_message(
                    'Calculating the PSF of the calibration image...')
                telescope_interface = TelescopeInterface('psfex')
                # assign values
                telescope_interface.set_input_value(
                    'psfex_bin_path', psfex_bin_path)
                telescope_interface.set_input_value(
                    'psfex_cfg_path', psfex_cfg_path)
                telescope_interface.set_input_value(
                    'sextractor_cat_path', sextractor_cat_path)
                self.telescope.sextractor(telescope_interface)
                # assign output values
                success = telescope_interface.get_output_value('success')
                if not success:
                    self.logger.error(
                        'Error. Calculation of PSF failed.')
                    continue
                # get psfex output
                success = self.telescope.get_file(
                    psfex_psf_remote_path, psfex_psf_local_path)
                if not success:
                    self.logger.error(
                        'Error. Could not get PSF file (%s).' % psfex_psf_remote_path)
                    continue
                # get PSF from header
                psf_fits = fits.open(psfex_psf_local_path)
                fwhm = psf_fits[1].header['PSF_FWHM']
                # add focus/psf pair to the data
                focus_psf_plot_data[focus_pos_index] = focus_pos, fwhm
                self.slack.send_message(
                    'For a focus position of %d, estimated FWHM is %s.' % (focus_pos, fwhm))

            # for now, back to the original!
            self._set_focus(focus_pos_original)

        except Exception as e:
            self.handle_error(command.group(0), 'Exception (%s).' % (e))

    def to_stars(self, command, user):
        # get sky image from SEO camera
        try:
            self.slack.send_message(
                'Transferring recent images to stars.uchicago.edu. Please wait...')
            telescope_interface = TelescopeInterface('to_stars')
            # assign input
            telescope_interface.set_input_value('image_dir', self.config.get(
                'telescope', 'itzamna_image_dir'))
            telescope_interface.set_input_value('stars_remote_dir', self.config.get(
                'stars_server', 'stars_remote_dir'))
            telescope_interface.set_input_value('stars_key_path', self.config.get(
                'stars_server', 'stars_key_path'))
            telescope_interface.set_input_value('stars_user', self.config.get(
                'stars_server', 'stars_user'))
            telescope_interface.set_input_value('stars_url', self.config.get(
                'stars_server', 'stars_url'))
            telescope_interface.set_input_value(
                'year', datetime.datetime.utcnow().strftime('%Y'))
            telescope_interface.set_input_value(
                'date', datetime.datetime.utcnow().strftime('%Y-%m-%d'))
            # create a command that applies the specified values
            self.telescope.to_stars(telescope_interface)
            telescope_interface.set_input_value('image_dir', self.config.get(
                'telescope', 'image_dir'))
            self.telescope.to_stars(telescope_interface)
            # add error handling here?
            self.slack.send_message(
                "Images uploaded to http://stars.uchicago.edu.")
        except Exception as e:
            self.handle_error(command.group(
                0), 'Failed to upload images to http://stars.uchicago.edu. Exception (%s).' % (e))

    def get_weather(self, command, user):
        base_url = self.config.get('weatherbit', 'base_url')
        icon_base_url = self.config.get('weatherbit', 'icon_base_url')
        api_key = self.config.get('weatherbit', 'api_key')
        latitude = self.config.get('telescope', 'latitude')
        longitude = self.config.get('telescope', 'longitude')
        # user the OpenWeatherMap API
        url = '%scurrent?lat=%s&lon=%s&units=I&key=%s' % (
            base_url, latitude, longitude, api_key)
        try:
            r = requests.post(url)
            if r.ok:
                data = r.json()
                weather = data.get('data')[0]
                station = weather.get('city_name')
                clouds = weather.get('clouds')
                conditions = weather.get('weather').get('description')
                temp = weather.get('temp')
                wind_speed = weather.get('wind_spd')
                wind_direction = weather.get('wind_cdir')
                humidity = weather.get('rh')
                icon_url = icon_base_url + \
                    weather.get('weather').get('icon') + '.png'
                # send weather report to Slack
                self.slack.send_message(
                    "", [{"image_url": "%s" % icon_url, "title": "Current Weather:"}])
                self.slack.send_message('>Station: %s' % station)
                self.slack.send_message('>Conditions: %s' % conditions)
                self.slack.send_message(
                    '>Temperature: %.1f° F' % temp)
                self.slack.send_message('>Clouds: %0.1f%%' % clouds)
                self.slack.send_message('>Wind Speed: %.1f mph' % wind_speed)
                self.slack.send_message(
                    '>Wind Direction: %s' % wind_direction)
                self.slack.send_message(
                    '>Humidity: %.1f%%' % humidity)
            else:
                self.handle_error(command.group(
                    0), 'Weatherbit API request (%s) failed (%d).' % (url, r.status_code))
        except Exception as e:
            self.handle_error(command.group(
                0), 'Weatherbit API request (%s) failed. Exception (%s).' % (url, e))

    # https://openweathermap.org/forecast5
    def get_forecast(self, command, user):
        base_url = self.config.get('openweathermap', 'base_url')
        icon_base_url = self.config.get('openweathermap', 'icon_base_url')
        api_key = self.config.get('openweathermap', 'api_key')
        max_forecasts = int(self.config.get(
            'openweathermap', 'max_forecasts', 5))
        latitude = self.config.get('telescope', 'latitude')
        longitude = self.config.get('telescope', 'longitude')
        timezone = self.config.get('telescope', 'timezone', 'GMT')
        # user the OpenWeatherMap API
        url = '%sforecast?lat=%s&lon=%s&units=imperial&APPID=%s' % (
            base_url, latitude, longitude, api_key)
        try:
            r = requests.post(url)
        except Exception as e:
            self.logger.error(
                'OpenWeatherMap API request (%s) failed.' % url)
            self.handle_error(command.group(0), e)
            return
        if r.ok:
            data = r.json()
            station = data.get('city').get('name', 'Unknown')
            forecasts = data.get('list')
            self.slack.send_message('Weather Forecast:')
            self.slack.send_message('>Station: %s' % station)
            for forecast in forecasts[:max_forecasts]:
                dt = datetime.datetime.utcfromtimestamp(
                    forecast.get('dt', time.time())).replace(tzinfo=pytz.utc)
                dt_local = dt.astimezone(pytz.timezone(timezone))
                icon_url = icon_base_url + \
                    forecast.get('weather')[0].get('icon', '01d') + '.png'
                weather = forecast.get('weather')[0].get('main', 'Unknown')
                clouds = int(forecast.get('clouds').get('all', 0))
                # self.slack.send_message('Date/Time: %s (%s)' % (dt_local.strftime(
                #    "%A, %B %d, %Y %I:%M%p"), dt.strftime("%A, %B %d, %Y %I:%M%p UTC")))
                dt_string = '%s (%s)' % (dt_local.strftime(
                    '%I:%M%p'), dt.strftime('%I:%M%p UTC'))
                # self.slack.send_message('Clouds: %0.1f%%' % clouds)
                if clouds > 0:
                    self.slack.send_message(
                        "", [{"image_url": "%s" % icon_url, "title": "%s (%d%%) @ %s" % (weather, clouds, dt_string)}])
                else:
                    self.slack.send_message(
                        "", [{"image_url": "%s" % icon_url, "title": "%s @ %s" % (weather, dt_string)}])
                time.sleep(1)  # don't trigger the Slack bandwidth threshold
        else:
            self.logger.error(
                'OpenWeatherMap API request (%s) failed (%d).' % (url, r.status_code))
            self.handle_error(command.group(0), e)

    def getDoAbort(self):
        global doAbort
        _doAbort = False
        self.lock.acquire()
        try:
            _doAbort = doAbort
        finally:
            self.lock.release()
        return _doAbort

    def setDoAbort(self, _doAbort):
        global doAbort
        self.lock.acquire()
        try:
            doAbort = _doAbort
        finally:
            self.lock.release()
        return

    def get_fitsFname(self, target, filter, time, bin, user, index, hdr):
        fname = '%s_%s_%ss_bin%s%s_%s_%s_seo_%d_RAW.fits' % (
            target, filter, time, bin, hdr, datetime.datetime.utcnow().strftime('%y%m%d_%H%M%S'), user.lower(), index)
        return fname

    def get_fitsPath(self, user):
        path = self.image_dir + '/' + datetime.datetime.utcnow().strftime('%Y') + '/' + \
            datetime.datetime.utcnow().strftime('%Y-%m-%d') + '/' + user.lower() + '/'
        return path

    def init_commands(self):
        try:
            self.commands = [
                {
                    'regex': r'^\\find\s(.+)$',
                    'function': self.find,
                    'description': '`\\find <object>` finds <object> in the sky (add wildcard `*` to widen the search)',
                    'hide': False
                },

                {
                    'regex': r'^\\plot(\s[0-9]+)?$',
                    'function': self.plot,
                    'description': '`\\plot <object #> or \\plot <RA (hh:mm:ss.s)> <DEC (dd:mm:ss.s)>` shows if/when object (run `\\find` first!) or coordinate is observable',
                    'hide': False
                },

                {
                    # ra dec regex should be better
                    'regex': r'^\\plot(\s[0-9\:\-\+\.]+)(\s[0-9\:\-\+\.]+)$',
                    'function': self.plot_ra_dec,
                    'description': '`\\plot <RA> <DEC>` shows if/when coordinate is observable',
                    'hide': True
                },

                {
                    'regex': r'^\\track(\s(?:on|off))$',
                    'function': self.track,
                    'description': '`\\track <on/off>` toggles telescope tracking',
                    'hide': False,
                    'lock': True
                },

                {
                    'regex': r'^\\point(\s[0-9]+)?$',
                    'function': self.point,
                    'description': '`\\point <object #> or \\point <RA (hh:mm:ss.s)> <DEC (dd:mm:ss.s)>` points the telescope to an object (run `\\find` first!) or coordinate',
                    'hide': False,
                    'lock': True
                },

                {
                    # ra dec regex should be better
                    'regex': r'^\\point(\s[0-9\:\-\+\.]+)(\s[0-9\:\-\+\.]+)$',
                    'function': self.point_ra_dec,
                    'description': '`\\point <RA> <DEC>` points the telescope to a coordinate',
                    'hide': True,
                    'lock': True
                },

                {
                    # ra dec regex should be better
                    'regex': r'^\\nudge(\s[0-9\-\+\.]+)(\s[0-9\-\+\.]+)$',
                    'function': self.offset,
                    'description': '`\\nudge <dRA> <dDEC>` offsets the telescope by dRA/dDEC degrees',
                    'hide': False,
                    'lock': True
                },

                {
                    'regex': r'^\\pinpoint(\s[0-9]+)?$',
                    'function': self.pinpoint,
                    'description': '`\\pinpoint <object #> or \\pinpoint <RA (hh:mm:ss.s)> <DEC (dd:mm:ss.s)>` uses astrometry to point the telescope to an object (run `\\find` first!) or coordinate',
                    'hide': False,
                    'lock': True
                },

                {
                    # ra dec regex should be better
                    'regex': r'^\\pinpoint(\s[0-9\:\-\+\.]+)(\s[0-9\:\-\+\.]+)$',
                    'function': self.pinpoint_ra_dec,
                    'description': '`\\pinpoint <RA> <DEC>` uses astrometry to point the telescope to a coordinate',
                    'hide': True,
                    'lock': True
                },

                {
                    'regex': r'^\\image\s([0-9\.]+)\s(1|2)\s(%s)(\s[0-9]+)?$' % '|'.join(self.config.get('telescope', 'filters').split('\n')),
                    'function': self.get_image,
                    'description': '`\\image <exposure (s)> <binning> <%s> <count>` takes an image. <count> defaults to 1.' % '|'.join(self.config.get('telescope', 'filters').split('\n')),
                    'hide': False,
                    'lock': True
                },

                {
                    'regex': r'^\\filter$',
                    'function': self.get_filter,
                    'description': '`\\filter` shows the filter',
                    'hide': False
                },

                {
                    'regex': r'^\\filter\s(%s)$' % '|'.join(self.config.get('telescope', 'filters').split('\n')),
                    'function': self.set_filter,
                    'description': '`\\filter <%s>` sets the filter' % '|'.join(self.config.get('telescope', 'filters').split('\n')),
                    'hide': False,
                    'lock': True
                },

                {
                    'regex': r'^\\focus$',
                    'function': self.get_focus,
                    'description': '`\\focus` shows the telescope focus position',
                    'hide': False
                },

                {
                    'regex': r'^\\focus\s([0-9]+)$',
                    'function': self.set_focus,
                    'description': '`\\focus <integer>` sets the telescope focus position to <integer>',
                    'hide': False,
                    'lock': True
                },

                {
                    'regex': r'^\\crack$',
                    'function': self.open_observatory,
                    'description': '`\\crack` opens the observatory',
                    'hide': False,
                    'lock': True
                },

                {
                    'regex': r'^\\keepopen\s([0-9]+)$',
                    'function': self.keepopen,
                    'description': '`\\keepopen <duration (s)>` sets timer to automatically close slit to <duration> seconds',
                    'hide': True,
                    'lock': True
                },

                {
                    'regex': r'^\\squeeze$',
                    'function': self.close_observatory,
                    'description': '`\\squeeze` closes the observatory',
                    'hide': False,
                    'lock': True
                },

                {
                    'regex': r'^\\forecast$',
                    'function': self.get_forecast,
                    'description': '`\\forecast` shows the hourly weather forecast',
                    'hide': False
                },

                {
                    'regex': r'^\\help$',
                    'function': self.get_help,
                    'description': '`\\help` shows this message',
                    'hide': False
                },

                {
                    'regex': r'^\\lock$',
                    'function': self.set_lock,
                    'description': '`\\lock` locks the telescope for use by you',
                    'hide': False
                },

                {
                    'regex': r'^\\unlock$',
                    'function': self.unlock,
                    'description': '`\\unlock` unlocks the telescope for use by others',
                    'hide': False
                },

                {
                    'regex': r'^\\clear$',
                    'function': self.clear_lock,
                    'description': '`\\clear` clears the telescope lock',
                    'hide': True
                },

                {
                    'regex': r'^\\who$',
                    'function': self.get_who,
                    'description': '`\\who` shows who has the telescope locked',
                    'hide': False
                },

                {
                    'regex': r'^\\weather$',
                    'function': self.get_weather,
                    'description': '`\\weather` shows the current weather conditions',
                    'hide': False
                },

                {
                    'regex': r'^\\clouds$',
                    'function': self.get_clouds,
                    'description': '`\\clouds` shows the current cloud cover',
                    'hide': False
                },

                {
                    'regex': r'^\\sun$',
                    'function': self.get_sun,
                    'description': '`\\sun` shows the sun altitude',
                    'hide': False
                },

                {
                    'regex': r'^\\moon$',
                    'function': self.get_moon,
                    'description': '`\\moon` shows the moon altitude and phase',
                    'hide': False
                },

                {
                    'regex': r'^\\where$',
                    'function': self.get_where,
                    'description': '`\\where` shows where the telescope is pointing',
                    'hide': False
                },

                {
                    'regex': r'^\\ccd$',
                    'function': self.get_ccd,
                    'description': '`\\ccd` shows CCD information',
                    'hide': False
                },

                {
                    'regex': r'^\\ccd\s(cool|warm)\s([\.\+\-0-9]*)$',
                    'function': self.set_ccd,
                    'description': '`\\ccd <cool|warm> <T (°C)>` cools/warms CCD to specified temperature, T',
                    'hide': True,
                    'lock': True
                },

                {
                    'regex': r'^\\hdr$',
                    'function': self.get_hdr,
                    'description': '`\\hdr` shows the status of the CCD HDR (High Dynamic Range) mode',
                    'hide': False
                },

                {
                    'regex': r'^\\hdr\s(on|off)$',
                    'function': self.set_hdr,
                    'description': '`\\hdr <on|off>` enables/disables the CCD HDR (High Dynamic Range) mode',
                    'hide': False,
                    'lock': True
                },

                {
                    'regex': r'^\\preview$',
                    'function': self.get_preview,
                    'description': '`\\preview` shows the status of the FITS image preview',
                    'hide': False
                },

                {
                    'regex': r'^\\preview\s(on|off)$',
                    'function': self.set_preview,
                    'description': '`\\preview <on|off>` enables/disables the FITS image preview',
                    'hide': False,
                    'lock': True
                },

                {
                    'regex': r'^\\share\s(on|off)$',
                    'function': self.share_lock,
                    'description': '`\\share <on|off>` enables/disables others to access a locked telescope',
                    'hide': False,
                    'lock': True
                },

                {
                    'regex': r'^\\clearsky$',
                    'function': self.get_clearsky,
                    'description': '`\\clearsky` shows Clear Sky chart(s)',
                    'hide': False
                },

                {
                    'regex': r'^\\skycam$',
                    'function': self.get_skycam,
                    'description': '`\\skycam` shows skycam image(s)',
                    'hide': False
                },

                {
                    'regex': r'^\\dark\s([0-9\.]+)\s(1|2)(\s[0-9]+)?$',
                    'function': self.get_dark,
                    'description': '`\\dark <exposure (s)> <binning> <count>` takes a dark frame. <count> defaults to 1.',
                    'hide': False,
                    'lock': True
                },

                {
                    'regex': r'^\\bias\s(1|2)(\s[0-9]+)?$',
                    'function': self.get_bias,
                    'description': '`\\bias <binning> <count>` takes a bias frame. <count> defaults to 1.',
                    'hide': False,
                    'lock': True
                },

                {
                    'regex': r'^\\tostars$',
                    'function': self.to_stars,
                    'description': '`\\tostars` uploads images to http://stars.uchicago.edu',
                    'hide': False
                },

                {
                    'regex': r'^\\slit$',
                    'function': self.get_slit,
                    'description': '`\\slit` shows status of dome slit',
                    'hide': False
                },

                {
                    'regex': r'^\\slit\s(open|close)$',
                    'function': self.set_slit,
                    'description': '`\\slit <open|close>` opens/closes the dome slit.',
                    'hide': False,
                    'lock': True
                },

                {
                    'regex': r'^\\dome$',
                    'function': self.get_dome,
                    'description': '`\\dome` shows dome slit azimuth',
                    'hide': False
                },

                {
                    'regex': r'^\\dome\scenter$',
                    'function': self.center_dome,
                    'description': '`\\dome center` centers the dome slit on telescope',
                    'hide': False,
                    'lock': True
                },

                {
                    'regex': r'^\\home\sdome$',
                    'function': self.home_dome,
                    'description': '`\\home dome` calibrates the dome movement',
                    'hide': False,
                    'lock': True
                },

                {
                    'regex': r'^\\abort$',
                    'function': self.abort,
                    'description': '`\\abort` terminates the current task',
                    'hide': False,
                    'lock': True
                },

                {
                    'regex': r'^\\hocus$',
                    'function': self.hocus,
                    'description': '`\\hocus` calibrates the focus setting',
                    'hide': False,
                    'lock': True
                }
            ]
        except Exception as e:
            raise Exception(
                'Failed to build list of commands. Exception (%s).' % e)
