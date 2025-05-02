import ipaddress
import socket
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from sshsync.config import Config
from sshsync.schemas import Host, SSHResult

console = Console()


def is_valid_ip(ip: str) -> bool:
    """Check if the string is a valid ip address"""
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False


def get_host_name_or_ip() -> str:
    """Prompt the user to enter a valid hostname or ip address"""
    while True:
        host_input = Prompt.ask("Enter the host name or IP address")

        if is_valid_ip(host_input):
            return host_input

        try:
            socket.gethostbyname(host_input)
            return host_input
        except socket.gaierror:
            console.print(
                f"[bold red]Error:[/bold red] Invalid host name or IP address: [bold]{host_input}[/bold]. Please try again."
            )


def check_file_exists(file_path: str) -> bool:
    """Check if the given path exists and is a valid file"""
    path = Path(file_path)
    return path.exists() and path.is_file()


def get_valid_file_path() -> str:
    """Prompt the user to enter a valid file path"""
    while True:
        file_path = Prompt.ask("Enter path to ssh key for this host")
        if check_file_exists(file_path):
            return file_path
        console.log(
            f"[bold red]Error:[/bold red] The file at [bold]{file_path}[/bold] does not exist. Please try again."
        )


def get_valid_username() -> str:
    """Prompt the user to enter a valid username"""
    while True:
        username = Prompt.ask("Enter the SSH username for this server").strip()
        if username:
            break
        console.print(
            "[bold red]Error:[/bold red] Username cannot be empty. Please try again."
        )
    return username


def get_valid_port_number() -> int:
    """Prompt the user to enter a valid port number"""
    while True:
        port_input = Prompt.ask(
            "Enter the port on which the SSH server is running", default="22"
        )
        if port_input.isdigit():
            port = int(port_input)
            if 1 <= port <= 65535:
                return port
        console.print(
            "[bold red]Error:[/bold red] Please enter a valid port number (1–65535)."
        )


def is_host_reachable(host: str, port: int = 80, timeout: int = 2) -> bool:
    """
    Check if a host is reachable by attempting to establish a TCP connection.

    Args:
        host (str): The hostname or IP address to check.
        port (int, optional): The port to attempt to connect to. Defaults to 80.
        timeout (int, optional): Timeout in seconds for the connection attempt. Defaults to 2.

    Returns:
        bool: True if the host is reachable on the specified port, False otherwise.
    """
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (socket.timeout, socket.error):
        return False


def add_group(
    prompt_text: str = "Enter the name(s) of the new group(s) (comma-separated)",
) -> list[str]:
    """Prompt the user for new groups and return a list[str]"""
    group_input = Prompt.ask(prompt_text)
    groups = [group.strip() for group in group_input.split(",")]
    return groups


def add_host() -> Host:
    """Prompt the user for host information and return a Host instance"""
    name = get_host_name_or_ip()
    ssh_key_path = get_valid_file_path()
    username = get_valid_username()
    port = get_valid_port_number()
    groups = add_group(
        "Enter the name(s) of the group(s) this host can belong to (comma-separated)"
    )
    return Host(
        address=name,
        ssh_key_path=ssh_key_path,
        username=username,
        port=port,
        groups=groups,
    )


def list_configuration(with_status: bool) -> None:
    """
    Display the current SSH configuration including hosts and groups in rich-formatted tables.

    This function retrieves the loaded YAML configuration using the `Config` class,
    and displays:
      - A list of all defined group names.
      - A list of all configured hosts with details like address, username, port, SSH key path,
        group memberships and optionally host reachability.

    Uses the `rich` library to print visually styled tables to the console.

    Returns:
        None: This function prints the results to the console and does not return a value.
    """
    config = Config()

    hosts = config.hosts
    groups = config.groups

    if groups:
        group_table = Table(title="Configured Groups")
        group_table.add_column("Group Name", style="cyan", no_wrap=True)

        for group_name in groups:
            group_table.add_row(group_name)

        console.print(group_table)
    else:
        console.print("[bold yellow]No groups configured.[/bold yellow]")

    if hosts:
        host_table = Table(title="Configured Hosts")
        host_table.add_column("Host", style="cyan", no_wrap=True)
        host_table.add_column("Username", style="green")
        host_table.add_column("Port", style="blue")
        host_table.add_column("SSH Key", style="magenta")
        host_table.add_column("Groups", style="white")
        if with_status:
            host_table.add_column("Status")

        for host in hosts:
            row = [
                host.address,
                host.username,
                str(host.port),
                host.ssh_key_path,
                ", ".join(host.groups) if host.groups else "-",
            ]
            if with_status:
                row.append(
                    "[bold green]Up[/bold green]"
                    if is_host_reachable(host.address, host.port)
                    else "[bold red]Down[/bold red]"
                )
            host_table.add_row(*row)

        console.print(host_table)
    else:
        console.print("[bold yellow]No hosts configured.[/bold yellow]")


def print_ssh_results(results: list[SSHResult]) -> None:
    """
    Display SSH command execution results in a formatted table.

    Args:
        results (list[SSHResult | BaseException]): A list containing the results of SSH command
        executions, which may include `SSHResult` objects or exceptions from failed tasks.

    Returns:
        None: This function prints the results to the console and does not return a value.
    """

    table = Table(title="SSHSYNC Results")
    table.add_column("Host", style="cyan", no_wrap=True)
    table.add_column("Status", style="green")
    table.add_column("Output", style="magenta")

    for result in results:
        if result is not None and not isinstance(result, BaseException):
            status = "[green]Success[/green]" if result.success else "[red]Failed[/red]"
            output = f"{result.output.strip()}\n" if result.output else "-"
            table.add_row(result.host, status, str(output))

    console.print(table)


def print_error(message: str, exit: bool = False) -> None:
    """
    Display an error message in a styled panel and optionally exit the program.

    Args:
        message (str): The error message to display.
        exit (bool, optional): If True, exits the program with status code 1. Defaults to False.

    Raises:
        typer.Exit: If exit is True, the function raises a typer.Exit with code 1.
    """
    console.print(
        Panel(
            message,
            title="Error",
            title_align="left",
            border_style="red",
        ),
        style="bold white",
    )
    if exit:
        raise typer.Exit(1)
