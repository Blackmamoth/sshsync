import ipaddress
import socket
from pathlib import Path

from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table

from sshsync.config import Config
from sshsync.schemas import Host

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
