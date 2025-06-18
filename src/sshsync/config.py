import re
from pathlib import Path

import structlog
import yaml
from sshconf import read_ssh_config

from sshsync.logging import setup_logging
from sshsync.schemas import Host, HostAuth, YamlConfig

setup_logging()


class ConfigError(Exception):
    """Raised when there is an issue with the configuration"""

    ...


class Config:
    """
    Manages loading, saving, and modifying configuration
    """

    def __init__(self) -> None:
        """
        Initializes the configuration, ensuring the config file exists.
        """
        self.logger = structlog.get_logger()
        home_dir = Path.home()

        self.config_path = Path(home_dir).joinpath(".config", "sshsync", "config.yml")

        config_file = Path(home_dir).joinpath(".ssh", "config")

        if not config_file.exists() or not config_file.is_file():
            raise ConfigError(
                f"{config_file} doesn't exist, sshsync requires this file for host configuration"
            )

        self.ssh_config = read_ssh_config(config_file)

        self.ensure_config_directory_exists()

        self.config = self._load_config()

        self.configure_ssh_hosts()

    def configured_hosts(self):
        """
        Return a list of all configured hosts except the default host.

        Returns:
            list[Host]: List of configured Host objects excluding the default.
        """
        return list(filter(lambda x: x.alias != "default", self.hosts))

    def _default_config(self) -> YamlConfig:
        """
        Return a default YamlConfig object with empty groups and host_auth.

        Returns:
            YamlConfig: Default configuration object.
        """
        return YamlConfig(groups=dict(), host_auth=dict())

    def ensure_config_directory_exists(self) -> None:
        """Ensures the config directory and file exist, creating them if necessary."""
        file = Path(self.config_path)
        if not file.exists():
            file.parent.mkdir(parents=True, exist_ok=True)
            file.touch(exist_ok=True)

    def _resolve_ssh_value(
        self, value: str | int | list[str | int] | None, default: str | int = ""
    ) -> str | int:
        """
        Resolve a value from SSH config, handling lists and defaults.

        Args:
            value (str | int | list[str | int] | None): The value to resolve.
            default (str | int): Default value if input is None or empty.

        Returns:
            str | int: The resolved value.
        """
        if isinstance(value, list):
            return value[0] if value else default
        return value or default

    def configure_ssh_hosts(self) -> None:
        """Parse ~/.ssh/config and populate internal host list.

        Returns:
            None
        """

        default_host = self.ssh_config.host("*")
        default_config = {
            "alias": "default",
            "address": self._resolve_ssh_value(default_host.get("hostname")),
            "username": self._resolve_ssh_value(default_host.get("user")),
            "port": int(self._resolve_ssh_value(default_host.get("port"), 22)),
            "identity_file": self._resolve_ssh_value(default_host.get("identityfile")),
            "groups": [],
        }

        hosts: list[Host] = []

        if default_host:
            hosts.append(Host(**default_config))

        for host in self.ssh_config.hosts():
            if host == "*":
                continue

            config = self.ssh_config.host(host)
            if not config:
                continue

            hosts.append(
                Host(
                    alias=host,
                    address=str(
                        self._resolve_ssh_value(
                            config.get("hostname"), default_config["address"]
                        )
                    ),
                    username=str(
                        self._resolve_ssh_value(
                            config.get("user"), default_config["username"]
                        )
                    ),
                    port=int(
                        self._resolve_ssh_value(
                            config.get("port", 22), default_config["port"]
                        )
                    ),
                    identity_file=str(
                        self._resolve_ssh_value(
                            config.get("identityfile"), default_config["identity_file"]
                        )
                    ),
                    groups=self.get_groups_by_host(host),
                )
            )

        self.hosts = hosts

    def _load_config(self) -> YamlConfig:
        """
        Loads configuration from the YAML.

        Returns:
            YamlConfig: Loaded or default configuration.
        """
        with open(self.config_path) as f:
            try:
                config: dict | None = yaml.safe_load(f)
            except yaml.YAMLError as e:
                raise ConfigError(f"Failed to parse configuration file: {e}")

            if config is None:
                return self._default_config()

            groups: dict[str, list[str]] = config.get("groups", dict())
            host_auth_data: dict = config.get("host_auth", dict())
            host_auth: dict[str, HostAuth] = dict()

            for key, value in host_auth_data.items():
                host_auth[key] = HostAuth(**value)

            return YamlConfig(groups=groups, host_auth=host_auth)

    def _save_yaml(self) -> None:
        """Saves the current configuration to the YAML file."""
        with open(self.config_path, "w") as f:
            yaml.safe_dump(
                self.config.as_dict(),
                f,
                default_flow_style=False,
                indent=4,
            )

    def get_hosts_by_group(self, group: str, regex: str = "") -> list[Host]:
        """Return all hosts that belong to the specified group.

        Args:
            group (str): Group name to filter hosts by.
            regex (str): Only include host aliases with the matching regex

        Returns:
            list[Host]: Hosts that are members of the group.
        """
        return [
            host
            for host in self.hosts
            if group in host.groups
            and host.alias != "default"
            and (not regex or re.search(regex, host.alias))
        ]

    def get_host_by_name(self, name: str) -> Host | None:
        """Find a host by its alias.

        Args:
            name (str): Host alias to search for.

        Returns:
            Host | None: The matching host, or None if not found.
        """
        return next((h for h in self.hosts if h.alias == name), None)

    def add_hosts_to_group(self, group: str, hosts: list[str]) -> None:
        """Add given hosts to the specified group, avoiding duplicates.

        Args:
            group (str): Name of the group to add hosts to.
            hosts (list[str]): List of host aliases to add.

        Returns:
            None
        """
        if group not in self.config.groups:
            self.config.groups[group] = []

        for alias in set(hosts):
            h = self.get_host_by_name(alias)
            if h is None:
                self.logger.warning(
                    f"Host with alias '{alias}' not found in ~/.ssh/config"
                )
                continue

            if group not in h.groups:
                h.groups.append(group)

            if alias not in self.config.groups[group]:
                self.config.groups[group].append(alias)

        self._save_yaml()

    def get_groups_by_host(self, alias: str) -> list[str]:
        """Return all groups that the given host belongs to.

        Args:
            alias (str): Host alias to look up.

        Returns:
            list[str]: Groups the host is a member of.
        """
        return [key for key, value in self.config.groups.items() if alias in value]

    def get_ungrouped_hosts(self) -> list[str]:
        """
        Get aliases of hosts not assigned to any group.

        Returns:
            list[str]: Host aliases without groups.
        """
        return [
            host.alias
            for host in self.hosts
            if not host.groups and host.alias != "default"
        ]

    def get_unconfigured_hosts(self) -> list[dict[str, str]]:
        """
        Get a list of hosts that do not have authentication configured.

        Returns:
            list[dict[str, str]]: List of dicts with alias and identity_file for unconfigured hosts.
        """
        return [
            {"alias": host.alias, "identity_file": host.identity_file}
            for host in self.hosts
            if self.config.host_auth.get(host.alias) is None
        ]

    def assign_groups_to_hosts(self, host_group_mapping: dict[str, list[str]]) -> None:
        """
        Assign groups to hosts and update config.

        Args:
            host_group_mapping (dict[str, list[str]]): Host-to-groups mapping.
        """
        for host, groups in host_group_mapping.items():
            for group in groups:
                if group not in self.config.groups:
                    self.config.groups[group] = [host]
                elif host not in self.config.groups[group]:
                    self.config.groups[group].append(host)

        self._save_yaml()

    def save_host_auth(self, host_auth_details: dict[str, HostAuth]) -> None:
        """
        Save authentication details for hosts and update the YAML config file.

        Args:
            host_auth_details (dict[str, HostAuth]): Mapping of host aliases to HostAuth objects.
        """
        self.config.host_auth = host_auth_details
        self._save_yaml()

    def add_new_host(self, host: Host) -> None:
        """
        Add or update a host in ~/.ssh/config.

        Args:
            host (Host): SSH host details.

        Returns:
            None
        """
        if not self.ssh_config.host(host.alias):
            self.ssh_config.add(host.alias)

        self.ssh_config.set(
            host.alias,
            Hostname=host.address,
            Port=host.port,
            User=host.username,
            IdentityFile=host.identity_file,
        )
        self.ssh_config.save()

        return self.assign_groups_to_hosts({host.alias: host.groups})
