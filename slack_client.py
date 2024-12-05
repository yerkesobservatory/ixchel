"""

The Slack module wraps the Slack Python API to allow the Ixchel and IxchelCommand modules
to send/receive data in the Slack channel.

"""

import logging
import json
import datetime
import os
import asyncio
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk.errors import SlackApiError


class Slack:
    """ Slack class is Ixchel's wrapper around the slack-bolt sdk
    """
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

        # This is probably not needed anymore, but I am hanging on to it for now
        self.connected = True

        # Establish the Slack app
        self.app = App(token=self.bot_token)

        # Create the socket mode handler
        self.handler = SocketModeHandler(self.app, self.app_token)

    
    def is_connected(self):
        """ Checks whether we are currently to the Slack bot

        Returns:
            bool: whether or not we are connected
        """
        try:
            self.app.client.auth_test()
            return True
        except SlackApiError as e:
            self.logger.error(
                'Slack web client is not connected. Exception (%s).', e.response['error'])
            return False

    def send_block_message(self, block_message, channel=None, username=None):
        """ Sends a block-style message to the given Slack interface
            (May not be used?)

        Args:
            block_message (dict): _description_
            channel (string, optional): Channel ID to send to. Defaults to the bot's init value.
            username (string, optional): Username to send with. Defaults to the bot's init value.

        Returns:
            bool: Send successful?
        """
        if not self.connected:
            self.logger.warning(
                'Could not send message (%s). Not connected.', block_message)
            return False

        # Use default values if none sent
        if channel is None:
            channel = self.channel_id
        if username is None:
            username = self.bot_name

        try:
            self.app.client.chat_postMessage(
                channel=channel,
                blocks=json.loads(block_message),
                username=username
            )
        except Exception as e:
            self.logger.error(
                'Could not send block message (%s). Exception (%s).', block_message, e)
            return False
        return True

    def send_message(self, message, attachments=None, channel=None, username=None, blocks=None):
        """ Sends a simple message to the given Slack interface

        Args:
            message (string): Message to be sent
            attachments (dict, optional): Slack attachments object. Defaults to None.
            channel (string, optional): Channel ID to send to. Defaults to the bot's init value.
            username (string, optional): Username to send with. Defaults to the bot's init value.
            blocks (dict, optional): _description_. Defaults to None.
s
        Returns:
            bool: Send successful?
        """
        if not self.connected:
            self.logger.warning(
                'Could not send message (%s). Not connected.', message)
            return False

        # Use default values if none sent
        if channel is None:
            channel = self.channel_id
        if username is None:
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
        """ Sends a file to the given Slack interface

        Args:
            path (string): filepath
            title (string, optional): Title of the image to be displaced on Slack. Defaults to the filename.
            channel (string, optional): Channel ID to send to. Defaults to the bot's init value.
            username (string, optional): Username to send with. Defaults to the bot's init value.

        Returns:
            bool: Send successful?
        """
        if not os.path.exists(path):
            self.logger.error(
                'File (%s) does not exist.', path)
            return False
        if not self.connected:
            self.logger.warning(
                'Could not send file (%s). Not connected.', path)
            return False

        # Use default values if none sent
        if channel is None:
            channel = self.channel_id
        if username is None:
            username = self.bot_name

        try:
            files = {'file': open(path, 'rb')}
            data = {'channels': channel,
                    'title': title, 'token': self.bot_token}

            # Attempt the file upload (New 2024 API)
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

    def get_user_by_id(self, uid):
        """ Finds a Slack user via their User ID

        Args:
            uid (string): Slack User ID

        Returns:
            dict : Slack user object, or {}
        """
        try:
            # Look for the user's info
            result = self.app.client.users_info(user=uid)
            if 'error' in result: # ooops
                self.logger.error('Failed to find user. Error (%s).', result['error'])
                return {}
            return result['user']

        except Exception as e:
            self.logger.error(
                'Failed to find user. Exception (%s).', e)
            return {}
