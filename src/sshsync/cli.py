import typer

from sshsync.client import SSHClient
from sshsync.config import Config
from sshsync.schemas import FileTransferAction, Target
from sshsync.utils import (
    add_group,
    add_host,
    check_file_exists,
    list_configuration,
    print_error,
    print_ssh_results,
)

app = typer.Typer(
    name="sshsync",
    help="A fast, minimal SSH tool for running commands and syncing files across multiple servers.",
)


@app.command(help="Run a shell command on all configured hosts concurrently")
def all(
    cmd: str = typer.Argument(..., help="The shell command to execute on all hosts."),
    timeout: int = typer.Option(
        10, help="Timeout in seconds for SSH command execution."
    ),
):
    """
    Run a shell command on all configured hosts concurrently.

    Args:
        cmd (str): The shell command to execute remotely.
        timeout (int): Timeout (in seconds) for SSH command execution.
    """
    if not cmd.strip():
        typer.echo("Error: Command cannot be empty.")
        raise typer.Exit(code=1)

    config = Config()

    ssh_client = SSHClient()
    results = ssh_client.begin(cmd, config.hosts, timeout)
    print_ssh_results(results)


@app.command(
    help="Run a shell command on all hosts within the specified group concurrently"
)
def group(
    name: str = typer.Argument(..., help="Name of the host group to target."),
    cmd: str = typer.Argument(..., help="The shell command to execute on the group."),
    timeout: int = typer.Option(
        10, help="Timeout in seconds for SSH command execution."
    ),
):
    """
    Run a shell command on all hosts within the specified group concurrently.

    Args:
        name (str): The name of the host group to target.
        cmd (str): The shell command to execute remotely.
        timeout (int): Timeout (in seconds) for both SSH connection and command execution.
    """
    config = Config()
    hosts = config.get_hosts_by_group(name)

    ssh_client = SSHClient()
    results = ssh_client.begin(cmd, hosts, timeout)
    print_ssh_results(results)


@app.command(help="Add a host or group to the configuration")
def add(
    target: Target = typer.Argument(..., help="Target type to add (host or group)"),
):
    """
    Add a host or group to the configuration.

    Args:
        target (Target): The type of target to add (host or group).
    """
    config = Config()
    if target == Target.HOST:
        config.add_host(add_host())
    else:
        config.add_group(add_group())


@app.command(help="Push a file to remote hosts using SSH.")
def push(
    local_path: str = typer.Argument(
        ..., help="The local path to the file or directory to be pushed."
    ),
    remote_path: str = typer.Argument(
        ..., help="The remote destination path where the file/directory will be placed."
    ),
    all: bool = typer.Option(False, "--all", help="Push to all configured hosts."),
    group: str = typer.Option("", "--group", help="Push to a specific group of hosts."),
    host: str = typer.Option("", "--host", help="Push to a single specific host."),
    recurse: bool = typer.Option(
        False, "--recurse", help="Recursively push a directory and its contents."
    ),
):
    """
    Push a local file to remote destination over SSH.

    You must specify exactly one of the following options to determine where to push:
    --all (to all hosts), --group (to a group), or --host (to a specific host).

    Args:
        local_path (str): The local file or directory to push.
        remote_path (str): The destination path on the remote host(s).
        all (bool): Push to all hosts.
        group (str): Push to a specified group of hosts.
        host (str): Push to a specified individual host.
        recurse (bool): If True, recursively push a directory and all its contents.
    """
    options = [all, bool(group), bool(host)]
    if sum(options) != 1:
        print_error(
            "You must specify exactly one of --all, --group, or --host.",
            True,
        )

    if not check_file_exists(local_path):
        print_error(f"File ({local_path}) does not exist", True)

    config = Config()
    ssh_client = SSHClient()

    host_obj = config.get_host_by_name(host)
    hosts = (
        config.hosts
        if all
        else (
            config.get_hosts_by_group(group)
            if group
            else [host_obj]
            if host_obj is not None
            else []
        )
    )

    if len(hosts) == 0:
        return print_error("Invalid host or group")

    results = ssh_client.begin_transfer(
        local_path, remote_path, hosts, FileTransferAction.PUSH, recurse
    )

    print_ssh_results(results)


@app.command(help="Pull a file from remote hosts using SSH.")
def pull(
    remote_path: str = typer.Argument(
        ..., help="The remote path to the file or directory to be pushed."
    ),
    local_path: str = typer.Argument(
        ..., help="The local destination path where the file/directory will be placed."
    ),
    all: bool = typer.Option(False, "--all", help="Pull from all configured hosts."),
    group: str = typer.Option(
        "", "--group", help="Pull from a specific group of hosts."
    ),
    host: str = typer.Option("", "--host", help="Pull from a single specific host."),
    recurse: bool = typer.Option(
        False, "--recurse", "Recursively pull a directory and its contents."
    ),
):
    """
    Pull a remote file to local destination over SSH.

    You must specify exactly one of the following options to determine where to pull from:
    --all (to all hosts), --group (to a group), or --host (to a specific host).

    Args:
        remote_path (str): The remote file path.
        local_path (str): The local file path.
        all (bool): Pull from all hosts.
        group (str): Pull from a specified group of hosts.
        host (str): Pull from a specified individual host.
        recurse (bool): If True, recursively pull directories and all their contents.
    """
    options = [all, bool(group), bool(host)]
    if sum(options) != 1:
        print_error(
            "You must specify exactly one of --all, --group, or --host.",
            True,
        )

    config = Config()
    ssh_client = SSHClient()

    host_obj = config.get_host_by_name(host)
    hosts = (
        config.hosts
        if all
        else (
            config.get_hosts_by_group(group)
            if group
            else [host_obj]
            if host_obj is not None
            else []
        )
    )

    if len(hosts) == 0:
        return print_error("Invalid host or group")

    results = ssh_client.begin_transfer(
        local_path,
        remote_path,
        hosts,
        FileTransferAction.PULL,
        recurse,
    )

    print_ssh_results(results)


@app.command(help="List all configured host groups and hosts")
def list(
    with_status: bool = typer.Option(
        False, "--with-status", help="Show whether a host is reachable"
    ),
):
    """
    List all configured host groups and hosts.

    Args:
        with_status (bool): Whether to include network reachability status for each host.
    """
    list_configuration(with_status)


@app.command(help="Display the current version of sshsync.")
def version():
    """
    Display the current version.
    """
    typer.echo("v0.2.0")
