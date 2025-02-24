import os
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
import inquirer

import tomli_w
from rich.prompt import Prompt

from spotify_snapshot.logging import get_colorized_logger

logger = get_colorized_logger()


@dataclass
class SpotifySnapshotConfig:
    git_remote_url: str | None = None
    backup_interval_hours: int = 8
    macos_backup_dir: Path | None = None
    linux_backup_dir: Path | None = None
    ssh_key_name: str | None = None

    @property
    def backup_dir(self) -> Path | None:
        """Get the backup directory for the current platform."""
        if sys.platform == "darwin":
            return self.macos_backup_dir
        elif sys.platform == "linux":
            return self.linux_backup_dir
        return None

    @property
    def ssh_key_path(self) -> Path | None:
        """Get the full path to the SSH key."""
        if self.ssh_key_name:
            if self.ssh_key_name.startswith("~/.ssh/"):
                return Path(self.ssh_key_name)
        # if we get here, something is probably fucked
        return None

    @classmethod
    def load(cls) -> "SpotifySnapshotConfig":
        """Load config from the default config file location."""
        config_path = cls.get_config_path()

        if not config_path.exists():
            return cls.create_initial_config()

        with open(config_path, "rb") as f:
            try:
                config_data = tomllib.load(f)
                macos_backup_dir = (
                    Path(config_data["macos_backup_dir"])
                    if config_data.get("macos_backup_dir")
                    else ""
                )
                linux_backup_dir = (
                    Path(config_data["linux_backup_dir"])
                    if config_data.get("linux_backup_dir")
                    else ""
                )
                ssh_key_name = config_data.get("ssh_key_name", "")
                git_remote_url = config_data.get("git_remote_url", "")

                if not git_remote_url.startswith("git@"):
                    logger.error(
                        "<red>git_remote_url must be an SSH URL (starts with git@)</red>"
                    )
                    sys.exit(1)

                # if backup dir isn't set for the current platform, error out
                if sys.platform == "darwin" and macos_backup_dir == "":
                    logger.error(
                        "<red>Backup directory not set in config file for macOS. Please set the macos_backup_dir in the config file.</red>"
                    )
                    sys.exit(1)
                elif sys.platform == "linux" and linux_backup_dir == "":
                    logger.error(
                        "<red>Backup directory not set in config file for Linux. Please set the linux_backup_dir in the config file.</red>"
                    )
                    sys.exit(1)
                


                return cls(
                    git_remote_url=git_remote_url,
                    macos_backup_dir=macos_backup_dir,
                    linux_backup_dir=linux_backup_dir,
                    backup_interval_hours=config_data.get("backup_interval_hours", 8),
                    ssh_key_name=ssh_key_name if ssh_key_name else None,
                )
            except tomllib.TOMLDecodeError as e:
                # Log error and return default config
                logger.error(f"<red>Error loading config file: {config_path}</red>")
                logger.error(f"<red>{e}</red>")
                sys.exit(1)

    @classmethod
    def create_initial_config(cls) -> "SpotifySnapshotConfig":
        """Create initial config file with user input."""
        logger = get_colorized_logger()
        logger.info("\n<yellow>No config file found. Let's create one!</yellow>\n")

        # Get git remote URL and ensure it's SSH
        while True:
            git_remote_url = Prompt.ask(
                "(optional) Enter your Git remote URL. Must be an SSH URL (starts with git@)", default=""
            )
            if not git_remote_url:
                break
            if not git_remote_url.startswith("git@"):
                logger.error("Please provide an SSH URL (starts with git@)")
                continue
            git_remote_url = git_remote_url.strip()
            break

        # Get SSH key name if git URL is provided
        ssh_dir = Path.home() / ".ssh"
        # Get list of potential SSH private keys (files without .pub extension)
        ssh_keys = [
            f"~/.ssh/{f.name}"
            for f in ssh_dir.iterdir()
            if f.is_file()
            and not f.name.endswith(".pub")
            and not f.name in ["known_hosts", "config"]
        ]

        if not ssh_keys:
            logger.error(f"<red>No SSH keys found in {ssh_dir}</red>")
            sys.exit(1)

        ssh_key_name = inquirer.prompt(
            [
                inquirer.List(
                    "ssh_key",
                    message="Choose your SSH key",
                    choices=ssh_keys,
                    default=ssh_keys[0],
                )
            ]
        )["ssh_key"]

        # Get backup directory based on platform
        default_backup_dir = str(Path.home() / ".local/share/spotify-snapshots")

        backup_dir = Prompt.ask(
            f"Enter the {'macOS' if sys.platform == 'darwin' else 'Linux'} backup directory path",
            default=default_backup_dir,
        )

        if sys.platform == "darwin":
            macos_backup_dir = Path(backup_dir)
            linux_backup_dir = ""
        elif sys.platform == "linux":
            linux_backup_dir = Path(backup_dir)
            macos_backup_dir = ""
        else:
            logger.error("Unsupported platform. Backup directory will not be set.")
            sys.exit(1)

        # Get backup interval
        backup_interval = Prompt.ask("Enter backup interval in hours", default="8")

        config = cls(
            git_remote_url=git_remote_url if git_remote_url else None,
            macos_backup_dir=macos_backup_dir,
            linux_backup_dir=linux_backup_dir,
            backup_interval_hours=int(backup_interval),
            ssh_key_name=ssh_key_name if ssh_key_name else None,
        )

        # Save the config
        config_path = cls.get_config_path()
        config_path.parent.mkdir(parents=True, exist_ok=True)

        config_data = {
            "git_remote_url": config.git_remote_url,
            "macos_backup_dir": str(config.macos_backup_dir),
            "linux_backup_dir": str(config.linux_backup_dir),
            "backup_interval_hours": config.backup_interval_hours,
            "ssh_key_name": config.ssh_key_name,
        }

        with open(config_path, "wb") as f:
            tomli_w.dump(config_data, f)

        logger.info(f"<green>Config file created at {config_path}</green>")

        return config

    @staticmethod
    def get_config_path() -> Path:
        """Get the path to the config file."""
        xdg_config_home = os.environ.get(
            "XDG_CONFIG_HOME", str(Path.home() / ".config")
        )
        return Path(xdg_config_home) / "spotify-snapshot.toml"
