import asyncio
from os import EX_OK
from pathlib import Path
from typing import Literal

import asyncssh
import keyring
import structlog
from rich.progress import Progress

from sshsync.config import Config
from sshsync.logging import setup_logging
from sshsync.schemas import FileTransferAction, Host, SSHDryRun, SSHResult

setup_logging()


class SSHClient:
    def __init__(self) -> None:
        """Initialize the SSHClient with configuration data from the config file."""
        self.logger = structlog.get_logger()
        self.config = Config()

    def _is_key_encrypted(self, key_path: str) -> bool:
        """Check if the given ssh key is protected by a passphrase

        Returns:
            bool: True if the ssh key is encrypted, False otherwise
        """
        # Check if key_path is empty or points to a directory
        path = Path(key_path).expanduser()
        if not key_path or not path.exists() or path.is_dir():
            return False  # Cannot be encrypted if it's not a valid file
        try:
            asyncssh.read_private_key(key_path, passphrase=None)
            return False
        except asyncssh.KeyEncryptionError:
            return True
        except ValueError:
            return True
        except Exception:
            self.logger.exception("Error reading key")
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

        results = []
        with Progress() as progress:
            tasks = [self._execute_command(host, cmd, progress) for host in hosts]
            results = await asyncio.gather(*tasks)
        return results

    def begin_dry_run_exec(
        self, cmd: str, hosts: list[Host], operation: Literal["exec", "push", "pull"]
    ) -> list[SSHDryRun]:
        """
        Simulate a shell command on multiple hosts.

        Args:
            cmd (str): Command to simulate.
            hosts (list[Host]): Hosts to run the command on.
            operation (Literal["exec", "push", "pull"]): Operation type.

        Returns:
            list[SSHDryRun]: Simulated command details per host.
        """
        return [
            SSHDryRun(
                host.address,
                host.alias,
                host.username,
                host.port,
                operation,
                cmd,
                None,
                None,
            )
            for host in hosts
        ]

    def begin_dry_run_transfer(
        self,
        hosts: list[Host],
        local_path: str,
        remote_path: str,
        operation: Literal["push", "pull"],
    ) -> list[SSHDryRun]:
        """
        Simulate a file transfer on multiple hosts.

        Args:
            hosts (list[Host]): Hosts involved.
            local_path (str): Local file/directory path.
            remote_path (str): Remote destination path.
            direction (Literal["push", "pull"]): Transfer direction.

        Returns:
            list[SSHDryRun]: Simulated transfer details per host.
        """
        return [
            SSHDryRun(
                host.address,
                host.alias,
                host.username,
                host.port,
                operation,
                None,
                local_path,
                remote_path,
            )
            for host in hosts
        ]

    def _handle_ssh_exceptions(self, e: Exception, host: Host) -> SSHResult:
        """
        Logs SSH exceptions and returns a failed SSHResult.

        Args:
            e (Exception): Exception raised during SSH.
            host (Host): Host where the error occurred.

        Returns:
            SSHResult: Result with error info and success=False.
        """
        data = {
            "host": host.address,
            "exit_status": None,
            "success": False,
        }

        if isinstance(e, asyncssh.KeyEncryptionError):
            data["output"] = f"Encrypted private key, passphrase required: {e}"
        elif isinstance(e, asyncssh.PermissionDenied):
            data["output"] = f"Permission denied: {e.reason}"
        elif isinstance(e, asyncssh.TimeoutError):
            data["output"] = f"Timeout error: {e.reason}"
            data["exit_status"] = e.exit_status
        elif isinstance(e, asyncssh.ProcessError):
            data["output"] = f"Command failed: {e}"
            data["exit_status"] = e.exit_status
        elif isinstance(e, asyncssh.SFTPError):
            data["output"] = f"SFTP error: {e.reason}"
        elif isinstance(e, asyncssh.ChannelOpenError):
            data["output"] = f"Channel open error: {e.reason}"
        else:
            data["output"] = f"Unexpected error: {e}"

        self.logger.exception(data["output"], **data)
        return SSHResult(**data)

    def get_host_pass(self, host: str) -> str | None:
        return keyring.get_password("sshsync", host)

    async def _execute_command(
        self, host: Host, cmd: str, progress: Progress
    ) -> SSHResult:
        """Establish an SSH connection to a host and run a command."""

        task = progress.add_task(
            f"[cyan]{host.alias}[/cyan]: Connecting...", total=None, start=False
        )

        try:
            progress.start_task(task)
            conn_kwargs = {
                "host": host.address,
                "username": host.username,
                "port": host.port,
            }

            # Only use identity_file if it's a valid file
            if host.identity_file and Path(host.identity_file).expanduser().is_file():
                if not self._is_key_encrypted(host.identity_file):
                    conn_kwargs["client_keys"] = [host.identity_file]
                else:
                    host_pass = self.get_host_pass(host.alias)
                    if host_pass:
                        host_auth = self.config.config.host_auth.get(host.alias, None)
                        if host_auth:
                            if host_auth.auth == "key":
                                conn_kwargs["client_keys"] = [host.identity_file]
                                conn_kwargs["passphrase"] = host_pass
                            else:
                                conn_kwargs["password"] = host_pass

            async with asyncssh.connect(**conn_kwargs) as conn:
                progress.update(
                    task,
                    description=f"[green]{host.alias}: Connected. Running command...[/green]",
                )

                result = await conn.run(cmd, check=True, timeout=self.timeout)

                progress.update(
                    task, description=f"[green]{host.alias}: Command completed[/green]"
                )
                progress.remove_task(task)

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

        except Exception as e:
            progress.update(
                task, description=f"[red]{host.alias}: Error occurred[/red]"
            )
            progress.remove_task(task)
            return self._handle_ssh_exceptions(e, host)

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
        results = []
        with Progress() as progress:
            tasks = [
                (
                    self._push(local_path, remote_path, host, progress)
                    if transfer_action == FileTransferAction.PUSH
                    else self._pull(local_path, remote_path, host, progress)
                )
                for host in hosts
            ]
            results = await asyncio.gather(*tasks)
            return results

    async def _push(
        self, local_path: str, remote_path: str, host: Host, progress: Progress
    ) -> SSHResult:
        """Push a local file or directory to a remote host over SSH.

        Args:
            local_path (str): Path to the local file or directory.
            remote_path (str): Destination path on the remote host.
            host (Host): Host information for the SSH connection.

        Returns:
            SSHResult: Result of the file transfer.
        """
        task = progress.add_task(
            f"[cyan]{host.alias}[/cyan]: Connecting...", total=None, start=False
        )

        if local_path.endswith("/") and Path(local_path).is_dir():
            local_path = local_path.rstrip("/")

        conn_kwargs = {
            "host": host.address,
            "username": host.username,
            "port": host.port,
        }

        if host.identity_file and Path(host.identity_file).expanduser().is_file():
            if not self._is_key_encrypted(host.identity_file):
                conn_kwargs["client_keys"] = [host.identity_file]
            else:
                host_pass = self.get_host_pass(host.alias)
                if host_pass:
                    host_auth = self.config.config.host_auth.get(host.alias, None)
                    if host_auth:
                        if host_auth.auth == "key":
                            conn_kwargs["client_keys"] = [host.identity_file]
                            conn_kwargs["passphrase"] = host_pass
                        else:
                            conn_kwargs["password"] = host_pass

        try:
            progress.start_task(task)
            async with asyncssh.connect(**conn_kwargs) as conn:
                progress.update(
                    task,
                    description=f"[green]{host.alias}: Connected. Upload Started...[/green]",
                )
                await asyncssh.scp(
                    local_path, (conn, remote_path), recurse=self.recurse
                )
                progress.update(
                    task, description=f"[green]{host.alias}: Upload completed[/green]"
                )
                progress.remove_task(task)
                data = {
                    "host": host.address,
                    "exit_status": EX_OK,
                    "success": True,
                    "output": f"Successfully sent to {host.address}:{remote_path}",
                }
                self.logger.info("Upload successful", **data)
                return SSHResult(**data)
        except Exception as e:
            progress.update(
                task, description=f"[red]{host.alias}: Error occurred[/red]"
            )
            progress.remove_task(task)
            return self._handle_ssh_exceptions(e, host)

    async def _pull(
        self, local_path: str, remote_path: str, host: Host, progress: Progress
    ) -> SSHResult:
        """Pull a file or directory from a remote host to the local machine over SSH.

        Args:
            local_path (str): Destination path on the local machine.
            remote_path (str): Path to the file or directory on the remote host.
            host (Host): Host information for the SSH connection.

        Returns:
            SSHResult: Result of the file transfer.
        """
        task = progress.add_task(
            f"[cyan]{host.alias}[/cyan]: Connecting...", total=None, start=False
        )

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

        if host.identity_file and Path(host.identity_file).expanduser().is_file():
            if not self._is_key_encrypted(host.identity_file):
                conn_kwargs["client_keys"] = [host.identity_file]
            else:
                host_pass = self.get_host_pass(host.alias)
                if host_pass:
                    host_auth = self.config.config.host_auth.get(host.alias, None)
                    if host_auth:
                        if host_auth.auth == "key":
                            conn_kwargs["client_keys"] = [host.identity_file]
                            conn_kwargs["passphrase"] = host_pass
                        else:
                            conn_kwargs["password"] = host_pass

        try:
            progress.start_task(task)
            async with asyncssh.connect(**conn_kwargs) as conn:
                progress.update(
                    task,
                    description=f"[green]{host.alias}: Connected. Download Started...[/green]",
                )
                await asyncssh.scp(
                    (conn, remote_path), unique_path, recurse=self.recurse
                )
                progress.update(
                    task, description=f"[green]{host.alias}: Download completed[/green]"
                )
                progress.remove_task(task)
                data = {
                    "host": host.address,
                    "exit_status": EX_OK,
                    "success": True,
                    "output": f"Downloaded successfully from {host.address}:{remote_path}",
                }
                self.logger.info("Download successful", **data)
                return SSHResult(**data)
        except Exception as e:
            progress.update(
                task, description=f"[red]{host.alias}: Error occurred[/red]"
            )
            progress.remove_task(task)
            return self._handle_ssh_exceptions(e, host)

    def begin(
        self,
        cmd: str,
        hosts: list[Host],
        timeout: int = 10,
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
