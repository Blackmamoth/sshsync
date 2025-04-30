import asyncio
from os import EX_OK

import asyncssh

from sshsync.config import Config
from sshsync.schemas import Host, SSHResult


class SSHClient:
    def __init__(self) -> None:
        """Initialize the SSHClient with configuration data from the config file."""
        self.config = Config()

    async def _run_command_across_hosts(
        self, cmd: str, group: str | None = None
    ) -> list[SSHResult]:
        """Run a command concurrently on all hosts or a specific group of hosts.

        Args:
            cmd (str): The shell command to execute remotely.
            group (str | None, optional): An optional group name to filter the target hosts.

        Returns:
            list[SSHResult]: A list of results from each host.
        """
        hosts = (
            self.config.hosts
            if group is None
            else self.config.get_hosts_by_group(group)
        )

        tasks = [self._execute_command(host, cmd) for host in hosts]

        return await asyncio.gather(*tasks)

    async def _execute_command(self, host: Host, cmd: str) -> SSHResult:
        """Establish an SSH connection to a host and run a command.

        Args:
            host (HostType): The connection details of the host.
            cmd (str): The command to execute remotely.

        Returns:
            SSHResult: The result of the command execution.
        """
        try:
            async with asyncssh.connect(
                host.address,
                username=host.username,
                client_keys=[host.ssh_key_path],
                port=host.port,
            ) as conn:
                result = await conn.run(cmd, check=True, timeout=self.timeout)
                return SSHResult(
                    host=host.address,
                    exit_status=result.exit_status,
                    success=result.exit_status == EX_OK,
                    output=(
                        result.stdout if result.exit_status == EX_OK else result.stderr
                    ),
                )
        except asyncssh.PermissionDenied as e:
            return SSHResult(
                host=host.address,
                exit_status=None,
                success=False,
                output=f"Permission denied: {e.reason}",
            )
        except asyncssh.ProcessError as e:
            return SSHResult(
                host=host.address,
                exit_status=e.exit_status,
                success=False,
                output=f"Command failed: {e.stderr}",
            )
        except Exception as e:
            return SSHResult(
                host=host.address,
                exit_status=None,
                success=False,
                output=f"Unexpected error: {e}",
            )

    def begin(
        self, cmd: str, group: str | None = None, timeout: int | None = 10
    ) -> list[SSHResult]:
        """Execute a command across multiple hosts using asyncio.

        Args:
            cmd (str): The shell command to execute.
            group (str | None, optional): An optional group name to filter hosts.

        Returns:
            list[SSHResult]: A list of results from each host execution.
        """
        self.timeout = timeout
        return asyncio.run(self._run_command_across_hosts(cmd, group))
