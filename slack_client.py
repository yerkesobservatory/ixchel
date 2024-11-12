"""

The Slack module wraps the Slack Python API to allow the Ixchel and IxchelCommand modules
to send/receive data in the Slack channel.

"""

import logging
import requests
import json
import datetime
import time
import os
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk.errors import SlackApiError
import asyncio
import concurrent


class Slack:
    def __init__(self, ixchel):
        self.logger = logging.getLogger('Slack')
        self.ixchel = ixchel
        self.config = ixchel.config
        self.bot_token = self.config.get('slack', 'bot_token')
        self.app_token = self.config.get('slack', 'app_token')
        self.channel = self.config.get('slack', 'channel_name')
        self.channel_id = self.config.get('slack', 'channel_id')
        self.bot_name = self.config.get('slack', 'bot_name')
        self.dt_last_ping = datetime.datetime.now()
        self.ping_delay_s = float(self.config.get('slack', 'ping_delay_s', 5))
        self.reconnect_delay_s = float(self.config.get(
            'slack', 'reconnect_delay_s', 10))
        self.loop = asyncio.get_event_loop()
        # this is probably not needed anymore, but I am hanging on to it for now
        self.connected = True
        
        # Establish the Slack app
        self.app = App(token=self.bot_token)

        # Create the RTM mode
        self.handler = SocketModeHandler(self.app, self.app_token)


    # def send_typing(self, channel=None):
    #     # use default values if none sent
    #     if channel == None:
    #         channel = self.channel
    #     try:
    #         self.rtm.typing(channel)
    #     except Exception as e:
    #         self.logger.error('Could not send typing. Exception (%s).' % e)

    def is_connected(self):
        try:
            # self.app.client.ping()
            return True
        except client_err.SlackClientNotConnectedError as e:
            self.logger.error(
                'Slack RTM client is not connected. Exception (%s).' % e)
            return False

    def send_block_message(self, block_message, channel=None, username=None):
        if not self.connected:
            self.logger.warning(
                'Could not send message (%s). Not connected.' % block_message)
            return False
        # use default values if none sent
        if channel == None:
            channel = self.channel_id
        if username == None:
            username = self.bot_name
        try:
            self.app.client.chat_postMessage(
                channel=channel,
                blocks=json.loads(block_message),
                username=username
            )
        except Exception as e:
            self.logger.error(
                'Could not send block message (%s). Exception (%s).' % (block_message, e))
            return False
        return True

    def send_message(self, message, attachments=None, channel=None, username=None, blocks=None):
        if not self.connected:
            self.logger.warning(
                'Could not send message (%s). Not connected.' % message)
            return False
        # use default values if none sent
        if channel == None:
            channel = self.channel_id
        if username == None:
            username = self.bot_name
        try:
            self.app.client.chat_postMessage(
                channel=channel,
                text=message,
                blocks=blocks,
                username=username,
                attachments=attachments
            )
            self.logger.info('Sent Slack message: %s.', message)
        except Exception as e:
            self.logger.error(
                'Could not send message (%s). Exception (%s).', message, e)
            return False
        return True

    def send_file(self, path, title=None, channel=None, username=None):
        if not os.path.exists(path):
            self.logger.error(
                'File (%s) does not exist.', path)
            return False
        if not self.connected:
            self.logger.warning(
                'Could not send file (%s). Not connected.', path)
            return False
        # use default values if none sent
        if channel == None:
            channel = self.channel_id
        if username == None:
            username = self.bot_name
        try:
            files = {'file': open(path, 'rb')}
            data = {'channels': channel,
                    'title': title, 'token': self.bot_token}
            
            # Attempt the file upload
            response = self.app.client.files_upload_v2(
                channel=channel,
                file=path,
                title=title
            )
            
            if not response['ok']:
                self.logger.error(
                    'Could not send file (%s). Bad upload.', path)
                return False

        except Exception as e:
            self.logger.error(
                'Could not send file (%s). Exception (%s).', path, e)
            return False
        return response['ok']

    # def get_channels(self):
    #     try:
    #         result = self.web.api_call("channels.list")
    #         return result['channels']
    #     except Exception as e:
    #         self.logger.error(
    #             'Failed to get channel list. Exception (%s).', e)
    #         return []

    # def get_channel_id(self, channel):
    #     channel_id = None
    #     for ch in self.get_channels():
    #         if 'name' in ch and ch['name'] == channel:
    #             channel_id = ch['id']
    #             self.logger.info('Channel (%s) id is %s.', channel, channel_id)
    #             break
    #     return channel_id

    # def get_users(self):
    #     try:
    #         result = self.web.api_call("users.list")
    #         return result['members']
    #     except Exception as e:
    #         self.logger.error(
    #             'Failed to get user list. Exception (%s).' % e)
    #         return []

    def get_user_by_id(self, uid):
        try:  

            # Look for the user's info
            result = self.app.client.users_info(user=uid)
            # self.logger.info(result)
            if 'error' in result: # ooops
                self.logger.error('Failed to find user. Error (%s).', result['error'])
                return {}
            else:           
                return result['user']
        except Exception as e:
            self.logger.error(
                'Failed to find user. Exception (%s).', e)
            return {}
