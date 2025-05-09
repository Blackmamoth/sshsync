import asyncio
from os import EX_OK
from pathlib import Path

import asyncssh
import structlog

from sshsync.config import Config
from sshsync.logging import setup_logging
from sshsync.schemas import FileTransferAction, Host, SSHResult

setup_logging()


class SSHClient:
    def __init__(self) -> None:
        """Initialize the SSHClient with configuration data from the config file."""
        self.config = Config()
        self.logger = structlog.get_logger()

    def _is_key_encrypted(self, key_path: str) -> bool:
        """Check if the given ssh key is protected by a passphrase

        Returns:
            bool: True if the ssh key is encrypted, False otherwise
        """
        try:
            asyncssh.read_private_key(key_path, passphrase=None)
            return False
        except asyncssh.KeyEncryptionError:
            return True
        except ValueError:
            return True
        except Exception as e:
            print(f"Error reading key: {e}")
            raise

    async def _run_command_across_hosts(
        self, cmd: str, hosts: list[Host]
    ) -> list[SSHResult]:
        """Run a command concurrently on all hosts or a specific group of hosts.

        Args:
            cmd (str): The shell command to execute remotely.
            hosts (list[Host]): The targeted hosts.

        Returns:
            list[SSHResult]: A list of results from each host.
        """

        return await asyncio.gather(
            *[self._execute_command(host, cmd) for host in hosts]
        )

    async def _execute_command(self, host: Host, cmd: str) -> SSHResult:
        """Establish an SSH connection to a host and run a command.

        Args:
            host (HostType): The connection details of the host.
            cmd (str): The command to execute remotely.

        Returns:
            SSHResult: The result of the command execution.
        """
        try:
            conn_kwargs = {
                "host": host.address,
                "username": host.username,
                "port": host.port,
            }
            if not self._is_key_encrypted(host.identity_file):
                conn_kwargs["client_keys"] = [host.identity_file]
            async with asyncssh.connect(**conn_kwargs) as conn:
                result = await conn.run(cmd, check=True, timeout=self.timeout)
                data = {
                    "host": host.address,
                    "exit_status": result.exit_status,
                    "success": result.exit_status == EX_OK,
                    "output": (
                        result.stdout if result.exit_status == EX_OK else result.stderr
                    ),
                }
                self.logger.info("SSH Execution completed", **data)
                return SSHResult(**data)
        except asyncssh.KeyEncryptionError as e:
            data = {
                "host": host.address,
                "exit_status": None,
                "success": False,
                "output": f"Encrypted private key, passphrase required: {e}",
            }
            self.logger.error("SSH error: Encrypted private key", **data)
            return SSHResult(**data)
        except asyncssh.PermissionDenied as e:
            data = {
                "host": host.address,
                "exit_status": None,
                "success": False,
                "output": f"Permission denied: {e.reason}",
            }
            self.logger.error("SSH error: Permission denied", **data)
            return SSHResult(**data)

        except asyncssh.ProcessError as e:
            data = {
                "host": host.address,
                "exit_status": e.exit_status,
                "success": False,
                "output": f"Command failed: {e.stderr}",
            }
            self.logger.error("SSH error: Command failed", **data)
            return SSHResult(**data)

        except Exception as e:
            data = {
                "host": host.address,
                "exit_status": None,
                "success": False,
                "output": f"Unexpected error: {e}",
            }
            self.logger.error("SSH error: Unexpected error", **data)
            return SSHResult(**data)

    async def _transfer_file_across_hosts(
        self,
        local_path: str,
        remote_path: str,
        hosts: list[Host],
        transfer_action: FileTransferAction,
    ) -> list[SSHResult]:
        """Perform file transfer (push or pull) across multiple hosts asynchronously.

        Args:
            local_path (str): Local file or directory path.
            remote_path (str): Remote path for file transfer.
            hosts (list[Host]): List of target hosts.
            transfer_action (FileTransferAction): Transfer direction (PUSH or PULL).

        Returns:
            list[SSHResult]: Transfer results from each host.
        """
        return await asyncio.gather(
            *[
                (
                    self._push(local_path, remote_path, host)
                    if transfer_action == FileTransferAction.PUSH
                    else self._pull(local_path, remote_path, host)
                )
                for host in hosts
            ]
        )

    async def _push(self, local_path: str, remote_path: str, host: Host) -> SSHResult:
        """Push a local file or directory to a remote host over SSH.

        Args:
            local_path (str): Path to the local file or directory.
            remote_path (str): Destination path on the remote host.
            host (Host): Host information for the SSH connection.

        Returns:
            SSHResult: Result of the file transfer.
        """
        if local_path.endswith("/") and Path(local_path).is_dir():
            local_path = local_path.rstrip("/")
        conn_kwargs = {
            "host": host.address,
            "username": host.username,
            "port": host.port,
        }
        if not self._is_key_encrypted(host.identity_file):
            conn_kwargs["client_keys"] = [host.identity_file]
        try:
            async with asyncssh.connect(**conn_kwargs) as conn:
                await asyncssh.scp(
                    local_path, (conn, remote_path), recurse=self.recurse
                )
                data = {
                    "host": host.address,
                    "exit_status": EX_OK,
                    "success": True,
                    "output": f"Successfully sent to {host.address}:{remote_path}",
                }
                self.logger.info("Upload successful", **data)
                return SSHResult(**data)
        except asyncssh.PermissionDenied as e:
            data = {
                "host": host.address,
                "exit_status": None,
                "success": False,
                "output": f"Permission denied: {e.reason}",
            }
            self.logger.error("SSH error: Permission denied", **data)
            return SSHResult(**data)

        except asyncssh.SFTPError as e:
            data = {
                "host": host.address,
                "exit_status": None,
                "success": False,
                "output": f"SFTP error: {e.reason}",
            }
            self.logger.error("SSH error: SFTP error", **data)
            return SSHResult(**data)

        except asyncssh.ChannelOpenError as e:
            data = {
                "host": host.address,
                "exit_status": None,
                "success": False,
                "output": f"Channel open error: {e.reason}",
            }
            self.logger.error("SSH error: Channel open error", **data)
            return SSHResult(**data)

        except Exception as e:
            data = {
                "host": host.address,
                "exit_status": None,
                "success": False,
                "output": f"Unexpected error: {e}",
            }
            self.logger.error("SSH error: Unexpected error", **data)
            return SSHResult(**data)

    async def _pull(self, local_path: str, remote_path: str, host: Host) -> SSHResult:
        """Pull a file or directory from a remote host to the local machine over SSH.

        Args:
            local_path (str): Destination path on the local machine.
            remote_path (str): Path to the file or directory on the remote host.
            host (Host): Host information for the SSH connection.

        Returns:
            SSHResult: Result of the file transfer.
        """
        base_name = Path(remote_path).name
        unique_path = Path(local_path).joinpath(f"{host.address}_{base_name}")
        local_dir = Path(local_path)

        if not local_dir.exists():
            local_dir.mkdir(parents=True, exist_ok=True)

        conn_kwargs = {
            "host": host.address,
            "username": host.username,
            "port": host.port,
        }
        if not self._is_key_encrypted(host.identity_file):
            conn_kwargs["client_keys"] = [host.identity_file]
        try:
            async with asyncssh.connect(**conn_kwargs) as conn:
                await asyncssh.scp(
                    (conn, remote_path), unique_path, recurse=self.recurse
                )
                data = {
                    "host": host.address,
                    "exit_status": EX_OK,
                    "success": True,
                    "output": f"Downloaded successfully from {host.address}:{remote_path}",
                }
                self.logger.info("Download successful", **data)
                return SSHResult(**data)
        except asyncssh.PermissionDenied as e:
            data = {
                "host": host.address,
                "exit_status": None,
                "success": False,
                "output": f"Permission denied: {e.reason}",
            }
            self.logger.error("SSH error: Permission denied", **data)
            return SSHResult(**data)

        except asyncssh.SFTPError as e:
            data = {
                "host": host.address,
                "exit_status": None,
                "success": False,
                "output": f"SFTP error: {e.reason}",
            }
            self.logger.error("SSH error: SFTP error", **data)
            return SSHResult(**data)

        except asyncssh.ChannelOpenError as e:
            data = {
                "host": host.address,
                "exit_status": None,
                "success": False,
                "output": f"Channel open error: {e.reason}",
            }
            self.logger.error("SSH error: Channel open error", **data)
            return SSHResult(**data)

        except Exception as e:
            data = {
                "host": host.address,
                "exit_status": None,
                "success": False,
                "output": f"Unexpected error: {e}",
            }
            self.logger.error("SSH error: Unexpected error", **data)
            return SSHResult(**data)

    def begin(
        self, cmd: str, hosts: list[Host], timeout: int | None = 10
    ) -> list[SSHResult]:
        """Execute a command across multiple hosts using asyncio.

        Args:
            cmd (str): The shell command to execute.
            group (str | None, optional): An optional group name to filter hosts.

        Returns:
            list[SSHResult]: A list of results from each host execution.
        """
        self.timeout = timeout
        return asyncio.run(self._run_command_across_hosts(cmd, hosts))

    def begin_transfer(
        self,
        local_path: str,
        remote_path: str,
        hosts: list[Host],
        transfer_action: FileTransferAction,
        recurse: bool = False,
    ) -> list[SSHResult]:
        """Transfer a file to or from multiple hosts using asyncio.

        Args:
            local_path (str): The local file or directory path.
            remote_path (str): The remote destination or source path.
            hosts (list[Host]): List of target host configurations.
            transfer_action (FileTransferAction): Direction of transfer (PUSH or PULL).

        Returns:
            list[SSHResult]: Results from each host transfer operation.
        """
        self.recurse = recurse
        return asyncio.run(
            self._transfer_file_across_hosts(
                local_path, remote_path, hosts, transfer_action
            )
        )
