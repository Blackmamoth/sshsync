# sshsync ⚡🔐

**sshsync** is a fast, minimal CLI tool to run shell commands across multiple remote servers via SSH. Easily target all servers or just a specific group — great for sysadmins, developers, and automation workflows.

> 🔜 *File push/pull support is coming soon!*

---

## Features ✨

- 🔁 Run shell commands on **all hosts** or **specific groups**
- 🚀 Executes commands **concurrently** across servers
- 🧠 Group-based configuration for easy targeting
- 🕒 Adjustable SSH timeout settings
- 📁 Coming soon: **push/pull files from remote hosts**

---

## Installation 📦

Install with `pip` (Python 3.12+):

```bash
pip install sshsync
```

Or clone and install manually:

```bash
git clone https://github.com/Blackmamoth/sshsync.git
cd sshsync
pipx install .
```

## Usage 🚀

Basic usage:

```bash
sshsync [COMMAND] [OPTIONS]
```

### Run a Command on All Hosts

```bash
sshsync all "uptime"
```

### Run a Command on a Specific Group

```bash
sshsync group web-servers "sudo systemctl restart nginx"
```

### Add a Host or Group

```bash
sshsync add host 
sshsync add group
```

### List Hosts and Groups

```bash
sshsync list
```

### Show Version

```bash
sshsync version
```


