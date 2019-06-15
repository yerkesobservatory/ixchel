import os
import logging
import ConfigParser
import time
import datetime
import json
import re
from ixchel_command import IxchelCommand
from slack import Slack
from config import Config
from telescope import Telescope

# logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - - %(name)s - %(funcName)s - %(message)s',
    handlers=[
        logging.FileHandler("ixchel.log"),
        logging.StreamHandler()
    ])
logger = logging.getLogger('ixchel')

# config
cfg_file_path = 'ixchel.cfg'


class Ixchel:
    # main loop delay
    loop_delay_s = 0.5

    # main ping delay
    slack_ping_delay_s = 5

    # reconnect delay
    slack_reconnect_delay_s = 10

    def __init__(self, config, telescope):
        self.logger = logging.getLogger('ixchel.Ixchel')
        self.config = config
        # init Slack interface
        self.slack = Slack(self.config)
        self.username = self.config.get('slack', 'username')
        self.channel = self.config.get('slack', 'channel')
        self.channel_id = self.slack.get_channel_id(self.channel)
        # the telescope
        self.telescope = telescope
        # init IxchelCommand
        self.ixchel_commands = IxchelCommand(
            self.config, self.slack, self.telescope)

    def loop(self):
        # connect to Slack
        self.slack.connect()
        # main loop
        while True:
            while self.slack.connected:
                # check to be sure we are still connected to the server
                self.slack.ping()
                # get messages
                messages = self.slack.read_messages()
                # parse messages
                self.parse(messages)
                # sleep a bit
                time.sleep(self.loop_delay_s)
            # sleep before trying to reconnect
            time.sleep(self.slack_reconnect_delay_s)
            # reconnect
            self.slack.connect()

    def parse(self, messages):
        for message in messages:
            if not 'type' in message:
                continue
            elif message['type'] == 'message':
                # ignore any messages sent from this bot
                if 'username' in message and message['username'] == self.username:
                    continue
                # only process commands from the self.channel
                if 'channel' in message:
                    # message posted in ixchel channel?
                    if message['channel'] == self.channel_id:
                        self.process(message)
                    else:  # message posted directly to bot
                        self.logger.debug('Received direct message.')
                        self.slack.send_message('Please use the channel #%s for communications with %s.' % (
                            self.channel, self.username), message['channel'], self.username)
            elif message['type'] == 'pong':
                self.logger.debug('Received pong message.')
            else:
                continue

    def process(self, message):
        if not 'text' in message:
            self.logger.error('Invalid message received.')
            return False
        text = message['text'].strip()
        if re.search(r'^\\\w+', text):
            self.ixchel_commands.parse(message)
        else:
            self.logger.debug('Received non-command text (%s).' % text)


def main():
    logger.info('Starting ixchel...')

    # read configuration file
    logger.info('Reading configuration from file (%s)...' % cfg_file_path)
    if not os.path.exists(cfg_file_path):
        raise Exception('Configuration file (%s) is missing.' % cfg_file_path)
    config = Config(cfg_file_path)

    # init the telescope
    telescope = Telescope(config)

    # Mayan goddess of the moon, medicine, and birth (mid-wifery). Stronger half of Itzamna!
    ixchel = Ixchel(config, telescope)
    ixchel.loop()


if __name__ == "__main__":
    main()
