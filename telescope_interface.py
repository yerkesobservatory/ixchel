import logging
import re

telescope_interfaces = {
    'get_precipitation': {
        'command': r'tx taux',
        'inputs': {},
        'outputs': {
            'clouds': {
                'regex': r'(?<=cloud=).*?(?= )',
                'value': None,
                'type': float
            },
            'rain': {
                'regex': r'(?<=rain=).*?(?= )',
                'value': None,
                'type': float
            },
            'dew': {
                'regex': r'(?<=dew=).*?$',
                'value': None,
                'type': float
            }
        }
    },
    'get_focus': {
        'command': r'tx focus',
        'inputs': {},
        'outputs': {
            'pos': {
                'regex': r'(?<=pos=).*?$',
                'value': None,
                'type': int
            }
        }
    },
    'get_lock': {
        'command': r'tx lock',
        'inputs': {},
        'outputs': {
            'user': {
                'regex': r'(?<=user=).*?(?= )',
                'value': None,
                'optional': True,
                'type': str
            },
            'email': {
                'regex': r'(?<=email=).*?(?= )',
                'value': None,
                'optional': True,
                'type': str
            },
            'phone': {
                'regex': r'(?<=phone=).*?(?= )',
                'value': None,
                'optional': True,
                'type': str
            },
            'comment': {
                'regex': r'(?<=comment=).*?(?= )',
                'value': None,
                'optional': True,
                'type': str
            },
            'timestamp': {
                'regex': r'(?<=timestamp=).*?$',
                'value': None,
                'optional': True,
                'type': str
            }
        }
    },
    'get_where': {
        'command': r'tx where',
        'inputs': {},
        'outputs': {
            'ra': {
                'regex': r'(?<=ra=).*?(?= )',
                'value': None,
                'type': str
            },
            'dec': {
                'regex': r'(?<=dec=).*?(?= )',
                'value': None,
                'type': str
            },
            'alt': {
                'regex': r'(?<=alt=).*?(?= )',
                'value': None,
                'type': float
            },
            'az': {
                'regex': r'(?<=az=).*?(?= )',
                'value': None,
                'type': float
            },
            'slewing': {
                'regex': r'(?<=slewing=).*?$',
                'value': None,
                'type': int
            }
        }
    },
}


class TelescopeInterface:

    def __init__(self, name):
        self.logger = logging.getLogger('ixchel.TelescopeInterface')
        self.command = self.assign(name)

    # assign the specific interface by name
    def assign(self, name):
        for key, value in telescope_interfaces.items():
            if key == name:
                return value
        self.logger.error('Command (%s) not found.' % name)
        raise ValueError('Command (%s) not found.' % name)

    # get command text
    def get_command(self):
        return self.command['command']

    # get names (keys) of all outputs
    def get_output_keys(self):
        return self.command['outputs'].keys()

    # get names (keys) of all inputs
    def get_input_keys(self):
        return self.command['inputs'].keys()

    # get output value by name
    def get_output_value(self, name):
        if name in self.command['outputs']:
            try:
                return self.command['outputs'][name]['type'](self.command['outputs'][name]['value'])
            except Exception as e:
                self.logger.error('Command output conversion (%s) failed.' %
                                  self.command['outputs'][name]['type'])
        else:
            self.logger.error('Command output (%s) value not found.' % name)
            return None

    # get regex that defines this output value
    def get_output_regex(self, name):
        if name in self.command['outputs']:
            return self.command['outputs'][name]['regex']
        else:
            self.logger.error('Command output (%s) regex not found.' % name)
            return None

    # is this output value marked as optional?
    def is_output_optional(self, name):
        if name in self.command['outputs']:
            return self.command['outputs'][name].get('optional', False)
        else:
            self.logger.error(
                'Command output (%s) is_optional not found.' % name)
            return False

    # set output value by name
    def set_output_value(self, name, value):
        if name in self.command['outputs']:
            self.command['outputs'][name]['value'] = value
        else:
            self.logger.error('Output (%s) not found.' % name)
            raise ValueError('Output (%s) not found.' % name)

    # get input value by name
    def get_input(self, name):
        if name in self.command['inputs']:
            return self.command['inputs'][name]['value']
        else:
            self.logger.error('Command input (%s) not found.' % name)
            return None

    # set input value by name
    def set_input(self, name, value):
        if name in self.command['inputs']:
            self.command['inputs'][name]['value'] = value
        else:
            self.logger.error('Input (%s) not found.' % name)
            raise ValueError('Input (%s) not found.' % name)

    # parse result and assign output values
    def assign_outputs(self, result):
        for key in self.get_output_keys():
            match = re.search(self.get_output_regex(key), result)
            if match:
                self.set_output_value(key, match.group(0))
            else:
                if self.is_output_optional(key):
                    self.logger.debug(
                        '%s value is missing (but optional).' % key)
                else:
                    self.logger.error('%s value is missing or invalid (%s).' %
                                      (key, self.get_output_value(key)))
                    raise ValueError('%s value is missing or invalid (%s).' %
                                     (key, self.get_output_value(key)))
