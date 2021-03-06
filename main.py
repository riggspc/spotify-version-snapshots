import spotipy
import time

import utils.gitutils as gitutils
import utils.outputfileutils as outputfileutils

from spotipy.oauth2 import SpotifyOAuth
from spotipy import Spotify
from credentials import CLIENT_ID, CLIENT_SECRET
from optparse import OptionParser

API_REQUEST_SLEEP_TIME_SEC = 0.5
# For albums, playlists, etc - the Spotify API has a (current) max of 50 things
# it can fetch at a time
API_REQUEST_LIMIT = 50
FILENAMES = {
    "tracks": "saved_tracks.tsv",
    "albums": "saved_albums.tsv",
    "playlists": "playlists.tsv",
}

test_mode = True


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


def is_test_mode() -> bool:
    return test_mode


def get_saved_tracks(sp_client: Spotify) -> dict:
    saved_tracks = {}
    results = sp_client.current_user_saved_tracks(API_REQUEST_LIMIT)

    while True:
        result_items = results["items"]
        print(
            f"Fetched {len(result_items)} tracks (pg {results['offset'] // API_REQUEST_LIMIT})"
        )

        # result_items is a list. Add them to the saved_tracks dict by track ID
        # to prevent duplicated tracks appearing if the library was added to
        # while being fetched
        for item in result_items:
            saved_tracks[item["track"]["id"]] = item

        if results["next"]:
            # Prevent rate limiting. Maybe not needed, playing it safe for now
            time.sleep(API_REQUEST_SLEEP_TIME_SEC)
            results = sp_client.next(results)
        else:
            break

        if is_test_mode():
            break

    return saved_tracks


def get_tracks_from_playlist(sp_client: Spotify, playlist) -> dict:
    playlist_tracks = {}
    results = sp_client.playlist_tracks(
        playlist_id=playlist["id"],
        fields="items(added_at,added_by(id),track(name,id,artists(name),album(name,id))),next,offset",
        limit=API_REQUEST_LIMIT,
    )

    while True:
        result_items = results["items"]
        print(
            f"Fetched {len(result_items)} tracks from playlist {playlist['name']} (pg {results['offset'] // API_REQUEST_LIMIT})"
        )

        # result_items is a list. Add them to the playlist_tracks dict by track ID
        # to prevent duplicated tracks appearing if the playlist was added to
        # while being fetched
        for item in result_items:
            track = item["track"]
            if track is None:
                # Not sure why this happens but it can (see KEXP Song Of The
                # Day 2021 playlist, id 6kImtfS73NEoA0CKe7Z4q4)
                continue
            playlist_tracks[track["id"]] = item

        if results["next"]:
            # Prevent rate limiting. Maybe not needed, playing it safe for now
            time.sleep(API_REQUEST_SLEEP_TIME_SEC)
            results = sp_client.next(results)
        else:
            break

        if is_test_mode():
            break

    return playlist_tracks


def get_saved_albums(sp_client: Spotify) -> dict:
    saved_albums = {}
    results = sp_client.current_user_saved_albums(API_REQUEST_LIMIT)

    while True:
        result_items = results["items"]
        print(
            f"Fetched {len(result_items)} albums (pg {results['offset'] // API_REQUEST_LIMIT})"
        )

        # result_items is a list. Add them to the saved_albums dict by album ID
        # to prevent duplicated albums appearing if the library was added to
        # while being fetched
        for item in result_items:
            saved_albums[item["album"]["id"]] = item

        if results["next"]:
            # Prevent rate limiting. Maybe not needed, playing it safe for now
            time.sleep(API_REQUEST_SLEEP_TIME_SEC)
            results = sp_client.next(results)
        else:
            break

        if is_test_mode():
            break

    return saved_albums


def get_playlists(sp_client: Spotify) -> dict:
    saved_playlists = {}
    results = sp_client.current_user_playlists(API_REQUEST_LIMIT)

    while True:
        result_items = results["items"]
        print(
            f"Fetched {len(result_items)} playlists (pg {results['offset'] // API_REQUEST_LIMIT})"
        )

        # result_items is a list. Add them to the saved_playlists dict by album
        # ID to prevent duplicated playlists appearing if new playlists were
        # made while being fetched
        for item in result_items:
            saved_playlists[item["id"]] = item

        if results["next"]:
            # Prevent rate limiting. Maybe not needed, playing it safe for now
            time.sleep(API_REQUEST_SLEEP_TIME_SEC)
            results = sp_client.next(results)
        else:
            break

        if is_test_mode():
            break

    return saved_playlists


def main():
    parser = OptionParser()
    parser.add_option(
        "-p",
        "--prod-run",
        action="store_true",
        default=False,
        dest="prodrun",
        help="runs the 'real' version of the script, fetching everything and "
        "writing to the 'real' snapshots repo instead of a test one",
    )
    parser.add_option(
        "-n",
        "--no-commit",
        action="store_true",
        dest="nocommit",
        help="when present, will run the entire script but not commit the "
        "results, leaving the repo dirty for manual committing later",
    )
    (options, args) = parser.parse_args()

    global test_mode
    test_mode = not options.prodrun

    if is_test_mode():
        print("Running in test mode...")
    else:
        print("*** RUNNING IN PROD MODE ***")

    sp_client = spotipy.Spotify(
        auth_manager=SpotifyOAuth(
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            redirect_uri="http://localhost:8888/callback",
            scope=[
                "user-library-read",
                "playlist-read-private",
                "playlist-read-collaborative",
            ],
        )
    )

    gitutils.setup_git_repo_if_needed(is_test_mode())
    snapshots_repo_name = gitutils.get_repo_name(is_test_mode())

    saved_tracks = get_saved_tracks(sp_client)
    outputfileutils.write_to_file(
        data=saved_tracks,
        sort_lambda=lambda item: (item["added_at"], item["track"]["name"]),
        header_row=outputfileutils.TRACK_HEADER_ROW,
        item_to_row_lambda=outputfileutils.track_to_row,
        output_filename=f"{snapshots_repo_name}/{FILENAMES['tracks']}",
    )
    print(f"Wrote {len(saved_tracks)} tracks to file")

    saved_albums = get_saved_albums(sp_client)
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
    playlists = get_playlists(sp_client)
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
        playlist_tracks = get_tracks_from_playlist(sp_client, playlist)
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

    if options.nocommit:
        print("Skipping committing changes, leaving in repo")
    else:
        print("Committing changes...")
        gitutils.commit_files(is_test_mode())
        print("Changes committed. All done!")


if __name__ == "__main__":
    main()
