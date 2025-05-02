from dataclasses import asdict, dataclass
from enum import Enum

from asyncssh import BytesOrStr


class Target(str, Enum):
    """
    Enum representing the types of configuration targets.

    Attributes:
        HOST (TargetType): Indicates a host entry in the configuration.
        GROUP (TargetType): Indicates a group entry in the configuration.
    """

    HOST = "host"
    GROUP = "group"


class FileTransferAction(str, Enum):
    """
    Enum representing the types of transfer actions.

    Attributes:
        PUSH (TransferType): Indicates a push action or file action.
        PULL (TransferType): Indicates a pull action or file download action.
    """

    PUSH = "push"
    PULL = "pull"


@dataclass
class Host:
    """
    Represents a host configuration with connection and grouping details.

    Attributes:
        address (str): The IP address or hostname of the host.
        ssh_key_path (str): The file path to the SSH private key used for authentication.
        username (str): The username used to connect to the host.
        port (int): The SSH port used to connect to the host (typically 22).
        groups (list[str]): A list of group names that this host belongs to.
    """

    address: str
    ssh_key_path: str
    username: str
    port: int
    groups: list[str]


@dataclass
class YamlConfig:
    """
    Represents the YAML configuration containing a list of hosts and groups.

    Attributes:
        hosts (list[HostType]): A list of `HostType` objects, each representing a host in the configuration.
        groups (list[str]): A list of group names.
    """

    hosts: list[Host]
    groups: list[str]

    def as_dict(self) -> dict:
        """
        Converts the `YamlConfig` instance into a dictionary format.

        Returns:
            dict: A dictionary representation of the `YamlConfig` instance, where keys are attribute names
                  and values are the corresponding attribute values.
        """
        return asdict(self)


@dataclass
class SSHResult:
    """
    Stores the result of an SSH operation.

    Attributes:
        host (str): The remote host's address or hostname.
        exit_status (int | None): The exit status of the operation (None if failed).
        success (bool): Whether the operation was successful.
        output (BytesOrStr | None): The output of the operation (None if no output).
    """

    host: str
    exit_status: int | None
    success: bool
    output: BytesOrStr | None
