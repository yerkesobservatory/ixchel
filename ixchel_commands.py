# -*- coding: utf-8 -*-

import logging
import re
import requests


class IxchelCommands:

    commands = []

    def __init__(self, config, slack):
        self.logger = logging.getLogger('ixchel.IxchelCommands')
        self.config = config
        self.channel = self.config.get('slack', 'channel')
        self.username = self.config.get('slack', 'username')
        self.slack = slack
        # build list of backslash commands
        self.init_commands()

    def parse(self, message):
        text = message['text'].strip()
        for cmd in self.commands:
            if re.search(cmd['regex'], text, re.IGNORECASE):
                user = self.slack.get_user_by_id(message.get('user'))
                self.logger.debug('Received the command: %s from %s.' % (
                    text, user.get('name')))
                cmd['function'](text, user)
                return
        self.slack.send_message(
            '%s does not recognize your command (%s).' % (self.username, text))

    def help(self, text, user):
        help_message = 'Here are some helpful tips:\n' + '>Please report %s issues here: https://github.com/mcnowinski/seo/issues/new\n' % self.username + \
            '>A more detailed %s tutorial can be found here: https://stoneedgeobservatory.com/guide-to-using-itzamna/\n' % self.username
        for cmd in self.commands:
            if not cmd['hide']:
                help_message += '>%s\n' % cmd['description']
        self.slack.send_message(help_message)

    def weather(self, text, user):
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
            if r.ok:
                data = r.json()
                self.logger.debug(data)
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
                return
            else:
                self.slack.send_message(
                    'OpenWeatherMap API request failed (%s).' % (url))
        except:
            self.logger.error(
                'Exception occurred getting the current weather from OpenWeatherMap.')
        self.slack.send_message(
            '%s was unable to grant your wish (%s).' % (self.username, text))
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
#                 '>Please report itzamna issues here: https://github.com/mcnowinski/seo/issues/new\n' +
#                 '>A more detailed itzamna tutorial can be found here: https://stoneedgeobservatory.com/guide-to-using-itzamna/\n' +
#                 '>`\\help` shows this message\n' +
#                 '>`\\where` shows where the telescope is pointing\n' +
#                 '>`\\weather` shows the current weather conditions\n' +
#                 '>`\\forecast` shows the hourly weather forecast\n' +
#                 '>`\\clouds` shows the current cloud cover\n' +
#                 '>`\\focus` shows the current focus position\n' +
#                 '>`\\focus <position>` sets the current focus position\n' + \
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
                'regex': r'^\\help$',
                'function': self.help,
                'description': '`\\help` shows this message',
                'hide': False
            },

            {
                'regex': r'^\\weather$',
                'function': self.weather,
                'description': '`\\weather` shows the current weather conditions',
                'hide': False
            },

        ]
