from slackclient import SlackClient
import logging
import requests
import json
import datetime
import time
import os


class Slack:
    def __init__(self, ixchel):
        self.logger = logging.getLogger('ixchel.Slack')
        self.ixchel = ixchel
        self.config = ixchel.config
        self.token = self.config.get('slack', 'token')
        self.channel = self.config.get('slack', 'channel')
        self.username = self.config.get('slack', 'username')
        self.dt_last_ping = datetime.datetime.now()
        self.ping_delay_s = float(self.config.get('slack', 'ping_delay_s', 5))
        self.reconnect_delay_s = float(self.config.get(
            'slack', 'reconnect_delay_s', 10))
        self.connected = False
        # init the slack client
        self.sc = SlackClient(self.token)

    def connect(self):
        try:
            self.connected = self.sc.rtm_connect()
        except Exception as e:
            self.logger.error('Connect failed. Exception (%s).' % e.message)
            self.connected = False

    def ping(self):
        if (datetime.datetime.now() - self.dt_last_ping).total_seconds() > self.ping_delay_s:
            try:
                self.sc.server.websocket.send(json.dumps({"type": "ping"}))
                self.dt_last_ping = datetime.datetime.now()
                return True
            except Exception as e:
                self.logger.error('Ping failed. Exception (%s).' % e.message)
                self.connected = False
                return False

    def send_typing(self, channel=None):
        # use default values if none sent
        if channel == None:
            channel = self.channel
        typing_event_json = {
            "id": 1,
            "type": "typing",
            "channel": self.get_channel_id(channel)
        }
        self.sc.server.websocket.send(json.dumps(typing_event_json))

    def read_messages(self):
        try:
            return self.sc.rtm_read()
        except Exception as e:
            self.logger.error(
                'Read messages failed. Exception (%s).' % e.message)
            self.connected = False
            return []

    def send_message(self, message, attachments=None, channel=None, username=None):
        if not self.connected:
            self.logger.warning(
                'Could not send message (%s). Not connected.' % message)
            return False
        # use default values if none sent
        if channel == None:
            channel = self.channel
        if username == None:
            username = self.username
        try:
            self.sc.api_call(
                "chat.postMessage",
                channel=channel,
                text=message,
                username=username,
                attachments=attachments
            )
        except Exception as e:
            self.logger.error(
                'Could not send message (%s). Exception (%s).' % (message, e.message))
            return False
        return True

    def send_file(self, path, title=None, channel=None, username=None):
        if not os.path.exists(path):
            self.logger.error(
                'File (%s) does not exist.' % path)
            return False
        if not self.connected:
            self.logger.warning(
                'Could not send file (%s). Not connected.' % path)
            return False
        # use default values if none sent
        if channel == None:
            channel = self.channel
        if username == None:
            username = self.username
        try:
            files = {'file': open(path, 'rb')}
            data = {'channels': channel,
                    'title': title, 'token': self.token}
            r = requests.post('https://slack.com/api/files.upload',
                              files=files, data=data)
        except Exception as e:
            self.logger.error(
                'Could not send file (%s). Exception.' % (path, e.message))
            return False
        return r.ok

    def get_channels(self):
        try:
            result = self.sc.api_call("channels.list")
            return result['channels']
        except Exception as e:
            self.logger.error(
                'Failed to get channel list. Exception (%s).' % e.message)
            return []

    def get_channel_id(self, channel):
        channel_id = None
        for ch in self.get_channels():
            if 'name' in ch and ch['name'] == channel:
                channel_id = ch['id']
                self.logger.debug('Channel (%s) id is %s.' %
                                  (channel, channel_id))
                break
        return channel_id

    def get_users(self):
        try:
            result = self.sc.api_call("users.list")
            return result['members']
        except Exception as e:
            self.logger.error(
                'Failed to get user list. Exception (%s).' % e.message)
            return []

    def get_user_by_id(self, id):
        for u in self.get_users():
            if 'id' in u and u['id'] == id:
                return u
        self.logger.error('No user found with id = %s.' % id)
        return {}

    # def get_user_id(self, username):
    #     user_id = None
    #     for user in self.get_users():
    #         if 'real_name' in user and user['real_name'] == username:
    #             user_id = user['id']
    #             self.logger.debug('User (%s) id is %s.' %
    #                               (username, user_id))
    #             break
    #     return user_id

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
    #     except Exception as e:
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
    #     except Exception as e:
    #         self.logger.error(
    #             'Could not set user photo (%s). Exception.' % user_photo_path)
    #         return False
    #     return r.ok
