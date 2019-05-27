import os
import logging
import ConfigParser
import time
import datetime
from slack import Slack

# logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
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

    def __init__(self, config):
        self.logger = logging.getLogger('ixchel.Ixchel')
        self.config = config
        self.slack = Slack(self.config)

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
                self.logger.debug(messages)
                time.sleep(self.loop_delay_s)
            time.sleep(self.slack_reconnect_delay_s)
            self.slack.connect()


def main():
    logger.info('Starting ixchel...')

    # read configuration file
    logger.info('Reading configuration from file (%s)...' % cfg_file_path)
    if not os.path.exists(cfg_file_path):
        raise Exception('Configuration file (%s) is missing.' % cfg_file_path)
    config = ConfigParser.SafeConfigParser()
    config.read(cfg_file_path)

    # Mayan goddess of the moon, medicine, and birth (mid-wifery). Stronger half of Itzamna!
    ixchel = Ixchel(config)

    ixchel.loop()


if __name__ == "__main__":
    main()
