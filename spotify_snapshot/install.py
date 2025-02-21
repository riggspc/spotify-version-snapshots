from rich.console import Console
import shutil
from pathlib import Path
import inspect
import os.path
from crontab import CronTab, CronItem
from loguru import logger
from spotify_snapshot.logging import get_colorized_logger
import sys

console = Console()


def get_spotify_snapshot_executable_path() -> str:
    # Check if executable is installed on $PATH
    which = shutil.which("spotify-snapshot")
    if which:
        logger.info(f"Found spotify-snapshot executable at {which}")
        return which
    else:
        # Maybe we're in the hatch dev env? We can grab the bin path from the filename
        filename = inspect.getframeinfo(inspect.currentframe()).filename
        logger.info(f"Filename: {filename}")
        path = os.path.dirname(os.path.abspath(filename))
        pkg_name = "spotify-snapshot"
        path = filename[: filename.rfind(f"{pkg_name}/")] + f"{pkg_name}/bin/{pkg_name}"
        logger.info(f"Path: {path}")
        if Path(path).exists():
            logger.info(f"Found spotify-snapshot executable in hatch dev env at {path}")
            return path
        else:
            raise FileNotFoundError(
                "Could not find spotify-snapshot executable. Make sure it is on your $PATH. You can check with `$ which spotify-snapshot`"
            )


CRONTAB_COMMENT = "spotify_snapshot"


def get_crontab_entries(cron: CronTab) -> list[CronItem] | None:
    entries = list(cron.find_comment(CRONTAB_COMMENT))
    if len(entries) == 0:
        return None
    else:
        return entries


def install_crontab_entry(interval_hours: int = 8) -> None:
    """Install spotify-snapshot as a cron job.

    Args:
        interval_hours: How often to run the backup (in hours)
    """
    logger = get_colorized_logger()
    cron = CronTab(user=True)

    # Remove any existing spotify-snapshot jobs
    cron.remove_all(comment="spotify-snapshot")

    # Create new job that runs every interval_hours
    job = cron.new(
        command=f"{sys.executable} -m spotify_snapshot --prod-run",
        comment="spotify-snapshot",
    )

    # Set to run every interval_hours
    job.every(interval_hours).hours()

    cron.write()
    logger.info(
        f"<green>✓</green> Installed cron job to run every {interval_hours} hours"
    )


def uninstall_crontab_entry() -> None:
    logger = get_colorized_logger()
    logger.info("Removing crontab entry if it exists...")
    user_cron = CronTab(user=True)
    user_cron.remove_all(comment=CRONTAB_COMMENT)
    user_cron.write()
