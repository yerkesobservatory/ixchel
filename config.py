"""

The Config module manages access to the configuration parameters (stored in a file).

"""

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

    def set(self, section, option, value):
        if self.config.has_option(section, option):
            self.config.set(section, option, str(value))
        else:
            self.logger.warning(
                'Configuration option (%s/%s) not found.' % (
                    section, option))          

    def exists(self, section, option):
        return self.config.has_option(section, option)

    def items(self, section):
        return self.config.items(section)
