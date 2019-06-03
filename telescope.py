import logging
import paramiko


class Telescope:

    def __init__(self, config):
        self.logger = logging.getLogger('ixchel.Telescope')
        self.config = config

    def init_ssh(self):
        server = 
        username = 
        key_filename = 
        
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh.connect(ssh_hostname, username=ssh_username,
                    key_filename=ssh_private_key_path)
        try:
            stdin, stdout, stderr = ssh.exec_command('echo its alive')
        except Exception as e:
            logme(e.to_string())        

    def run_command(self, command):
        # if self.ssh == None:
        #     self.log.warn(
        #         'SSH is not connected. Please reconnect to the telescope server.')
        #     return None

        # # make sure the connection hasn't timed out due to sleep
        # # if it has, reconnect
        # try:
        #     self.ssh.exec_command('echo its alive')
        # except Exception as e:
        #     self.ssh = self.connect()

        # # try and execute command 5 times if it fails
        # numtries = 0
        # exit_code = 1
        # while numtries < 5 and exit_code != 0:
        #     try:
        #         self.log.info(f'Executing: {command}')
        #         # deal with weird keepopen behavior
        #         if re.search('keepopen*', command):
        #             try:
        #                 self.ssh.exec_command(command, timeout=10)
        #                 return None
        #             except Exception as e:
        #                 pass
        #         else:
        #             stdin, stdout, stderr = self.ssh.exec_command(command)
        #             numtries += 1
        #             result = stdout.readlines()

        #             # check exit code
        #             exit_code = stdout.channel.recv_exit_status()
        #             if exit_code != 0:
        #                 self.log.warn(f'Command returned {exit_code}. Retrying in 3 seconds...')
        #                 time.sleep(3)
        #                 continue

        #             if result:
        #                 # valid result received
        #                 if len(result) > 0:
        #                     result = ' '.join(result).strip()
        #                     self.log.info(f'Result: {result}')
        #                     return result

        #     except Exception as e:
        #         self.log.critical(f'run_command: {e}')
        #         self.log.critical(f'Failed while executing {command}')
        #         self.log.critical('Please manually close the dome by running'
        #                           ' `closedown` and `logout`.')

        #         raise UnknownErrorException

        # return None
