"""
Telescope executes telescope commands via an SSH connection to the aster server (the SEO telescope host).

"""
import subprocess
import re
import logging
import threading
import paramiko
from astropy.coordinates import EarthLocation
import astropy.units as u
from slack_client import Slack
from config import Config


class SSH:
    """Manages connecting and executing commands over an SSH connection with
    Aster / the telescope
    """

    def __init__(self, config: Config, slack: Slack, lock: threading.Lock):
        self.config = config
        self.lock = lock
        self.slack = slack

        # defaults
        self.enabled = False
        self.logger = logging.getLogger("SSH")
        self.server = self.config.get("ssh", "server")
        self.username = self.config.get("ssh", "username")
        self.key_path = self.config.get("ssh", "key_path")

        # init paramiko
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    def connect(self):
        """Establish the SSH connection (configured at initialization)

        Returns:
            bool: connection successful?
        """
        try:
            self.slack.send_message("Connecting to the telescope. Please wait...")
            self.ssh.connect(
                self.server, username=self.username, key_filename=self.key_path
            )
            self.ssh.exec_command("echo its alive")  # test the connection
            self.slack.send_message("Connected to the telescope!")
            self.enabled = True # I would like to move this out of here, but it breaks Paramiko / puts the program in a loop
            return True
        except Exception as e:
            self.slack.send_message("Failed to connect to the telescope!")
            self.logger.error("SSH initialization failed. Exception (%s).", e)
        return False

    def command(self, command, is_background):
        """Execute a command over the SSH connection,
            either in the background or foreground

        Args:
            command (str): command string
            is_background (bool): run the given command in the background

        Returns:
            _type_: _description_ TODO: type this properly
        """
        if is_background:
            return self._command_background(command)

        return self._command_foreground(command)

    def _command_background(self, command):
        """Background command execution"""
        if not self.is_connected():
            self.logger.error(
                "Background command (%s) failed. SSH client is not connected.", command
            )
            return False
        # run command
        result = {"response": None, "stdout": [], "stderr": [], "pid": None}
        try:
            self.logger.info("Running background command: %s", command)
            stdin, stdout, stderr = self.ssh.exec_command(f"{command} &")
            stdout.channel.recv_exit_status()
            result["stdout"] = stdout.readlines()
            result["stderr"] = stderr.readlines()
            self.logger.debug(result["stdout"])
            self.logger.debug(result["stderr"])
            if len(result["stdout"]) > 0:
                result["response"] = result["stdout"][0]
                # get the pid
                match = re.search(r"([0-9]+)$", result["response"])
                if match:
                    result["pid"] = int(match.group(1))
                else:
                    self.logger.error("Command (%s) did not return a pid.", command)
            elif len(result["stderr"]) > 0:
                result["response"] = result["stderr"][0]
                self.logger.error(
                    "Command (%s) returned error (%s).", command, result["response"]
                )
            else:
                result["response"] = ""
                self.logger.warning("Command (%s) returned no response.", (command))
        except Exception as e:
            self.logger.error("SSH command failed. Exception (%s).", e)
        return result

    def _command_foreground(self, command):
        """Foreground command execution"""
        self.logger.info(command)
        if not self.is_connected():
            self.logger.error(
                "Foreground command (%s) failed. SSH client is not connected.", command
            )
            return False
        # run command
        result = {"response": None, "stdout": [], "stderr": [], "pid": None}
        try:
            self.logger.info("Running foreground command: %s", command)
            stdin, stdout, stderr = self.ssh.exec_command(command)
            stdout.channel.recv_exit_status()
            result["stdout"] = stdout.readlines()
            result["stderr"] = stderr.readlines()
            self.logger.debug(result["stdout"])
            self.logger.debug(result["stderr"])
            if len(result["stdout"]) > 0:
                result["response"] = result["stdout"]
            elif len(result["stderr"]) > 0:
                result["response"] = result["stderr"]
                self.logger.error(
                    "Command (%s) returned error (%s).", command, result["response"]
                )
            else:
                result["response"] = [""]
                self.logger.warning("Command (%s) returned no response.", command)
        except Exception as e:
            self.logger.error("SSH command failed. Exception (%s).", e)
        return result

    def get_file(self, remote_path, local_path):
        """Retrieve a file over the SSH connection (using SFTP)

        Args:
            remote_path (str): remote file path
            local_path (str): local file path to copy to

        Returns:
            bool: transfer successful?
        """
        if not self.is_connected():
            self.logger.error("SFTP failed. SSH client is not connected.")
            return False
        try:
            sftp = self.ssh.open_sftp()
            sftp.get(remote_path, local_path)
            sftp.close()
        except Exception as e:
            self.logger.error("SFTP failed. Exception (%s).", e)
            return False
        return True

    def is_connected(self):
        """Test the SSH connection, and attempt to reconnect otherwise

        Returns:
            bool: connection successful? (also true if SSH is disabled)
        """
        if not self.enabled:
            self.logger.warning("SSH is disabled, yet tried to test connection.")
            return False
        try:
            self.ssh.exec_command("echo its alive")  # test the connection
            return True
        except Exception as e:  # try to reconnect
            self.logger.warning(
                "SSH command failed. Exception (%s). Reconnecting...", e
            )
            return self.connect()


class Telescope:
    ssh = None

    def __init__(self, config: Config, slack: Slack, lock: threading.Lock):
        self.logger = logging.getLogger("Telescope")
        self.slack = slack
        self.config = config
        self.use_ssh = self.config.getboolean("telescope", "use_ssh", False)

        self.logger.info("Should use SSH? %s", self.use_ssh)

        self.latitude = self.config.get("telescope", "latitude")
        self.longitude = self.config.get("telescope", "longitude")
        self.elevation = self.config.get("telescope", "elevation")
        self.image_dir = self.config.get("telescope", "image_dir")
        self.earthLocation = EarthLocation(
            lat=float(self.latitude) * u.deg,
            lon=float(self.longitude) * u.deg,
            height=float(self.elevation) * u.m,
        )

        # create ssh instance
        self.ssh = SSH(config, slack, lock)
        # enable the connection based on configuration
        if self.use_ssh:
            self.ssh.connect()
        else:
            self.slack.send_message(
                "Telescope interface is running, but the SSH connection is currently disabled."
            )

    def command(self, command, is_background, use_communicate=True, timeout=0):
        result = {"stdout": [], "stderr": []}
        # add a timeout to this command
        if timeout > 0:
            command = "timeout %f " % timeout + command
        # use ssh
        if self.use_ssh:
            if not self.ssh.is_connected():
                self.logger.warning("SSH is not connected")
                self.slack.send_message("Command could not be run, telescope SSH is currently disconnected.")
                # self.ssh.connect()
            else:  # need to reconnect?
                try:
                    self.ssh.command("echo its alive", is_background)
                except Exception as e:
                    self.logger.warning("SSH is not connected. Reconnecting...")
                    self.ssh.connect()
            try:
                return self.ssh.command(command, is_background)
            except Exception as e:
                self.logger.error("Command (%s) via SSH failed. Exception (%s).", command,  e)
                return result
        else:
            # Uses local execution -- Why are we trying this?
            # self.logger.info("Attempting local command execution.")
            # command_array = command.split()
            # try:
            #     sp = subprocess.Popen(
            #         command_array, stderr=subprocess.PIPE, stdout=subprocess.PIPE
            #     )
            #     sp.wait()
            #     if use_communicate: # What is communicate?
            #         output, error = sp.communicate(b"\n\n")
            #         result["stdout"] = output.splitlines()
            #         result["stderr"] = error.splitlines()
            # except Exception as e:
            #     self.logger.error(
            #         "Command (%s) failed. Exception (%s).", command,  e
            #     )
            self.slack.send_message("Command could not be run, telescope SSH is currently disabled.")

            return result

    def get_file(self, remote_path, local_path):
        return self.ssh.get_file(remote_path, local_path)

    # Generic getter is the standard for all SEO get commands
    # To support future telescope interfaces,
    # these will be called by the *explicit* getter

    def getter(self, interface):
        results = self.command(interface.get_command(), interface.is_background())
        result = results["response"]
        # parse the result and assign values to output valuse
        interface.assign_outputs(result)

    # Generic setter is the standard for all SEO get commands
    # To support future telescope interfaces,
    # these will be called by the *explicit* setter
    def setter(self, interface):
        command = interface.assign_inputs()
        results = self.command(command, interface.is_background())
        result = results["response"]
        # parse the result and assign values to output valuse
        interface.assign_outputs(result)

    def get_domecam(self, interface):
        self.setter(interface)

    def get_skycam(self, interface):
        self.setter(interface)

    def to_stars(self, interface):
        self.setter(interface)

    def get_image(self, interface):
        self.setter(interface)

    def get_psf(self, interface):
        self.setter(interface)

    def convert_fits_to_jpg(self, interface):
        self.setter(interface)

    def get_precipitation(self, interface):
        self.getter(interface)

    def get_sun(self, interface):
        self.getter(interface)

    def get_dome(self, interface):
        self.getter(interface)

    def center_dome(self, interface):
        self.setter(interface)

    def home_domer(self, interface):
        self.getter(interface)

    def home_domel(self, interface):
        self.getter(interface)

    def get_slit(self, interface):
        self.getter(interface)

    def set_slit(self, interface):
        self.setter(interface)

    def get_mirror(self, interface):
        self.getter(interface)

    def set_mirror(self, interface):
        self.setter(interface)

    def get_lights(self, interface):
        self.getter(interface)

    def set_lights(self, interface):
        self.setter(interface)

    def get_ccd(self, interface):
        self.getter(interface)

    def set_ccd(self, interface):
        self.setter(interface)

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

    def keepopen(self, interface):
        self.setter(interface)

    def open_observatory(self, interface):
        self.setter(interface)

    def close_observatory(self, interface):
        self.setter(interface)

    def clear_lock(self, interface):
        self.setter(interface)

    def get_where(self, interface):
        self.getter(interface)

    def point(self, interface):
        self.setter(interface)

    def track(self, interface):
        self.setter(interface)

    def get_track(self, interface):
        self.setter(interface)

    def pinpoint(self, interface):
        self.setter(interface)

    def sextractor(self, interface):
        self.setter(interface)

    def psfex(self, interface):
        self.setter(interface)

    def offset(self, interface):
        self.setter(interface)
