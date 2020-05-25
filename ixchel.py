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
from ixchel_command import IxchelCommand
from slack_client import Slack
from config import Config
from telescope import Telescope

# logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(name)s - %(funcName)s - %(message)s',
    handlers=[
        logging.FileHandler("ixchel.log"),
        logging.StreamHandler()
    ])
logger = logging.getLogger('ixchel')

# config
cfg_file_path = 'ixchel.cfg'


class Ixchel:

    def __init__(self, config):
        self.logger = logging.getLogger('Ixchel')
        # init config
        self.config = config
        # init Slack interface
        self.slack = Slack(self)
        # the telescope
        self.telescope = Telescope(self)
        # init IxchelCommand
        self.ixchel_commands = IxchelCommand(self)
        # update settings
        self.username = self.config.get('slack', 'username')
        self.channel = self.config.get('slack', 'channel')
        self.channel_id = self.slack.get_channel_id(self.channel)

    async def parse_message(self, **payload):
        message = payload['data']
        self.logger.debug(message)
        self.logger.debug(message['channel'])
        if 'username' in message:
            self.logger.debug(message['username'])
        if 'user' in message:
            self.logger.debug(message['user'])

        # ignore any messages sent from this bot
        if 'username' in message and message['username'] == self.username:
            return
        # only process commands from the self.channel
        if 'channel' in message:
            # message posted in ixchel channel?
            if message['channel'] == self.channel_id:
                # self.slack.send_typing()
                self.process(message)
            else:  # message posted directly to bot
                self.logger.debug('Received direct message.')
                self.slack.send_message('Please use the channel #%s for communications with %s.' % (
                    self.channel, self.username), None, message['channel'], self.username)

    def process(self, message):
        if not 'text' in message:
            self.logger.error('Invalid message received.')
            return False
        text = message['text'].strip()
        if re.search(r'^\\\w+', text):
            self.ixchel_commands.parse(message)
        else:
            self.logger.debug('Received non-command text (%s).' % text)


async def loop():  # main loop
    while True:
        try:
            logger.debug('Checking connection to the telescope...')
            ixchel.telescope.ssh.is_connected()
            await asyncio.sleep(30)
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
    logger.info("%s has stopped." % ixchel.username)
    loop.close()
