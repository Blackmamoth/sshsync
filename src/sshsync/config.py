from pathlib import Path

import yaml

from sshsync.schemas import Host, YamlConfig


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
        home_dir = Path.home()

        self.config_path = Path(home_dir).joinpath(".config", "sshsync", "config.yml")

        self.ensure_config_directory_exists()

        self.config = self._load_config()

    @property
    def hosts(self) -> list[Host]:
        return self.config.hosts

    @property
    def groups(self) -> list[str]:
        return self.config.groups

    def _default_config(self) -> YamlConfig:
        return YamlConfig(hosts=[], groups=[])

    def ensure_config_directory_exists(self) -> None:
        """Ensures the config directory and file exist, creating them if necessary."""
        file = Path(self.config_path)
        if not file.exists():
            file.parent.mkdir(parents=True, exist_ok=True)
            file.touch(exist_ok=True)

    def _load_config(self) -> YamlConfig:
        """
        Loads configuration from the YAML.

        Returns:
            YamlConfig: Loaded or default configuration.
        """
        with open(self.config_path) as f:
            try:
                config: dict = yaml.safe_load(f)
            except yaml.YAMLError as e:
                raise ConfigError(f"Failed to parse configuration file: {e}")

            hosts: list[Host] = [
                Host(**host)
                for host in config.get("hosts", [])
                if isinstance(host, dict)
            ]
            groups: list[str] = config.get("groups", [])

            return YamlConfig(hosts=hosts, groups=groups)

    def _save_yaml(self) -> None:
        """Saves the current configuration to the YAML file."""
        with open(self.config_path, "w") as f:
            yaml.safe_dump(
                self.config.as_dict(),
                f,
                default_flow_style=False,
                indent=4,
            )

    def add_host(self, new_host: Host) -> None:
        """
        Adds a new host to the configuration if it doesn't already exist.

        Args:
            new_host (Host): The host to add.
        """
        existing_hosts = {host.address for host in self.hosts}
        if new_host.address not in existing_hosts:
            self.config.hosts.append(new_host)

        new_groups = {g.strip() for g in new_host.groups if g.strip()}
        existing_groups = set(self.groups)
        self.config.groups.extend(sorted(new_groups - existing_groups))

        self._save_yaml()

    def add_group(self, groups: list[str]) -> None:
        """
        Adds groups to the configuration if they don't already exist.

        Args:
            groups (list[str]): Groups to add.
        """
        new_groups = {g.strip() for g in groups if g.strip()}
        existing_groups = set(self.groups)

        self.config.groups.extend(sorted(new_groups - existing_groups))
        self._save_yaml()

    def get_hosts_by_group(self, group: str) -> list[Host]:
        """Return all hosts that belong to the specified group.

        Args:
            group (str): Group name to filter hosts by.

        Returns:
            list[Host]: Hosts that are members of the group.
        """
        return [host for host in self.hosts if group in host.groups]

    def get_host_by_name(self, name: str) -> Host | None:
        """Find a host by its address.

        Args:
            name (str): Host address to search for.

        Returns:
            Host | None: The matching host, or None if not found.
        """
        return next((h for h in self.config.hosts if h.address == name), None)
