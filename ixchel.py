"""

The Ixchel module is the primary interface with users on Slack.
It monitors the Slack channel for user input and passes commands to the
IxchelCommand module. Ixchel also monitors (and resets) connections to Slack and
the telescope host machine (aster) via ssh..

"""

from datetime import datetime
import os
import logging
import time
import datetime
import json
import re
import slack
import asyncio
import signal
import threading
from globals import doAbort
from ixchel_command import IxchelCommand
from slack_client import Slack
from config import Config
from telescope import Telescope

# logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(funcName)s - %(message)s',
    handlers=[
        logging.FileHandler("ixchel.log"),
        logging.StreamHandler()
    ])
logger = logging.getLogger('ixchel')

# config
cfg_file_path = './cfg/ixchel.cfg'


class Ixchel:

    def __init__(self, config: Config):
        self.logger = logging.getLogger('Ixchel')
        # init config
        self.config = config
        # update settings
        self.bot_name = self.config.get('slack', 'bot_name')
        self.channel = self.config.get('slack', 'channel_name')
        self.channel_id = self.config.get('slack', 'channel_id')
        # manage development settings
        self.production = self.config.get('general', 'production')
        # init loc
        self.lock = threading.Lock()
        # init Slack interface
        self.slack = Slack(self)
        # send initial message
        if self.slack.is_connected():
            self.slack.send_message("%s is booting up!" % self.bot_name)
        # the telescope
        self.telescope = Telescope(self.config, self.slack, self.lock)
        # init IxchelCommand
        self.ixchel_commands = IxchelCommand(self) # this is another circular dep I need to remove

    async def parse_message(self, **payload):
        message = payload['data']
        # if 'username' in message:
        #     self.logger.debug(message['username'])
        # if 'user' in message:
        #     self.logger.debug(message['user'])

        # ignore any messages sent from this bot
        if 'username' in message and message['username'] == self.bot_name:
            return
        # only process commands from the self.channel
        if 'channel' in message:
            # message posted in ixchel channel?
            if message['channel'] == self.channel_id:
                # self.slack.send_typing()
                self.process(message)
            else:  # message posted directly to bot
                self.logger.warning('Received direct message.')
                self.slack.send_message('Please use the channel #%s for communications with %s.' % (
                    self.channel, self.bot_name), None, message['channel'], self.bot_name)

    def process(self, message):
        if not 'text' in message:
            self.logger.error('Invalid message received.')
            return False
        text = message['text'].strip()
        if re.search(r'^\\\w+', text):
            self.ixchel_commands.parse(message)
        else:
            self.logger.warning('Received non-command text (%s).' % text)


async def loop():  # main loop
    while True:
        try:
            logger.debug('Checking connections (Slack, telescope, etc.)...')
            if ixchel.telescope.use_ssh:
                ixchel.telescope.ssh.is_connected()
            ixchel.slack.is_connected()
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            break


def cleanup(signum, frame):  # perform cleanup tasks
    tasks.cancel()


logger.info('Starting ixchel...')

# read configuration file
logger.info('Reading configuration from file (%s)...' % cfg_file_path)
if not os.path.exists(cfg_file_path):
    raise Exception('Configuration file (%s) is missing.' % cfg_file_path)
config = Config(cfg_file_path)

# Mayan goddess of the moon, medicine, and birth (mid-wifery). Stronger half of Itzamna!
ixchel = Ixchel(config)

# call back for incoming messages
ixchel.slack.rtm.on(event="message", callback=ixchel.parse_message)

# run slack and main loop concurrently
tasks = asyncio.gather(ixchel.slack.rtm.start(), loop())

# handle signals
signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)
loop = asyncio.get_event_loop()
try:
    loop.run_until_complete(tasks)
except asyncio.CancelledError as e:
    logger.error('Exception ( % s).' % e)
finally:
    logger.info("%s has stopped." % ixchel.bot_name)
    loop.close()
