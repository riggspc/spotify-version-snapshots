import time
import click

from spotify_version_snapshots import gitutils, outputfileutils, credentials, constants, spotify


CLIENT_ID = credentials.CLIENT_ID
CLIENT_SECRET = credentials.CLIENT_SECRET
FILENAMES = constants.FILENAMES

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
    '-p', '--prod-run',
    is_flag=True,
    default=False,
    help='Runs the "real" version of the script, fetching everything and writing to the "real" snapshots repo instead of a test one.'
)
@click.option(
    '-n', '--no-commit',
    is_flag=True,
    default=False,
    help='When present, will run the entire script but not commit the results, leaving the repo dirty for manual committing later.'
)
def main(prod_run, no_commit):
    """Fetch and snapshot Spotify library data."""
    is_test_mode = not prod_run

    if is_test_mode:
        print("Running in test mode...")
    else:
        print("*** RUNNING IN PROD MODE ***")

    sp_client = spotify.create_spotify_client(CLIENT_ID, CLIENT_SECRET)

    gitutils.setup_git_repo_if_needed(is_test_mode)
    snapshots_repo_name = gitutils.get_repo_name(is_test_mode)

    saved_tracks = spotify.get_saved_tracks(sp_client, is_test_mode)
    outputfileutils.write_to_file(
        data=saved_tracks,
        sort_lambda=lambda item: (item["added_at"], item["track"]["name"]),
        header_row=outputfileutils.TRACK_HEADER_ROW,
        item_to_row_lambda=outputfileutils.track_to_row,
        output_filename=f"{snapshots_repo_name}/{FILENAMES['tracks']}",
    )
    print(f"Wrote {len(saved_tracks)} tracks to file")

    saved_albums = spotify.get_saved_albums(sp_client, is_test_mode)
    outputfileutils.write_to_file(
        data=saved_albums,
        sort_lambda=lambda item: (item["added_at"], item["album"]["name"]),
        header_row=outputfileutils.ALBUM_HEADER_ROW,
        item_to_row_lambda=outputfileutils.album_to_row,
        output_filename=f"{snapshots_repo_name}/{FILENAMES['albums']}",
    )
    print(f"Wrote {len(saved_albums)} albums to file")

    # Playlists are a bit more complicated. Start by fetching all playlists the
    # user owns or is subscribed to
    playlists = spotify.get_playlists(sp_client, is_test_mode)
    # Eventually we'll fetch all the songs on those playlists and snapshot those
    # too. But for now, just list the playlists in the library
    outputfileutils.write_to_file(
        data=playlists,
        # Sorting by id seems weird but this is to make sure order stays stable
        # even if a playlist is renamed etc
        sort_lambda=lambda item: item["id"],
        header_row=outputfileutils.PLAYLIST_HEADER_ROW,
        item_to_row_lambda=outputfileutils.playlist_to_row,
        output_filename=f"{snapshots_repo_name}/{FILENAMES['playlists']}",
    )

    # Snapshot the contents of each playlist too
    for playlist in playlists.values():
        playlist_tracks = spotify.get_tracks_from_playlist(sp_client, playlist, is_test_mode)
        escaped_playlist_name = playlist["name"].replace("/", "\u2215")
        outputfileutils.write_to_file(
            data=playlist_tracks,
            sort_lambda=lambda item: (item["added_at"], item["track"]["name"]),
            header_row=outputfileutils.TRACK_IN_PLAYLIST_HEADER_ROW,
            item_to_row_lambda=outputfileutils.playlist_track_to_row,
            # Note that the playlist name needs to have slashes replaced with
            # a Unicode character that looks just like a slash
            output_filename=f"{snapshots_repo_name}/playlists/{escaped_playlist_name} ({playlist['id']}).tsv",
        )

    if no_commit:
        print("Skipping committing changes, leaving in repo")
    else:
        print("Committing changes...")
        gitutils.commit_files(is_test_mode)
        print("Changes committed. All done!")


if __name__ == "__main__":
    main() 
