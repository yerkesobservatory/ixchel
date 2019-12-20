import logging
import paramiko
import subprocess
import re
from telescope_interface import TelescopeInterface
from astropy.coordinates import EarthLocation
import astropy.units as u


class SSH:
    def __init__(self, ixchel):
        self.logger = logging.getLogger('SSH')
        self.ixchel = ixchel
        self.config = ixchel.config
        self.server = self.config.get('ssh', 'server')
        self.username = self.config.get('ssh', 'username')
        self.key_path = self.config.get('ssh', 'key_path')
        # init Paramiko
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    def connect(self):
        try:
            self.ixchel.slack.send_message(
                'Connecting to the telescope. Please wait...')
            self.ssh.connect(self.server, username=self.username,
                             key_filename=self.key_path)
            self.command('echo its alive', False)  # test the connection
            self.ixchel.slack.send_message('Connected to the telescope!')
            self.ixchel.slack.send_typing()
            return True
        except Exception as e:
            self.ixchel.slack.send_message(
                'Failed to connect to the telescope! Retrying...')
            self.logger.error(
                'SSH initialization failed. Exception (%s).' % e)
        return False

    def command(self, command, is_background):
        if is_background:
            return self.command_background(command)
        else:
            return self.command_foreground(command)

    def command_background(self, command):
        # test connection
        try:
            self.ssh.exec_command('echo its alive')  # test the connection
        except Exception as e:
            self.logger.warning(
                'SSH command failed. Exception (%s). Reconnecting...' % e)
            self.connect()
        # run command
        result = {
            'response': None,
            'stdout': [],
            'stderr': [],
            'pid': None
        }
        try:
            stdin, stdout, stderr = self.ssh.exec_command('%s &' % command)
            result['stdout'] = stdout.readlines()
            result['stderr'] = stderr.readlines()
            if len(result['stdout']) > 0:
                result['response'] = result['stdout'][0]
                # get the pid
                match = re.search(r'([0-9]+)$', result['response'])
                if match:
                    result['pid'] = int(match.group(1))
                else:
                    self.logger.error(
                        'Command (%s) did not return a pid.' % command)
            elif len(result['stderr']) > 0:
                result['response'] = result['stderr'][0]
                self.logger.error('Command (%s) returned error (%s).' % (
                    command, result['response']))
            else:
                result['response'] = ''
                self.logger.warning(
                    'Command (%s) returned no response.' % (command))
        except Exception as e:
            self.logger.error(
                'SSH command failed. Exception (%s).' % e)
        return result

    def command_foreground(self, command):
        # test connection
        try:
            self.ssh.exec_command('echo its alive')  # test the connection
        except Exception as e:
            self.logger.warning(
                'SSH command failed. Exception (%s). Reconnecting...' % e)
            self.connect()
        # run command
        result = {
            'response': None,
            'stdout': [],
            'stderr': [],
            'pid': None
        }
        try:
            stdin, stdout, stderr = self.ssh.exec_command(command)
            result['stdout'] = stdout.readlines()
            result['stderr'] = stderr.readlines()
            if len(result['stdout']) > 0:
                result['response'] = result['stdout'][0]
            elif len(result['stderr']) > 0:
                result['response'] = result['stderr'][0]
                self.logger.error('Command (%s) returned error (%s).' % (
                    command, result['response']))
            else:
                result['response'] = ''
                self.logger.warning(
                    'Command (%s) returned no response.' % (command))
        except Exception as e:
            self.logger.error(
                'SSH command failed. Exception (%s).' % e)
        return result

    def get_file(self, remote_path, local_path):
        # test connection
        try:
            self.ssh.exec_command('echo its alive')  # test the connection
        except Exception as e:
            self.logger.warning(
                'SSH command failed. Exception (%s). Reconnecting...' % e)
            self.connect()
        try:
            sftp = self.ssh.open_sftp()
            sftp.get(remote_path, local_path)
            sftp.close()
        except Exception as e:
            self.logger.error('SFTP failed. Exception (%s).' % e)
            return False
        return True


class Telescope:

    ssh = None

    def __init__(self, ixchel):
        self.logger = logging.getLogger('Telescope')
        self.ixchel = ixchel
        self.config = ixchel.config
        self.use_ssh = self.config.get('telescope', 'use_ssh', False)
        self.latitude = self.config.get('telescope', 'latitude')
        self.longitude = self.config.get('telescope', 'longitude')
        self.elevation = self.config.get('telescope', 'elevation')
        self.earthLocation = EarthLocation(lat=float(
            self.latitude)*u.deg, lon=float(self.longitude)*u.deg, height=float(self.elevation)*u.m)
        if self.use_ssh:
            self.ssh = SSH(ixchel)
            self.ssh.connect()

    def init_ssh(self):
        server = self.config.get('ssh', 'server')
        username = self.config.get('ssh', 'username')
        key_path = self.config.get('ssh', 'key_path')

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(server, username=username, key_filename=key_path)
        try:
            ssh.exec_command('echo its alive')  # test the connection
            return ssh
        except Exception as e:
            self.logger.error(
                'SSH initialization failed. Exception (%s).' % e)
        return None

    def command(self, command, is_background, use_communicate=True, timeout=0):
        result = {
            'stdout': [],
            'stderr': []
        }
        # add a timeout to this command
        if timeout > 0:
            command = 'timeout %f ' % timeout + command
        # use ssh
        if self.use_ssh:
            if self.ssh == None:  # not connected?
                self.logger.warn(
                    'SSH is not connected. Reconnecting...')
                self.ssh.connect()
            else:  # need to reconnect?
                try:
                    self.ssh.command('echo its alive', is_background)
                except Exception as e:
                    self.logger.warn(
                        'SSH is not connected. Reconnecting...')
                    self.ssh.connect()
            try:
                return self.ssh.command(command, is_background)
            except Exception as e:
                self.logger.error(
                    'Command (%s) via SSH failed. Exception (%s).')
                return result
        else:  # use local
            command_array = command.split()
            try:
                sp = subprocess.Popen(
                    command_array, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
                sp.wait()
                if use_communicate:
                    output, error = sp.communicate(b'\n\n')
                    result['stdout'] = output.splitlines()
                    result['stderr'] = error.splitlines()
            except Exception as e:
                self.logger.error(
                    'Command (%s) failed. Exception (%s).')
            return result

    def get_file(self, remote_path, local_path):
        return self.ssh.get_file(remote_path, local_path)

    # Generic getter is the standard for all SEO get commands
    # To support future telescope interfaces,
    # these will be called by the *explicit* getter

    def getter(self, interface):
        results = self.command(interface.get_command(),
                               interface.is_background())
        result = results['response']
        # parse the result and assign values to output valuse
        interface.assign_outputs(result)

    # Generic setter is the standard for all SEO get commands
    # To support future telescope interfaces,
    # these will be called by the *explicit* setter
    def setter(self, interface):
        command = interface.assign_inputs()
        results = self.command(command, interface.is_background())
        result = results['response']
        # parse the result and assign values to output valuse
        interface.assign_outputs(result)

    def get_skycam(self, interface):
        self.setter(interface)

    def get_image(self, interface):
        self.setter(interface)

    def convert_fits_to_jpg(self, interface):
        self.setter(interface)

    def get_precipitation(self, interface):
        self.getter(interface)

    def get_sun(self, interface):
        self.getter(interface)

    def get_ccd(self, interface):
        self.getter(interface)

    def get_moon(self, interface):
        self.getter(interface)

    def get_filter(self, interface):
        self.getter(interface)

    def set_filter(self, interface):
        self.setter(interface)

    def get_focus(self, interface):
        self.getter(interface)

    def set_focus(self, interface):
        self.setter(interface)

    def get_lock(self, interface):
        self.getter(interface)

    def set_lock(self, interface):
        self.setter(interface)

    def unlock(self, interface):
        self.setter(interface)

    def clear_lock(self, interface):
        self.setter(interface)

    def get_where(self, interface):
        self.getter(interface)

    def point(self, interface):
        self.setter(interface)

    def track(self, interface):
        self.setter(interface)
