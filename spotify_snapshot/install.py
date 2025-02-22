import inspect
import os.path
import shutil
import sys
from pathlib import Path

from crontab import CronItem, CronTab
from loguru import logger
from rich.console import Console

from spotify_snapshot.logging import get_colorized_logger

console = Console()


def get_spotify_snapshot_executable_path() -> str:
    # Check if executable is installed on $PATH
    which = shutil.which("spotify-snapshot")
    if which:
        logger.info(f"Found spotify-snapshot executable at {which}")
        return which
    else:
        # Maybe we're in the hatch dev env? We can grab the bin path from the filename
        current_frame = inspect.currentframe()
        if current_frame is None:
            raise RuntimeError("Could not get current frame")

        filename = inspect.getframeinfo(current_frame).filename
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


CRONTAB_COMMENT = "spotify-snapshot"


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
    command = f"{sys.executable} -m spotify_snapshot --push"
    cron = CronTab(user=True)
    logger.info(f"Installing crontab entry for $ {command}")
    existing_entries = get_crontab_entries(cron)
    if existing_entries:
        logger.info("Crontab entries already exist. Removing them...")
        cron.remove_all(comment=CRONTAB_COMMENT)

    # Create new job that runs every interval_hours
    job = cron.new(
        command=command,
        comment=CRONTAB_COMMENT,
    )

    # Set it to run every interval_hours
    job.hour.every(interval_hours)
    # Save the config
    cron.write()
    logger.info(
        f"<green>✓</green> Installed cron job to run every {interval_hours} hours, and am executing it now"
    )
    job.run()


def uninstall_crontab_entry() -> None:
    logger = get_colorized_logger()
    logger.info("Removing crontab entry if it exists...")
    user_cron = CronTab(user=True)
    logger.info(f"Current crontab entries for this program: {get_crontab_entries(user_cron)}")
    user_cron.remove_all(comment=CRONTAB_COMMENT)
    user_cron.write()
