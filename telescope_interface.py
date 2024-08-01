"""

The TelescopeInterface module specifies the command line syntax associated with each telescope command,
including the command, inputs, and expected outputs. These commands are executed by the Telescope module.

"""

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
    'get_track': {
        'command': 'tx track',
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
    'get_image_hdr': {
        'command': 'mkdir -p {path}; image {dark} time={exposure} bin={bin} outfile={path}{fname} lowfile={path}{low_fname}',
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
            'low_fname': {
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
            }
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
            }
        }
    },
    'get_dome': {
        'command': 'tx dome',
        'inputs': {},
        'outputs': {
            'az': {
                'regex': r'(?<=az=).*?$',
                'value': None,
                'type': str
            }
        }
    },
    'center_dome': {
        'command': 'tx dome center',
        'inputs': {},
        'outputs': {
            'az': {
                'regex': r'(?<=az=).*?$',
                'value': None,
                'type': str
            }
        }
    },
    'home_domer': {
        'command': 'tx home domer',
        'inputs': {},
        'outputs': {
            'az_hit': {
                'regex': r'(?<=az_hit=).*?(?= )',
                'value': None,
                'type': float
            },
            'rem': {
                'regex': r'(?<=rem=).*?$',
                'value': None,
                'type': str
            }
        }
    },
    'home_domel': {
        'command': 'tx home domel',
        'inputs': {},
        'outputs': {
            'az_hit': {
                'regex': r'(?<=az_hit=).*?(?= )',
                'value': None,
                'type': float
            },
            'rem': {
                'regex': r'(?<=rem=).*?$',
                'value': None,
                'type': str
            }
        }
    },
    'get_lights': {
        'command': 'tx lamps',
        'inputs': {},
        'outputs': {
            '1_on_off': {
                'regex': r'(?<=one=).*?(?= )',
                'value': None,
                'type': str
            },
            '2_on_off': {
                'regex': r'(?<=two=).*?(?= )',
                'value': None,
                'type': str
            },
            '3_on_off': {
                'regex': r'(?<=three=).*?(?= )',
                'value': None,
                'type': str
            },
            '4_on_off': {
                'regex': r'(?<=four=).*?(?= )',
                'value': None,
                'type': str
            },
            '5_on_off': {
                'regex': r'(?<=five=).*?(?= )',
                'value': None,
                'type': str
            },
            '6_on_off': {
                'regex': r'(?<=six=).*?(?= )',
                'value': None,
                'type': str
            },
            '7_on_off': {
                'regex': r'(?<=seven=).*?(?= )',
                'value': None,
                'type': str
            },
            '8_on_off': {
                'regex': r'(?<=eight=).*?$',
                'value': None,
                'type': str
            }
        }
    },
    'set_lights': {
        'command': 'tx lamps {light_number}={on_off}',
        'inputs': {
            'light_number': {
                'value': None
            },
            'on_off': {
                'value': None
            }
        },
        'outputs': {
            'on_off': {
                'regex': r'(?<=one=).*?(?= )',
                'value': None,
                'type': str
            }
        }
    },
    'get_mirror': {
        'command': 'tx mirror',
        'inputs': {},
        'outputs': {
            'open_close': {
                'regex': r'(?<=state=).*?$',
                'value': None,
                'type': str
            }
        }
    },
    'set_mirror': {
        'command': 'tx mirror {open_close}',
        'inputs': {
            'open_close': {
                'value': None
            }
        },
        'outputs': {
            'open_close': {
                'regex': r'(?<=state=).*?$',
                'value': None,
                'type': str
            }
        }
    },
    'get_slit': {
        'command': 'tx slit',
        'inputs': {},
        'outputs': {
            'open_close': {
                'regex': r'(?<=slit=).*?$',
                'value': None,
                'type': str
            }
        }
    },
    'set_slit': {
        'command': 'tx slit {open_close}',
        'inputs': {
            'open_close': {
                'value': None
            }
        },
        'outputs': {
            'open_close': {
                'regex': r'(?<=slit=).*?$',
                'value': None,
                'type': str
            }
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
            'drive': {
                'regex': r'(?<=drive=).*?(?= )',
                'value': None,
                'type': float
            }
        }
    },
    'set_ccd': {
        'command': 'ccd {cool_warm} nowait setpoint={setpoint} && echo 1 || echo 0',
        'inputs': {
            'cool_warm': {
                'value': None
            },
            'setpoint': {
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
    'get_domecam': {
        'command': 'curl --progress-bar -o {domecam_remote_file_path} {domecam_image_url}',
        'inputs': {
            'domecam_image_url': {
                'value': None
            },
            'domecam_remote_file_path': {
                'value': None
            }
        },
        'outputs': {
            'success': {
                'regex': r'100\.0',
                'value': None,
                'type': str
            },
        }
    },
    'to_stars': {
        'command': 'bash -c "rsync -auvz --progress --files-from=<(find {image_dir} -mtime -3 -type f | sed -n \'s|^{image_dir}||p\') {image_dir} {stars_user}@{stars_url}:{stars_remote_dir}"',
        'is_background': False,
        'inputs': {
            'image_dir': {
                'value': None
            },
            'stars_remote_dir': {
                'value': None
            },
            'stars_key_path': {
                'value': None
            },
            'stars_user': {
                'value': None
            },
            'stars_url': {
                'value': None
            },
            'year': {
                'value': None
            },
            'date': {
                'value': None
            }
        },
        'outputs': {
            'error': {
                'regex': r'^.*$',
                'value': None,
                'type': str
            }
        }
    },
    'offset': {
        'command': 'tx offset dec={dDEC} ra={dRA}',
        'is_background': False,
        'inputs': {
            'dRA': {
                'value': None
            },
            'dDEC': {
                'value': None
            },
        },
        'outputs': {
            'success': {
                'regex': r'^done offset',
                'value': None,
                'optional': False,
                'type': str
            }
        }
    },
    'psfex': {
        'command': '{psfex_bin_path} {sextractor_cat_path} -c {psfex_cfg_path}',
        'is_background': False,
        'inputs': {
            'psfex_bin_path': {
                'value': None
            },
            'sextractor_cat_path': {
                'value': None
            },
            'psfex_cfg_path': {
                'value': None
            }
        },
        'outputs': {
            'success': {
                'regex': r'> All done',
                'value': None,
                'optional': False,
                'type': str
            }
        }
    },
    'sextractor': {
        'command': '{sextractor_bin_path} {path}{fname} -c {sextractor_sex_path} -CATALOG_NAME {sextractor_cat_path} -PARAMETERS_NAME {sextractor_param_path} -FILTER_NAME {sextractor_conv_path}',
        'is_background': False,
        'inputs': {
            'sextractor_bin_path': {
                'value': None
            },
            'path': {
                'value': None
            },
            'fname': {
                'value': None
            },
            'sextractor_sex_path': {
                'value': None
            },
            'sextractor_cat_path': {
                'value': None
            },
            'sextractor_param_path': {
                'value': None
            },
            'sextractor_conv_path': {
                'value': None
            }
        },
        'outputs': {
            'success': {
                'regex': r'> All done',
                'value': None,
                'optional': False,
                'type': str
            }
        }
    },
    'pinpoint': {
        'command': '{solve_field_path} --no-verify --overwrite --no-remove-lines --downsample {downsample} --scale-units arcsecperpix --no-plots --scale-low {scale_low} --scale-high {scale_high} --ra {ra_target} --dec {dec_target} --radius {radius} --cpulimit {cpulimit} {path}{fname}; rm -f {path}*.axy; rm -f {path}*.corr; rm -f {path}*.match; rm -f {path}*.new; rm -f {path}*.rdls; rm -f {path}*.solved; rm -f {path}*.wcs',
        'is_background': False,
        'inputs': {
            'solve_field_path': {
                'value': None
            },
            'downsample': {
                'value': None
            },
            'scale_low': {
                'value': None
            },
            'scale_high': {
                'value': None
            },
            'ra_target': {
                'value': None
            },
            'dec_target': {
                'value': None
            },
            'radius': {
                'value': None
            },
            'cpulimit': {
                'value': None
            },
            'fname': {
                'value': None
            },
            'path': {
                'value': None
            }
        },
        # Field center: (RA,Dec) = (132.077893, 26.584066) deg.
        'outputs': {
            'ra_image': {
                'regex': r'(?<=Field center: \(RA,Dec\) = \().*?(?=\,)',
                'value': None,
                'type': str
            },
            # I don't love this...
            'dec_image': {
                'regex': r'(?<=, ).*?(?=\) deg.)',
                'value': None,
                'type': str
            }
        }
    },
    'convert_fits_to_jpg_hdr': {
        'command': 'rm -f {jpg_file}; rm -f {tiff_file}; mv {fits_file_hdr} {fits_file}; stiffy {fits_file} {tiff_file}; convert -resize 50% -normalize -quality 75 {tiff_file} {jpg_file};  [ -e "{jpg_file}" ] && echo 1 || echo 0',
        'inputs': {
            'fits_file': {
                'value': None
            },
            'fits_file_hdr': {
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
                'regex': r'(?<=pos=)[0-9]+',
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
                'regex': r'^done lock',
                'value': None,
                'optional': False,
                'type': str
            }
        }
    },
    'open_observatory': {
        'command': 'openup_nolock nocloud; keepopen kill maxtime=36000 slit >& /dev/null',
        'inputs': {
        },
        'outputs': {
            'failure': {
                'regex': r'ERROR',
                'value': None,
                'optional': True,
                'type': str
            }
        }
    },
    'keepopen': {
        'command': 'keepopen kill maxtime={maxtime} dome >& /dev/null',
        'inputs': {
            'maxtime': {
                'value': None
            }
        },
        'outputs': {
        }
    },
    'close_observatory': {
        'command': 'closedown_nolock; tx slit close; tx lock clear',
        'inputs': {
        },
        'outputs': {
            'failure': {
                'regex': r'ERROR',
                'value': None,
                'optional': True,
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
                'regex': r'^done lock',
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
                'type': int,
                'optional': True
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

    # get is_background
    def is_background(self):
        try:
            return self.command['is_background']
        except Exception as e:
            self.logger.info(
                'A value of is_background not found. Assumed False.')
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
            # process all lines in output
            for line in result:
                match = re.search(self.get_output_regex(key), line)
                if match:
                    break
            if match:
                self.set_output_value(key, match.group(0))
            else:
                if self.is_output_optional(key):
                    self.logger.warning(
                        '%s value is missing (but optional).' % key)
                else:
                    # TODO: FIX THE PROBLEM WITH STRIP HERE?
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
