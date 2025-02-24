import os
import subprocess
from pathlib import Path
from sys import exit
from time import sleep
import click
from rich import print as rprint

from spotify_snapshot.__about__ import __version__
from spotify_snapshot.config import SpotifySnapshotConfig
from spotify_snapshot.install import install_crontab_entry, uninstall_crontab_entry
from spotify_snapshot.logging import configure_logging, get_colorized_logger
from spotify_snapshot import gitutils, outputfileutils, spotify
from spotify_snapshot.spotify import SpotifyCredentialsManager
from spotify_snapshot.spotify_snapshot_output_manager import (
    SpotifySnapshotOutputManager,
)
from spotify_snapshot.lockfile import process_lock, ProcessLockError


@click.command(
    epilog="https://github.com/alichtman/spotify-snapshot",
    context_settings={
        "help_option_names": ["-h", "-help", "--help"],
    },
)
@click.option(
    "-t",
    "--test",
    is_flag=True,
    default=False,
    help="Runs in test mode, writing to a test repo instead of the production snapshots repo.",
)
@click.option(
    "--backup-all",
    is_flag=True,
    default=False,
    help="Backup all library data, including liked songs, saved albums, and playlists.",
)
@click.option(
    "--backup-liked-songs", is_flag=True, default=False, help="Backup liked songs only."
)
@click.option(
    "--backup-saved-albums",
    is_flag=True,
    default=False,
    help="Backup saved albums only.",
)
@click.option(
    "--backup-playlists", is_flag=True, default=False, help="Backup playlists only."
)
@click.option(
    "--pretty_print",
    type=click.Path(exists=True),
    required=False,
    help="Path to a file to print the TSV data of.",
)
@click.option(
    "--install",
    is_flag=True,
    default=False,
    help="Install spotify-snapshot as a cron job.",
)
@click.option(
    "--uninstall",
    is_flag=True,
    default=False,
    help="Remove the spotify-snapshot cron job.",
)
@click.option("--version", "-v", is_flag=True, help="Print the version")
@click.option(
    "--edit-config",
    is_flag=True,
    default=False,
    help="Open the config file in your default editor ($EDITOR)",
)
@click.option(
    "--push",
    is_flag=True,
    default=False,
    help="Push changes to the remote repository.",
)
@click.option(
    "--set-creds",
    is_flag=True,
    default=False,
    help="Set Spotify API credentials in system keyring",
)
@click.option(
    "--clear-creds",
    is_flag=True,
    default=False,
    help="Remove Spotify API credentials from system keyring",
)
def main(
    test: bool,
    backup_all: bool,
    backup_liked_songs: bool,
    backup_saved_albums: bool,
    backup_playlists: bool,
    pretty_print: str | None,
    install: bool,
    uninstall: bool,
    version: bool,
    edit_config: bool,
    push: bool,
    set_creds: bool,
    clear_creds: bool,
) -> None:
    """Fetch and snapshot Spotify library data."""
    logger = get_colorized_logger()

    if version:
        rprint(
            f"[bold green]spotify-snapshot[/bold green] [bold blue]{__version__}[/bold blue]"
        )
        return

    # Handle credential management before other operations
    if set_creds:
        SpotifyCredentialsManager.prompt_and_store_credentials()
        return

    if clear_creds:
        SpotifyCredentialsManager.remove_stored_credentials()
        return

    configure_logging()

    # This will guide the user through creating the config file if it doesn't exist
    config = SpotifySnapshotConfig.load()

    # Handle install request if specified
    if install:
        install_crontab_entry(interval_hours=config.backup_interval_hours)
        return

    try:
        with process_lock.acquire():
            # Ensure Spotify credentials are configured
            SpotifyCredentialsManager.ensure_spotify_credentials()

            # Handle uninstall request if specified
            if uninstall:
                uninstall_crontab_entry()
                return

            # Handle edit-config request if specified
            if edit_config:
                editor = os.environ.get(
                    "EDITOR", "vim"
                )  # Default to vim if $EDITOR not set
                logger.info(f"Opening config file in {editor}")
                subprocess.call([editor, config.get_config_path()])
                return

            # Handle pretty print request if specified
            if pretty_print:
                outputfileutils.pretty_print_tsv_table(Path(pretty_print))
                return

            # TODO: Add as custom name for --test, so we don't need to do reassingment
            is_test_mode: bool = test

            if is_test_mode:
                logger.info("<yellow>Running in test mode...</yellow>")
            else:
                logger.info("<yellow>*** RUNNING IN PROD MODE ***</yellow>")

            sp_client = spotify.create_spotify_client()

            logger.info(
                f"<green>Logged in as {spotify.get_username(sp_client)}</green>"
            )

            gitutils.setup_git_repo_if_needed(is_test_mode)

            # Set remote URL if configured
            if config.git_remote_url:
                gitutils.set_remote_url(config.git_remote_url, is_test_mode)

            snapshots_repo_name = gitutils.get_repo_filepath(is_test_mode)
            SpotifySnapshotOutputManager.initialize(snapshots_repo_name)

            # If no specific backup option is selected, default to backing up everything
            if not any(
                [backup_all, backup_liked_songs, backup_saved_albums, backup_playlists]
            ):
                backup_all = True
                logger.info(
                    "<yellow>No specific backup option selected. Backing up all data...</yellow>"
                )

            if backup_all or backup_liked_songs:
                spotify.write_liked_songs_to_git_repo(sp_client)

            if backup_all or backup_saved_albums:
                sleep_time = 10
                logger.info(f"<yellow>Sleeping for {sleep_time} seconds...</yellow>")
                sleep(sleep_time)
                spotify.write_saved_albums_to_git_repo(sp_client)

            if backup_all or backup_playlists:
                sleep_time = 30
                logger.info(f"<yellow>Sleeping for {sleep_time} seconds...</yellow>")
                sleep(sleep_time)
                spotify.write_playlists_to_git_repo(sp_client)

            username = spotify.get_username(sp_client)
            do_changes_to_push_exist = gitutils.commit_files(is_test_mode, username)
            if do_changes_to_push_exist:
                gitutils.maybe_git_push(
                    is_test_mode, should_push_without_prompting_user=push
                )
            else:
                logger.info(
                    "<yellow>Exiting without pushing changes, since there are no changes to push</yellow>"
                )

            gitutils.cleanup_repo()
            exit(0)

    except Exception as e:
        logger.error(f"<red>An error occurred: {e.with_traceback}</red>")
        raise e


if __name__ == "__main__":
    main()
