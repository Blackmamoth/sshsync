# sshsync ⚡🔐

**sshsync** is a fast, minimal CLI tool to run shell commands across multiple remote servers via SSH. Easily target all servers or just a specific group, great for sysadmins, developers, and automation workflows.

## Features ✨

- 🔁 Run shell commands on **all hosts** or **specific groups**
- 🚀 Executes commands **concurrently** across servers
- 🧠 Group-based configuration for easy targeting
- 🕒 Adjustable SSH timeout settings
- 📁 **Push/pull files** between local and remote hosts
- 📊 (Coming Soon) Execution history and logging

## Installation 📦

### Requirements

- Python 3.10 or higher

### Install with pip

```bash
pip install sshsync
```

### Manual Installation

Clone and install manually:

```bash
git clone https://github.com/Blackmamoth/sshsync.git
cd sshsync
pipx install .
```

## Usage 🚀

```bash
sshsync [OPTIONS] COMMAND [ARGS]...
```

**Global Options:**

- `--install-completion` - Install completion for the current shell
- `--show-completion` - Show completion for the current shell
- `--help` - Show help message and exit

## Commands & Usage 🛠️

```bash
sshsync [OPTIONS] COMMAND [ARGS]...
```

### Running Commands on Servers

#### Execute on All Hosts

```bash
sshsync all [OPTIONS] CMD
```

**Options:**

- `--timeout INTEGER` - Timeout in seconds for SSH command execution (default: 10)

**Example:**

```bash
# Check disk space on all servers with a 20 second timeout
sshsync all --timeout 20 "df -h"
```

#### Execute on a Specific Group

```bash
sshsync group [OPTIONS] NAME CMD
```

**Options:**

- `--timeout INTEGER` - Timeout in seconds for SSH command execution (default: 10)

**Example:**

```bash
# Restart web services on production servers
sshsync group web-servers "sudo systemctl restart nginx"
```

### File Transfer Operations

#### Push Files to Remote Hosts

```bash
sshsync push [OPTIONS] LOCAL_PATH REMOTE_PATH
```

**Options:**

- `--all` - Push to all configured hosts
- `--group TEXT` - Push to a specific group of hosts
- `--host TEXT` - Push to a single specific host
- `--recurse` - Recursively push a directory and its contents

**Examples:**

```bash
# Push configuration file to all hosts
sshsync push --all ./config.yml /etc/app/config.yml

# Push directory to web-servers group recursively
sshsync push --group web-servers --recurse ./app/ /var/www/app/
```

#### Pull Files from Remote Hosts

```bash
sshsync pull [OPTIONS] REMOTE_PATH LOCAL_PATH
```

**Options:**

- `--all` - Pull from all configured hosts
- `--group TEXT` - Pull from a specific group of hosts
- `--host TEXT` - Pull from a single specific host
- `--recurse` - Recursively pull a directory and its contents

**Examples:**

```bash
# Pull log files from all database servers
sshsync pull --group db-servers /var/log/mysql/error.log ./logs/

# Pull configuration directory from a specific host
sshsync pull --host prod-web-01 --recurse /etc/nginx/ ./backups/nginx-configs/
```

### Configuration Management

#### Add Hosts or Groups

```bash
sshsync add TARGET:{host|group}
```

**Examples:**

```bash
# Add a new host
sshsync add host

# Add a new group
sshsync add group
```

#### List Configured Hosts and Groups

```bash
sshsync list [OPTIONS]
```

**Options:**

- `--with-status` - Show whether a host is reachable

**Example:**

```bash
# List all hosts with their connection status
sshsync list --with-status
```

#### Show Version

```bash
sshsync version
```

## Configuration 🔧

sshsync stores its configuration in a YAML file located at `~/.config/sshsync/config.yaml`.

### Configuration File Structure

```yaml
groups:
- dev
- web
- db

hosts:
-   address: example.com
    groups:
    - dev
    - web
    port: 22
    ssh_key_path: ~/.ssh/id_ed25519
    username: admin
-   address: db.example.org
    groups:
    - db
    port: 22
    ssh_key_path: ~/.ssh/id_rsa
    username: dbadmin
```

You can edit this file manually or use the built-in commands to add hosts and groups.

### Host Configuration Options

- **address**: The server hostname or IP address
- **username**: SSH username
- **port**: SSH port (default: 22)
- **ssh_key_path**: Path to your SSH private key
- **groups**: List of groups the host belongs to

> **Note**: sshsync uses SSH key-based authentication only. Password authentication is not supported.

## Examples 🧪

```bash
# Check disk space on all servers
sshsync all "df -h"

# View memory usage on all database servers with increased timeout
sshsync group db-servers --timeout 30 "free -m"

# Push configuration files to production servers recursively
sshsync push --group production --recurse ./configs/ /etc/app/configs/

# Pull log files from all web servers
sshsync pull --group web-servers /var/log/nginx/error.log ./logs/

# Check if hosts are reachable
sshsync list --with-status
```

## Upcoming Features 🛣️

- Initial implementation of execution history and logging
- Support for additional authentication methods
- Performance optimizations for large server fleets

## License 📄

MIT License
