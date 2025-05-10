import sys
from pathlib import Path

import structlog


def get_log_path() -> Path:
    home = Path.home()
    if sys.platform.startswith("win"):
        log_dir = home.joinpath("AppData", "Local", "sshsync", "logs")
    elif sys.platform.startswith("darwin"):
        log_dir = home.joinpath("Library", "Logs", "sshsync")
    else:
        log_dir = home.joinpath(".local", "state", "sshsync")

    if not log_dir.exists():
        log_dir.mkdir(exist_ok=True, parents=True)
    return log_dir


def setup_logging():
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.WriteLoggerFactory(
            file=get_log_path().joinpath("app.log").open("a")
        ),
    )
