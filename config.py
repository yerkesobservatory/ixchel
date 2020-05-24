import logging
import configparser


class Config:

    def __init__(self, cfg_file_path):
        self.logger = logging.getLogger('ixchel.Config')
        self.config = configparser.SafeConfigParser()
        self.config.read(cfg_file_path)

    def get(self, section, option, default=None):
        if self.config.has_option(section, option):
            return self.config.get(section, option)
        else:
            self.logger.warning(
                'Configuration option (%s/%s) not found. Returning default value (%s).' % (
                    section, option, str(default)))
            return default
