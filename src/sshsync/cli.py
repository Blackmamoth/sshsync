import typer

from sshsync.client import SSHClient
from sshsync.config import Config
from sshsync.schemas import Target
from sshsync.utils import add_group, add_host, list_configuration, print_ssh_results

app = typer.Typer(
    name="sshsync",
    help="A fast, minimal SSH tool for running commands and syncing files across multiple servers.",
)


@app.command(help="Run a shell command on all configured hosts concurrently")
def all(
    cmd: str = typer.Argument(..., help="The shell command to execute on all hosts."),
    timeout: int = typer.Option(
        10, help="Timeout in seconds for SSH connection and command execution."
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

    ssh_client = SSHClient()
    results = ssh_client.begin(cmd, timeout=timeout)
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
    ssh_client = SSHClient()
    results = ssh_client.begin(cmd, group=name, timeout=timeout)
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


@app.command(help="List all configured host groups and hosts")
def list():
    """
    List all configured host groups and hosts.
    """
    list_configuration()


@app.command(help="Display the current version of sshsync.")
def version():
    """
    Display the current version.
    """
    typer.echo("v0.1.0")
