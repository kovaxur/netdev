"""
ComwareLikeDevice Class is abstract class for using in HP Comware like devices

Connection Method are based upon AsyncSSH and should be running in asyncio loop
"""

import re

from .base import BaseDevice
from .logger import logger


class ComwareLikeDevice(BaseDevice):
    """
    This Class for working with hp comware like devices

    HP Comware like devices having several concepts:

    * user exec or user view. This mode is using for getting information from device
    * system view. This mode is using for configuration system
    """

    def __init__(self, host=u'', username=u'', password=u'', port=22, device_type=u'', known_hosts=None,
                 local_addr=None, client_keys=None, passphrase=None, loop=None):
        """
        Initialize  class for asynchronous working with network devices

        :param str host: hostname or ip address for connection
        :param str username: username for logger to device
        :param str password: password for user for logger to device
        :param int port: ssh port for connection. Default is 22
        :param str device_type: network device type
        :param known_hosts: file with known hosts. Default is None (no policy). with () it will use default file
        :param str local_addr: local address for binding source of tcp connection
        :param client_keys: path for client keys. With () it will use default file in OS.
        :param str passphrase: password for encrypted client keys
        :param loop: asyncio loop object
        """
        super().__init__(host=host, username=username, password=password, port=port, device_type=device_type,
                         known_hosts=known_hosts, local_addr=local_addr, client_keys=client_keys, passphrase=passphrase,
                         loop=loop)

    _delimiter_list = ['>', ']']
    """All this characters will stop reading from buffer. It mean the end of device prompt"""

    _delimiter_left_list = ['<', '[']
    """Begging prompt characters. Prompt must contain it"""

    _pattern = r"[{}]{}[\-\w]*[{}]"
    """Pattern for using in reading buffer. When it found processing ends"""

    _disable_paging_command = 'screen-length disable'
    """Command for disabling paging"""

    _system_view_enter = 'system-view'
    """Command for entering to system view"""

    _system_view_exit = 'return'
    """Command for existing from system view to user view"""

    _system_view_check = ']'
    """Checking string in prompt. If it's exist im prompt - we are in system view"""

    async def _set_base_prompt(self):
        """
        Setting two important vars
            base_prompt - textual prompt in CLI (usually hostname)
            base_pattern - regexp for finding the end of command. IT's platform specific parameter

        For Comware devices base_pattern is "[\]|>]prompt(\-\w+)?[\]|>]
        """
        logger.info("Host {}: Setting base prompt".format(self._host))
        prompt = await self._find_prompt()
        # Strip off trailing terminator
        self._base_prompt = prompt[1:-1]
        delimiter_right = map(re.escape, type(self)._delimiter_list)
        delimiter_right = r"|".join(delimiter_right)
        delimiter_left = map(re.escape, type(self)._delimiter_left_list)
        delimiter_left = r"|".join(delimiter_left)
        base_prompt = re.escape(self._base_prompt[:12])
        pattern = type(self)._pattern
        self._base_pattern = pattern.format(delimiter_left, base_prompt, delimiter_right)
        logger.debug("Host {}: Base Prompt: {}".format(self._host, self._base_prompt))
        logger.debug("Host {}: Base Pattern: {}".format(self._host, self._base_pattern))
        return self._base_prompt

    async def _check_system_view(self):
        """Check if we are in system view. Return boolean"""
        logger.info('Host {}: Checking system view'.format(self._host))
        check_string = type(self)._system_view_check
        self._stdin.write(self._normalize_cmd('\n'))
        output = await self._read_until_prompt()
        return check_string in output

    async def _system_view(self):
        """Enter to system view"""
        logger.info('Host {}: Entering to system view'.format(self._host))
        output = ""
        system_view_enter = type(self)._system_view_enter
        if not await self._check_system_view():
            self._stdin.write(self._normalize_cmd(system_view_enter))
            output += await self._read_until_prompt()
            if not await self._check_system_view():
                raise ValueError("Failed to enter to system view")
        return output

    async def _exit_system_view(self):
        """Exit from system view"""
        logger.info('Host {}: Exiting from system view'.format(self._host))
        output = ""
        system_view_exit = type(self)._system_view_exit
        if await self._check_system_view():
            self._stdin.write(self._normalize_cmd(system_view_exit))
            output += await self._read_until_prompt()
            if await self._check_system_view():
                raise ValueError("Failed to exit from system view")
        return output

    async def send_config_set(self, config_commands=None, exit_system_view=False):
        """
        Sending configuration commands to device
        Automatically exits/enters system-view.

        :param list config_commands: iterable string list with commands for applying to network devices in system view
        :param bool exit_system_view: If true it will quit from system view automatically
        :return: The output of this commands
        """

        if config_commands is None:
            return ''

        # Send config commands
        output = await self._system_view()
        output += await super().send_config_set(config_commands=config_commands)

        if exit_system_view:
            output += await self._exit_system_view()

        output = self._normalize_linefeeds(output)
        logger.debug("Host {}: Config commands output: {}".format(self._host, repr(output)))
        return output
