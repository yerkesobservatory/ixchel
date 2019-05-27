from slackclient import SlackClient
import logging
import requests
import json
import datetime
import time
import os


class Slack:
    def __init__(self, config):
        self.logger = logging.getLogger('ixchel.Slack')
        self.config = config
        self.token = self.config.get('slack', 'token')
        self.channel = self.config.get('slack', 'channel')
        self.username = self.config.get('slack', 'username')
        self.dt_last_ping = datetime.datetime.now()
        self.ping_delay_s = self.config.getfloat('slack', 'ping_delay_s')
        self.reconnect_delay_s = self.config.getfloat(
            'slack', 'reconnect_delay_s')
        self.connected = False
        # init the slack client
        self.sc = SlackClient(self.token)

    def connect(self):
        try:
            self.connected = self.sc.rtm_connect()
        except:
            self.logger.error('Connect failed.')
            self.connected = False

    def ping(self):
        if (datetime.datetime.now() - self.dt_last_ping).total_seconds() > self.ping_delay_s:
            try:
                self.sc.server.websocket.send(json.dumps({"type": "ping"}))
                self.dt_last_ping = datetime.datetime.now()
                return True
            except:
                self.logger.error('Ping failed.')
                self.connected = False
                return False

    def read_messages(self):
        try:
            return self.sc.rtm_read()
        except:
            self.logger.error(
                'Read messages failed.')
            self.connected = False
            return []

    def send_message(self, message):
        if not self.connected:
            self.logger.warning(
                'Could not send message (%s). Not connected.' % message)
            return False
        try:
            self.sc.api_call(
                "chat.postMessage",
                channel=self.channel,
                text=message,
                username=self.username,
            )
        except:
            self.logger.error(
                'Could not send message (%s). Exception.' % message)
            return False
        return True

    def send_file(self, path, title=''):
        if not os.path.exists(path):
            self.logger.error(
                'File (%s) does not exist.' % path)
            return False
        if not self.connected:
            self.logger.warning(
                'Could not send file (%s). Not connected.' % path)
            return False
        try:
            files = {'file': open(path, 'rb')}
            data = {'channels': self.channel,
                    'title': title, 'token': self.token}
            r = requests.post('https://slack.com/api/files.upload',
                              files=files, data=data)
        except:
            self.logger.error(
                'Could not send file (%s). Exception.' % path)
            return False
        return r.ok

    # def get_channels(self):
    #     try:
    #         result = self.sc.api_call("channels.list")
    #         return result['channels']
    #     except:
    #         self.logger.error('Could not get channel list.')
    #         return []

    # def join_channel(self, channel):
    #     channel_id = None
    #     for ch in self.get_channels():
    #         if ch['name'] == channel:
    #             channel_id = ch['id']
    #             self.logger.debug('Channel (%s) id is %s.' %
    #                               (channel, channel_id))
    #             break
    #     if channel_id == None:
    #         self.logger.error('Could not find channel (%s).' % channel)
    #         return False
    #     try:
    #         self.sc.api_call("channels.join", channel=channel_id)
    #     except:
    #         self.logger.error(
    #             'Could not join channel (%s). Exception.' % channel)
    #         return False
    #     return True

    # def set_user_photo(self, user_photo_path):
    #     if not os.path.exists(user_photo_path):
    #         self.logging.error(
    #             'User photo (%s) does not exist.' % user_photo_path)
    #         return False
    #     if not self.connected:
    #         self.logger.warning(
    #             'Could not set user photo (%s). Not connected.' % user_photo_path)
    #         return False
    #     try:
    #         files = {'image': open(user_photo_path, 'rb')}
    #         data = {'token': self.token}
    #         r = requests.post(
    #             'https://slack.com/api/users.setPhoto', files=files, data=data)
    #     except:
    #         self.logger.error(
    #             'Could not set user photo (%s). Exception.' % user_photo_path)
    #         return False
    #     return r.ok
