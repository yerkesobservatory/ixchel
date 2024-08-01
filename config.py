"""

The Config module manages access to the configuration parameters (stored in a file).

"""

import logging
import configparser


class Config:

    def __init__(self, cfg_file_path):
        self.logger = logging.getLogger('ixchel.Config')
        self.config = configparser.ConfigParser()
        self.config.read(cfg_file_path)
        # let's hang on to the base settings too
        # will be handy for reset_session and new \config command
        self.base_config = configparser.ConfigParser()
        self.base_config.read(cfg_file_path)

    def get(self, section, option, default=None):
        if self.config.has_option(section, option):
            return self.config.get(section, option)
        else:
            self.logger.warning(
                'Configuration option (%s/%s) not found. Returning default value (%s).' % (
                    section, option, str(default)))
            return default

    def getboolean(self, section, option, default=None):
        if self.config.has_option(section, option):
            return self.config.getboolean(section, option)
        else:
            self.logger.warning(
                'Configuration option (%s/%s) not found. Returning default value (%s).' % (
                    section, option, str(default)))
            return default

    def get_base(self, section, option, default=None):
        if self.base_config.has_option(section, option):
            return self.base_config.get(section, option)
        else:
            self.logger.warning(
                'Base configuration option (%s/%s) not found. Returning default value (%s).' % (
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
