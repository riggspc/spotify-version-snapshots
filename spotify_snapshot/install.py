from rich.console import Console
import shutil
from pathlib import Path
import inspect, os.path
from crontab import CronTab, CronItem
from loguru import logger

console = Console()


def get_spotify_snapshot_executable_path():
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


def install_crontab_entry():
    logger.info("Installing in crontab...")
    user_cron = CronTab(user=True)
    existing_entries = get_crontab_entries(user_cron)
    if existing_entries:
        logger.info("Crontab entries already exist. Skipping.")
        return

    job = user_cron.new(
        command=f'"{get_spotify_snapshot_executable_path()}" --prod-run',
        comment=CRONTAB_COMMENT,
    )
    job.hour.every(8)
    job.run()
    user_cron.write()
    logger.info("Added a new crontab entry and executed it.")


def uninstall_crontab_entry():
    logger.info("Removing crontab entry if it exists...")
    user_cron = CronTab(user=True)
    user_cron.remove_all(comment=CRONTAB_COMMENT)
    user_cron.write()
