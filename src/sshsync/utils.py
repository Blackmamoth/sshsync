import ipaddress
import socket
from pathlib import Path

from rich.console import Console
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


def list_configuration() -> None:
    """
    Display the current SSH configuration including hosts and groups in rich-formatted tables.

    This function retrieves the loaded YAML configuration using the `Config` class,
    and displays:
      - A list of all defined group names.
      - A list of all configured hosts with details like address, username, port, SSH key path,
        and group memberships.

    Uses the `rich` library to print visually styled tables to the console.

    Returns:
        None: This function prints the results to the console and does not return a value.
    """
    config = Config()
    console = Console()

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

        for host in hosts:
            host_table.add_row(
                host.address,
                host.username,
                str(host.port),
                host.ssh_key_path,
                ", ".join(host.groups) if host.groups else "-",
            )

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
