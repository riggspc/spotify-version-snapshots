import click

from spotify_version_snapshots import gitutils, spotify, outputfileutils

API_REQUEST_SLEEP_TIME_SEC = 0.5
# For albums, playlists, etc - the Spotify API has a (current) max of 50 things
# it can fetch at a time
API_REQUEST_LIMIT = 50


# General TODOs:
# - Error handling
# - Refactor fetch code to share more logic
# - Turn print statements into real (and higher quality) logging
# - General things to support podcasts instead of just music tracks (default
#   for most of these API requests/return data)
# - If a playlist does not have a name then rename it something (eg. "Deleted playlist")
#   or try to find what it used to be called (using ID)
# - If a playlist renamed or deleted (renamed to empty string), do a move from the old tracks file to the new
#   one rather than just adding a new one and not touching the old one
# - Make num songs across playlists in commit message accurate when a new playlist
#   is subscribed to (it counts the first line of the TSV as a track)
# - Might be more accurate to read from the files when calculating initial commit
#   stats, as opposed to looking at the added lines from the commit...might not
#   be worth it
# - make script arg to push to remote repo, if configured
# - Handle the "no changes" situation (don't commit? better error? empty commit?)
# - Make things (like utils) into real classes
# - Better names for files (especially this one)
# - Added/removed playlists in commit message is wrong (adding/removing tracks
#   makes it look like both an addition and removal). Need to probably look at
#   playlist IDs to be accurate in that


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
def main(
    prod_run,
    no_commit,
    backup_all,
    backup_liked_songs,
    backup_saved_albums,
    backup_playlists,
    pretty_print,
):
    """Fetch and snapshot Spotify library data."""

    # Handle pretty print request if specified
    if pretty_print:
        outputfileutils.pretty_print_tsv_table(pretty_print)
        return

    is_test_mode = not prod_run

    if is_test_mode:
        print("Running in test mode...")
    else:
        print("*** RUNNING IN PROD MODE ***")

    sp_client = spotify.create_spotify_client()
    gitutils.setup_git_repo_if_needed(is_test_mode)
    snapshots_repo_name = gitutils.get_repo_name(is_test_mode)

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
        print("Skipping committing changes, leaving in repo")
    else:
        print("Committing changes...")
        gitutils.commit_files(is_test_mode)
        print("Changes committed. All done!")


if __name__ == "__main__":
    main()
