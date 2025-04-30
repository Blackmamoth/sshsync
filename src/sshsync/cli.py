import typer

from sshsync.config import Config
from sshsync.schemas import Target
from sshsync.utils import add_group, add_host, list_configuration

app = typer.Typer(
    name="sshsync",
    help="A fast, minimal SSH tool for running commands and syncing files across multiple servers.",
)


@app.command()
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


@app.command()
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
