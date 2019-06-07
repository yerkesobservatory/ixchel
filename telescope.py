import logging
import paramiko
import subprocess


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
        try:
            stdin, stdout, stderr = self.ssh.exec_command(command)
            return (stdout.readlines(), stderr.readlines())
        except Exception as e:
            self.logger.error(
                'SSH command failed. Exception (%s).' % e.message)
        return (None, None, None)


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
                return None
        else:  # use local
            command_array = command.split()
            try:
                sp = subprocess.Popen(
                    command_array, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
                sp.wait()
                if communicate:
                    output, error = sp.communicate(b'\n\n')
                    return (output.splitlines(), error.splitlines())
                else:  # some processes, like keepopen, hang forever with .communicate()
                    return ([''], [''])
            except Exception as e:
                self.logger.error(
                    'Command (%s) via SSH failed. Exception (%s).')
                return None
