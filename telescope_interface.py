import logging

telescope_interfaces = {
    'get_precipitation': {
        'command': r'tx taux',
        'inputs': {},
        'outputs': {
            'clouds': {
                'regex': r'(?<=cloud=).*?(?= )',
                'value': None
            },
            'rain': {
                'regex': r'(?<=rain=).*?(?= )',
                'value': None
            },
            'dew': {
                'regex': r'(?<=dew=).*?$',
                'value': None
            }
        }
    }
}


class TelescopeInterface:

    def __init__(self, name):
        self.logger = logging.getLogger('ixchel.TelescopeInterface')
        self.command = self.assign(name)

    def assign(self, name):
        for key, value in telescope_interfaces.items():
            if key == name:
                return value
        self.logger.error('Command (%s) not found.' % name)
        raise ValueError('Command (%s) not found.' % name)

    def get_command(self):
        return self.command['command']

    def get_outputs(self):
        return self.command['outputs'].keys()

    def get_inputs(self):
        return self.command['inputs'].keys()

    def get_output_value(self, name):
        if name in self.command['outputs']:
            return self.command['outputs'][name]['value']
        else:
            self.logger.error('Command output (%s) value not found.' % name)
            return None

    def get_output_regex(self, name):
        if name in self.command['outputs']:
            return self.command['outputs'][name]['regex']
        else:
            self.logger.error('Command output (%s) regex not found.' % name)
            return None

    def is_output_optional(self, name):
        if name in self.command['outputs']:
            return self.command['outputs'][name].get('optional', False)
        else:
            self.logger.error('Command output (%s) optional not found.' % name)
            return False

    def set_output_value(self, name, value):
        if name in self.command['outputs']:
            self.command['outputs'][name]['value'] = value
        else:
            self.logger.error('Output (%s) not found.' % name)
            raise ValueError('Output (%s) not found.' % name)

    def get_input(self, name):
        if name in self.command['inputs']:
            return self.command['inputs'][name]['value']
        else:
            self.logger.error('Command input (%s) not found.' % name)
            return None

    def set_input(self, name, value):
        if name in self.command['inputs']:
            self.command['inputs'][name]['value'] = value
        else:
            self.logger.error('Input (%s) not found.' % name)
            raise ValueError('Input (%s) not found.' % name)
