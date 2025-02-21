from pathlib import Path
import tomllib  # Python 3.11+
import tomli_w
import os
from dataclasses import dataclass
from typing import Optional
from rich.prompt import Prompt
from loguru import logger
from spotify_snapshot.logging import get_colorized_logger


@dataclass
class SpotifySnapshotConfig:
    git_remote_url: Optional[str] = None
    backup_dir: Optional[Path] = None
    backup_interval_hours: int = 8

    @classmethod
    def load(cls) -> "SpotifySnapshotConfig":
        """Load config from the default config file location."""
        config_path = cls._get_config_path()

        if not config_path.exists():
            return cls.create_initial_config()

        with open(config_path, "rb") as f:
            try:
                config_data = tomllib.load(f)
                backup_dir = config_data.get("backup_dir")
                return cls(
                    git_remote_url=config_data.get("git_remote_url"),
                    backup_dir=(
                        Path(os.path.expandvars(backup_dir)) if backup_dir else None
                    ),
                    backup_interval_hours=config_data.get("backup_interval_hours", 8),
                )
            except tomllib.TOMLDecodeError:
                # Log error and return default config
                return cls()

    @classmethod
    def create_initial_config(cls) -> "SpotifySnapshotConfig":
        """Create initial config file with user input."""
        logger = get_colorized_logger()
        logger.info("\n<yellow>No config file found. Let's create one!</yellow>\n")

        # Get git remote URL
        git_remote_url = Prompt.ask(
            "Enter your Git remote URL (optional, press Enter to skip)", default=""
        )

        # Get backup directory
        xdg_data_home = os.environ.get("XDG_DATA_HOME")
        # Use environment variables in the default path, falling back to $HOME/.local/share if XDG_DATA_HOME is not set
        default_backup_dir = (
            "$XDG_DATA_HOME/spotify-snapshots"
            if xdg_data_home
            else "$HOME/.local/share/spotify-snapshots"
        )
        backup_dir = Prompt.ask(
            "Enter the backup directory path (you can use environment variables like $HOME)",
            default=default_backup_dir,
        )

        # Get backup interval
        backup_interval = Prompt.ask("Enter backup interval in hours", default="8")

        config = cls(
            git_remote_url=git_remote_url if git_remote_url else None,
            backup_dir=Path(os.path.expandvars(backup_dir)),
            backup_interval_hours=int(backup_interval),
        )

        # Save the config
        config_path = cls._get_config_path()
        config_path.parent.mkdir(parents=True, exist_ok=True)

        config_data = {
            "git_remote_url": config.git_remote_url,
            "backup_dir": backup_dir,
            "backup_interval_hours": config.backup_interval_hours,
        }

        with open(config_path, "wb") as f:
            tomli_w.dump(config_data, f)

        logger.info(f"<green>Config file created at {config_path}</green>")

        return config

    @staticmethod
    def _get_config_path() -> Path:
        """Get the path to the config file."""
        xdg_config_home = os.environ.get(
            "XDG_CONFIG_HOME", str(Path.home() / ".config")
        )
        return Path(xdg_config_home) / "spotify-snapshot.toml"
