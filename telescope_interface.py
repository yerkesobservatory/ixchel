import logging
import re

telescope_interfaces = {
    'track': {
        'command': 'tx track {on_off}',
        'inputs': {
            'on_off': {
                'value': None
            }
        },
        'outputs': {
            'ha': {
                'regex': r'(?<=ha=).*?(?= )',
                'value': None,
                'type': float
            },
            'dec': {
                'regex': r'(?<=dec=).*?$',
                'value': None,
                'type': float
            },
        }
    },
    'point': {
        'command': 'tx point ra={ra} dec={dec}',
        'inputs': {
            'ra': {
                'value': None
            },
            'dec': {
                'value': None
            }
        },
        'outputs': {
            'move': {
                'regex': r'(?<=move=).*?(?= )',
                'value': None,
                'type': float
            },
            'dist': {
                'regex': r'(?<=dist=).*?$',
                'value': None,
                'type': float
            },
        }
    },
    'get_image': {
        'command': 'mkdir -p {path}; image {dark} time={exposure} bin={bin} outfile={path}{fname}',
        'inputs': {
            'exposure': {
                'value': None
            },
            'bin': {
                'value': None
            },
            'path': {
                'value': None
            },
            'fname': {
                'value': None
            },
            'dark': {
                'value': None,
                'default': ''
            }
        },
        'outputs': {
            'error': {
                'regex': r'^.*$',
                'value': None,
                'type': str
            },
        }
    },
    'get_ccd': {
        'command': 'tx ccd_status',
        'inputs': {},
        'outputs': {
            'nrow': {
                'regex': r'(?<=nrow=).*?(?= )',
                'value': None,
                'type': int
            },
            'ncol': {
                'regex': r'(?<=ncol=).*?(?= )',
                'value': None,
                'type': int
            },
            'tchip': {
                'regex': r'(?<=tchip=).*?(?= )',
                'value': None,
                'type': float
            },
            'setpoint': {
                'regex': r'(?<=setpoint=).*?(?= )',
                'value': None,
                'type': float
            },
            'name': {
                'regex': r'(?<=name=).*?(?= )',
                'value': None,
                'type': str
            },
        }
    },
    'get_skycam': {
        'command': 'rm -f {skycam_remote_file_path}; spacam; mv spacam.jpg {skycam_remote_file_path};  [ -e "{skycam_remote_file_path}" ] && echo 1 || echo 0',
        'inputs': {
            'skycam_remote_file_path': {
                'value': None
            },
            'skycam_local_file_path': {
                'value': None
            }
        },
        'outputs': {
            'success': {
                'regex': r'^[01]$',
                'value': None,
                'type': int
            },
        }
    },
    'convert_fits_to_jpg': {
        'command': 'rm -f {jpg_file}; rm -f {tiff_file}; stiffy {fits_file} {tiff_file}; convert -resize 50% -normalize -quality 75 {tiff_file} {jpg_file};  [ -e "{jpg_file}" ] && echo 1 || echo 0',
        'inputs': {
            'fits_file': {
                'value': None
            },
            'tiff_file': {
                'value': None
            },
            'jpg_file': {
                'value': None
            }
        },
        'outputs': {
            'success': {
                'regex': r'^[01]$',
                'value': None,
                'type': int
            },
        }
    },
    'get_sun': {
        'command': 'sun',
        'inputs': {},
        'outputs': {
            'alt': {
                'regex': r'(?<=alt=).*?$',
                'value': None,
                'type': float
            }
        }
    },
    'get_moon': {
        'command': 'moon',
        'inputs': {},
        'outputs': {
            'alt': {
                'regex': r'(?<=alt=).*?(?= )',
                'value': None,
                'type': float
            },
            'phase': {
                'regex': r'(?<=phase=).*?(?= )',
                'value': None,
                'type': float
            }
        }
    },
    'get_precipitation': {
        'command': 'tx taux',
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
    'get_filter': {
        'command': 'tx filter',
        'inputs': {},
        'outputs': {
            'num': {
                'regex': r'(?<=num=).*?(?= )',
                'value': None,
                'type': int
            },
            'name': {
                'regex': r'(?<=name=).*?$',
                'value': None,
                'type': str
            }
        }
    },
    'set_filter': {
        'command': 'tx filter num={num}',
        'inputs': {
            'num': {
                'value': None
            },
        },
        'outputs': {
            'num': {
                'regex': r'(?<=num=).*?(?= )',
                'value': None,
                'type': int
            },
            'name': {
                'regex': r'(?<=name=).*?$',
                'value': None,
                'type': str
            }
        }
    },
    'get_focus': {
        'command': 'tx focus',
        'inputs': {},
        'outputs': {
            'pos': {
                'regex': r'(?<=pos=).*?$',
                'value': None,
                'type': int
            }
        }
    },
    'set_focus': {
        'command': 'tx focus pos={pos}',
        'inputs': {
            'pos': {
                'value': None
            }
        },
        'outputs': {
            'pos': {
                'regex': r'(?<=pos=).*?$',
                'value': None,
                'type': int
            }
        }
    },
    'get_lock': {
        'command': 'tx lock',
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
    'unlock': {
        'command': 'tx lock clear',
        'inputs': {
        },
        'outputs': {
            'success': {
                'regex': r'^done lock$',
                'value': None,
                'optional': False,
                'type': str
            }
        }
    },
    'clear_lock': {
        'command': 'tx lock clear',
        'inputs': {
        },
        'outputs': {
            'success': {
                'regex': r'^done lock$',
                'value': None,
                'optional': False,
                'type': str
            }
        }
    },
    'set_lock': {
        'command': 'tx lock user={user}',
        'inputs': {
            'user': {
                'value': None
            }
        },
        'outputs': {
            'user': {
                'regex': r'(?<=user=).*?(?= )',
                'value': None,
                'optional': False,
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
        'command': 'tx where',
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
        # reset command inputs and outputs
        self.set_defaults()

    # assign the specific interface by name

    def assign(self, name):
        for key, value in telescope_interfaces.items():
            if key == name:
                return value
        self.logger.error('Command (%s) not found.' % name)
        raise ValueError('Command (%s) not found.' % name)

    def set_defaults(self):
        for key in self.get_output_keys():
            self.set_output_value(key, self.get_output_default(key))
        for key in self.get_input_keys():
            self.set_input_value(key, self.get_input_default(key))

    # get command text
    def get_command(self):
        return self.command['command']

    # get command text
    def is_background(self):
        try:
            return self.command['is_background']
        except Exception as e:
            self.logger.info(
                'Command is_background not found. Assumed False.')
            return False

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
                if self.command['outputs'][name]['value'] == None:
                    return self.command['outputs'][name]['value']
                else:
                    return self.command['outputs'][name]['type'](self.command['outputs'][name]['value'])
            except Exception as e:
                self.logger.error('Command output conversion (%s) failed.' %
                                  self.command['outputs'][name]['type'])
        else:
            self.logger.error('Command output (%s) value not found.' % name)
            return None

    # get regex that defines this output value
    def get_output_regex(self, name):
        try:
            return self.command['outputs'][name]['regex']
        except Exception as e:
            self.logger.error('Command output (%s) regex not found.' % name)
            return None

    # get default for this output value
    def get_output_default(self, name):
        try:
            return self.command['outputs'][name]['default']
        except Exception as e:
            self.logger.warning(
                'Command output (%s) default not found. Assumed None.' % name)
            return None

    # is this output value marked as optional?
    def is_output_optional(self, name):
        try:
            return self.command['outputs'][name].get('optional', False)
        except Exception as e:
            self.logger.error(
                'Command output (%s) is_optional not found.' % name)
            return False

    # set output value by name
    def set_output_value(self, name, value):
        try:
            self.command['outputs'][name]['value'] = value
        except Exception as e:
            self.logger.error('Output (%s) not found.' % name)
            raise ValueError('Output (%s) not found.' % name)

    # get input value by name
    def get_input_value(self, name):
        try:
            return self.command['inputs'][name]['value']
        except Exception as e:
            self.logger.error('Command input (%s) not found.' % name)
            return None

    # get default for this output value
    def get_input_default(self, name):
        try:
            return self.command['inputs'][name]['default']
        except Exception as e:
            self.logger.warning(
                'Command input (%s) default not found. Assumed None.' % name)
            return None

    # set input value by name
    def set_input_value(self, name, value):
        try:
            self.command['inputs'][name]['value'] = value
        except Exception as e:
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
                    self.logger.error(
                        '%s value is missing or invalid (%s).' % (key, result.strip()))
                    raise ValueError(
                        '%s value is missing or invalid' % (key, result.strip()))

    # parse result and assign output values
    def assign_inputs(self):
        inputs = dict()
        for key in self.get_input_keys():
            inputs[key] = self.get_input_value(key)
        # self.logger.debug(inputs)
        return self.get_command().format(**inputs)
