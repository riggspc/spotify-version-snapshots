import click
from rich import print as rprint
from spotify_snapshot import gitutils, spotify, outputfileutils
from spotify_snapshot.spotify_snapshot_output_manager import (
    SpotifySnapshotOutputManager,
)
from spotify_snapshot.install import install_crontab_entry
from spotify_snapshot.logging import configure_logging_to_syslog
from pathlib import Path

API_REQUEST_SLEEP_TIME_SEC = 0.5
# For albums, playlists, etc - the Spotify API has a (current) max of 50 things
# it can fetch at a time
API_REQUEST_LIMIT = 50


# General TODOs:
#
# Error Handling & Logging:
# - Add comprehensive error handling
# - Replace print statements with proper logging
#
# Code Quality:
# - Add support for podcasts (not just music tracks)
#
# Playlist Management:
# - Handle unnamed playlists (e.g. rename to "Deleted playlist")
#
# Repository:
# - Add command line option to push to remote repo


@click.command()
@click.option(
    "-p",
    "--prod-run",
    is_flag=True,
    default=False,
    help='Runs the "real" version of the script, fetching everything and writing to the "real" snapshots repo instead of a test one.',
)
@click.option(
    "-n",
    "--no-commit",
    is_flag=True,
    default=False,
    help="When present, will run the entire script but not commit the results, leaving the repo dirty for manual committing later.",
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
    help="Install spotify-snapshot as a cron job that runs every 8 hours.",
)
def main(
    prod_run,
    no_commit,
    backup_all,
    backup_liked_songs,
    backup_saved_albums,
    backup_playlists,
    pretty_print,
    install,
):
    """Fetch and snapshot Spotify library data."""

    configure_logging_to_syslog()

    # Handle install request if specified
    if install:
        install_crontab_entry()
        return

    # Handle pretty print request if specified
    if pretty_print:
        outputfileutils.pretty_print_tsv_table(pretty_print)
        return

    is_test_mode = not prod_run

    if is_test_mode:
        rprint("[yellow]Running in test mode[/yellow]...")
    else:
        rprint("[yellow]*** RUNNING IN PROD MODE ***[/yellow]")

    sp_client = spotify.create_spotify_client()
    gitutils.setup_git_repo_if_needed(is_test_mode)
    snapshots_repo_name = gitutils.get_repo_name(is_test_mode)
    SpotifySnapshotOutputManager.initialize(snapshots_repo_name)

    # If no specific backup option is selected, default to backing up everything
    if not any([backup_all, backup_liked_songs, backup_saved_albums, backup_playlists]):
        backup_all = True

    if backup_all or backup_liked_songs:
        spotify.write_liked_songs_to_git_repo(sp_client, snapshots_repo_name)

    if backup_all or backup_saved_albums:
        spotify.write_saved_albums_to_git_repo(sp_client, snapshots_repo_name)

    if backup_all or backup_playlists:
        spotify.write_playlists_to_git_repo(sp_client, snapshots_repo_name)

    if no_commit:
        rprint(
            "[yellow]Skipping committing changes, leaving in repo dirty for manual committing later[/yellow]"
        )
    else:
        gitutils.commit_files(is_test_mode)


if __name__ == "__main__":
    main()
