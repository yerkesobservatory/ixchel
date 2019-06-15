# -*- coding: utf-8 -*-

import logging
import re
import requests
import time
import datetime
import pytz


class IxchelCommands:

    commands = []

    def __init__(self, config, slack, telescope):
        self.logger = logging.getLogger('ixchel.IxchelCommands')
        self.config = config
        self.channel = self.config.get('slack', 'channel')
        self.username = self.config.get('slack', 'username')
        self.slack = slack
        self.telescope = telescope
        # build list of backslash commands
        self.init_commands()

    def parse(self, message):
        text = message['text'].strip()
        for cmd in self.commands:
            command = re.search(cmd['regex'], text, re.IGNORECASE)
            if command:
                user = self.slack.get_user_by_id(message.get('user'))
                self.logger.debug('Received the command: %s from %s.' % (
                    command.group(0), user.get('name')))
                cmd['function'](command, user)
                return
        self.slack.send_message(
            '%s does not recognize your command (%s).' % (self.username, text))

    def handle_error(self, text, e):
        self.logger.error(
            'Command failed (%s). Exception (%s).' % (text, e))
        self.slack.send_message('Error. Command (%s) failed.' % text)

    def get_help(self, command, user):
        help_message = 'Here are some helpful tips:\n' + '>Please report %s issues here: https://github.com/mcnowinski/seo/issues/new\n' % self.username + \
            '>A more detailed %s tutorial can be found here: https://stoneedgeobservatory.com/guide-to-using-itzamna/\n' % self.username
        for cmd in self.commands:
            if not cmd['hide']:
                help_message += '>%s\n' % cmd['description']
        self.slack.send_message(help_message)

    def get_where(self, command, user):
        try:
            # query telescope
            outputs = self.telescope.get_where()
            # assign values
            ra = outputs['ra']['value']
            dec = outputs['dec']['value']
            alt = outputs['alt']['value']
            az = outputs['az']['value']
            slewing = int(outputs['slewing']['value'])
            # send output to Slack
            self.slack.send_message('Telescope Pointing:')
            self.slack.send_message('>RA: %s' % ra)
            self.slack.send_message('>DEC: %s' % dec)
            self.slack.send_message(u'>Alt: %s°' % alt)
            self.slack.send_message(u'>Az: %s°' % az)
            if slewing == 1:
                self.slack.send_message('>Slewing? Yes')
            else:
                self.slack.send_message('>Slewing? No')
        except Exception as e:
            self.handle_error(command.group(0), e)

    def get_clouds(self, command, user):
        try:
            # query telescope
            outputs = self.telescope.get_precipitation()
            # assign values
            clouds = float(outputs['clouds']['value'])
            # send output to Slack
            self.slack.send_message('Cloud cover is %d%%.' % int(clouds*100))
        except Exception as e:
            self.handle_error(command.group(0), e)

    def get_focus(self, command, user):
        try:
            # query telescope
            outputs = self.telescope.get_focus()
            # assign values
            pos = int(outputs['pos']['value'])
            # send output to Slack
            self.slack.send_message('Focus position is %d.' % pos)
        except Exception as e:
            self.handle_error(command.group(0), e)

    def set_focus(self, command, user):
        try:
            pos = int(command.group(1))
            # query telescope
            outputs = self.telescope.set_focus(pos)
            # assign values
            pos = int(outputs['pos']['value'])
            # send output to Slack
            self.slack.send_message('Focus position is %d.' % pos)
        except Exception as e:
            self.handle_error(command.group(0), e)

    def get_lock(self, command, user):
        try:
            # query telescope
            outputs = self.telescope.get_lock()
            # assign values
            email = int(outputs['email']['value'])
            # send output to Slack
            self.slack.send_message(
                'Telescope is currently locked by %s.' % email)
        except Exception as e:
            self.handle_error(command.group(0), e)

    # https://openweathermap.org/weather-conditions
    def get_weather(self, command, user):
        base_url = self.config.get('openweathermap', 'base_url')
        icon_base_url = self.config.get('openweathermap', 'icon_base_url')
        api_key = self.config.get('openweathermap', 'api_key')
        latitude = self.config.get('telescope', 'latitude')
        longitude = self.config.get('telescope', 'longitude')
        # user the OpenWeatherMap API
        url = '%sweather?lat=%s&lon=%s&units=imperial&APPID=%s' % (
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
            station = data.get('name', 'Unknown')
            clouds = data.get('clouds').get('all', 0)
            conditions = data.get('weather')[0].get('main', 'Unknown')
            temp = data.get('main').get('temp', 0)
            wind_speed = data.get('wind').get('speed', 0)
            wind_direction = data.get('wind').get('deg', 0)
            humidity = data.get('main').get('humidity', 0)
            icon_url = icon_base_url + \
                data.get('weather')[0].get('icon', '01d') + '.png'
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
                '>Wind Direction: %.1f°' % wind_direction)
            self.slack.send_message(
                '>Humidity: %.1f%%' % humidity)
        else:
            self.logger.error(
                'OpenWeatherMap API request (%s) failed (%d).' % (url, r.status_code))
            self.handle_error(command.group(0), e)

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
                #self.slack.send_message('Clouds: %0.1f%%' % clouds)
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

    # {"clouds": {"all": 1}, "name": "Sonoma", "visibility": 9656,
    # "sys": {"country": "US", "sunset": 1559359588, "message": 0.0116, "type": 1, "id": 5152, "sunrise": 1559306926},
    # "weather": [{"main": "Mist", "id": 701, "icon": "50n", "description": "mist"}],
    # "coord": {"lat": 38.26, "lon": -122.44},
    # "base": "stations", "timezone": -25200, "dt": 1559359487,
    # "main": {"pressure": 1011, "temp_min": 285.15, "temp_max": 300.15, "temp": 292.59, "humidity": 100},
    # "id": 5397095, "wind": {"speed": 2.6, "deg": 320}, "cod": 200}
    # send_message("", [{"image_url": "%s" %
    #                    icon_url, "title": "Current Weather:"}])
    # send_message(">%s" % (last_update))
    # send_message(">Conditions: %s" % (weather))
    # send_message(">Temperature: %s" % (temp))
    # send_message(">Winds: %s" % (wind))
    # send_message(">Humidity: %s" % (rh))
    # send_message(">Local Station: %s (%s)" % (location, station))
    # send_message("\n")

# send_message(user_name + ', here are some helpful tips:\n' +
#                 # '>`\\stats` shows the weekly telescope statistics\n' + \
#                 '>`\\clearsky` shows the Clear Sky chart(s)\n' + \
#                 '>`\\skycam` shows nearby skycam images\n' + \
#                 '>`\\find <object>` finds <object> position in sky (add wildcard `*` to widen search)\n' + \
#                 '>`\\plot <object#>` shows if/when <object> is observable (run `\\find` first!)\n' + \
#                 '>`\\lock` locks the telescope\n' + \
#                 '>`\\unlock` unlocks the telescope\n' + \
#                 '>`\\crack` opens the observatory\n' + \
#                 '>`\\squeeze` closes the observatory\n' + \
#                 '>`\\share <on/off>` shares/unshares a locked telescope with others\n' + \
#                 #'>`\\homer` re-homes the scope and dome (this will `\squeeze` the observatory!)\n'
#                 '>`\\point <RA (hh:mm:ss.s)> <DEC (dd:mm:ss.s)>` or `\\point <object#>` points the telescope\n' + \
#                 '>`\\pinpoint <RA (hh:mm:ss.s)> <DEC (dd:mm:ss.s)>` or `\\pinpoint <object#>` pinpoints the telescope\n' + \
#                 # '>`\\track <on/off>` toggles telescope tracking\n' + \
#                 # '>`\\nudge <dRA in arcmin> <dDEC in arcmin>` offsets the telescope pointing\n' + \
#                 '>`\\image <exposure> <binning> <filter>` takes a picture\n' + \
#                 '>`\\bias <binning>` takes a bias frame\n' + \
#                 '>`\\dark <exposure> <binning>` takes a dark frame.\n' + \
#                 '>`\\tostars` uploads recent images to <%s|stars> (run this command at the end of your session)\n' % stars_url
#                 )

    def init_commands(self):
        self.commands = [

            {
                'regex': r'^\\focus$',
                'function': self.get_focus,
                'description': '`\\focus` shows the current focus position',
                'hide': False
            },

            {
                'regex': r'^\\focus\s([0-9]+)$',
                'function': self.set_focus,
                'description': '`\\focus <integer>` sets the current focus position to <integer>',
                'hide': False
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
                'function': self.get_lock,
                'description': '`\\lock` locks the telescope for use',
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
                'regex': r'^\\where$',
                'function': self.get_where,
                'description': '`\\where` shows where the telescope is currently pointing',
                'hide': False
            },

        ]
