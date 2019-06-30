import logging
import paramiko
import subprocess
import re
from telescope_interface import TelescopeInterface


class SSH:
    def __init__(self, config):
        self.logger = logging.getLogger('ixchel.SSH')
        self.config = config
        self.server = self.config.get('ssh', 'server')
        self.username = self.config.get('ssh', 'username')
        self.key_path = self.config.get('ssh', 'key_path')
        # init Paramiko
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    def connect(self):
        try:
            self.ssh.connect(self.server, username=self.username,
                             key_filename=self.key_path)
            self.command('echo its alive')  # test the connection
            return True
        except Exception as e:
            self.logger.error(
                'SSH initialization failed. Exception (%s).' % e.message)
        return False

    def command(self, command):
        # test connection
        try:
            self.ssh.exec_command('echo its alive')  # test the connection
        except Exception as e:
            self.logger.warning(
                'SSH command failed. Exception (%s). Reconnecting...' % e.message)
            self.connect()
        # run command
        result = {
            'response': None,
            'stdout': [],
            'stderr': []
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
                result['response'] = 'Invalid response.'
                self.logger.error(
                    'Command (%s) returned invalid response.' % (command))
        except Exception as e:
            self.logger.error(
                'SSH command failed. Exception (%s).' % e.message)
        return result


class Telescope:

    ssh = None

    def __init__(self, config):
        self.logger = logging.getLogger('ixchel.Telescope')
        self.config = config
        self.use_ssh = self.config.get('telescope', 'use_ssh', False)
        if self.use_ssh:
            self.ssh = SSH(config)
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
                'SSH initialization failed. Exception (%s).' % e.message)
        return None

    def command(self, command, use_communicate=True, timeout=0):
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
                    self.ssh.command('echo its alive')
                except Exception as e:
                    self.logger.warn(
                        'SSH is not connected. Reconnecting...')
                    self.ssh.connect()
            try:
                return self.ssh.command(command)
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

    # Generic getter is the standard for all SEO get commands
    # To support future telescope interfaces,
    # these will be called by the *explicit* getter
    def getter(self, interface):
        results = self.command(interface.get_command())
        result = results['response']
        # parse the result and assign values to output valuse
        interface.assign_outputs(result)

    # Generic setter is the standard for all SEO get commands
    # To support future telescope interfaces,
    # these will be called by the *explicit* setter
    def setter(self, interface):
        command = interface.assign_inputs()
        results = self.command(command)
        result = results['response']
        # parse the result and assign values to output valuse
        interface.assign_outputs(result)

    def get_precipitation(self, interface):
        self.getter(interface)

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
