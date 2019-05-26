import os
import logging
import ConfigParser
import time
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
    def __init__(self):
        self.logger = logging.getLogger('ixchel.Ixchel')


def main():
    logger.info('Starting ixchel...')

    # read configuration file
    logger.info('Reading configuration from file (%s)...' % cfg_file_path)
    if not os.path.exists(cfg_file_path):
        raise Exception('Configuration file (%s) is missing.' % cfg_file_path)
    config = ConfigParser.RawConfigParser()
    config.read(cfg_file_path)

    # Mayan goddess of the moon, medicine, and birth (mid-wifery). Stronger half of Itzamna!
    ixchel = Ixchel()

    # init Slack client
    slack = Slack(config.get('slack', 'token'), config.get(
        'slack', 'username'), config.get('slack', 'channel'))
    # connect to Slack channel
    slack.connect()
    slack.join_channel(config.get('slack', 'channel'))
    slack.send_message('This is a test!')
    slack.send_file('photo.jpg')

    # data loop
    while True:
        messages = slack.read_messages()
        logger.debug(messages)
        time.sleep(1)


if __name__ == "__main__":
    main()
