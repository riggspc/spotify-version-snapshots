import spotipy
import time

import utils.gitutils as gitutils
import utils.outputfileutils as outputfileutils

from spotipy.oauth2 import SpotifyOAuth
from spotipy import Spotify
from credentials import CLIENT_ID, CLIENT_SECRET

API_REQUEST_SLEEP_TIME_SEC = 0.5

# General TODOs:
# - Error handling
# - Refactor fetch code to share more logic
# - Debug mode (limited fetching for quicker testing)
# - Turn print statements into real (and higher quality) logging
# - General things to support podcasts instead of just music tracks (default
#   for most of these API requests/return data)
# - Support for "added by" in playlist contents snapshot (not that hard)
#   in all of the fetch methods (similar to example here - https://github.com/plamere/spotipy/blob/master/examples/user_playlists_contents.py)
# - Make commit message for the snapshots be meaningful
# - Params/args to this script to determine if the script commits changed
#   snapshot files, pushes to a remote repo, and maybe other configurables


def get_saved_tracks(sp_client: Spotify) -> dict:
    # Can only get 50 tracks at a time, iterate through the library until we've
    # got them all
    limit = 50
    saved_tracks = {}
    results = sp_client.current_user_saved_tracks(limit)

    while True:
        result_items = results["items"]
        print(f"Fetched {len(result_items)} tracks")

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

    return saved_tracks


def get_tracks_from_playlist(sp_client: Spotify, playlist) -> dict:
    # Can only get 50 tracks at a time, iterate through the playlist until
    # we've got them all
    limit = 50
    playlist_tracks = {}
    results = sp_client.playlist_tracks(
        playlist_id=playlist["id"],
        fields="items(added_at,added_by.id,track(name,id,artists(name),album(name,id))),next",
        limit=limit,
    )

    while True:
        result_items = results["items"]
        print(f"Fetched {len(result_items)} tracks from playlist {playlist['name']}")

        # result_items is a list. Add them to the playlist_tracks dict by track ID
        # to prevent duplicated tracks appearing if the playlist was added to
        # while being fetched
        for item in result_items:
            playlist_tracks[item["track"]["id"]] = item

        if results["next"]:
            # Prevent rate limiting. Maybe not needed, playing it safe for now
            time.sleep(API_REQUEST_SLEEP_TIME_SEC)
            results = sp_client.next(results)
        else:
            break

    return playlist_tracks


def get_saved_albums(sp_client: Spotify) -> dict:
    # Can only get 50 albums at a time, iterate through the library until we've
    # got them all
    limit = 50
    saved_albums = {}
    results = sp_client.current_user_saved_albums(limit)

    while True:
        result_items = results["items"]
        print(f"Fetched {len(result_items)} albums")

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

    return saved_albums


def get_playlists(sp_client: Spotify) -> dict:
    # Can only get 50 playlists at a time, iterate through the library until
    # we've got them all
    limit = 50
    saved_playlists = {}
    results = sp_client.current_user_playlists(limit)

    while True:
        result_items = results["items"]
        print(f"Fetched {len(result_items)} playlists")

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

    return saved_playlists


def main():
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

    gitutils.setup_git_repo_if_needed()

    saved_tracks = get_saved_tracks(sp_client)
    outputfileutils.write_to_file(
        data=saved_tracks,
        sort_lambda=lambda item: item["added_at"],
        header_row=outputfileutils.TRACK_HEADER_ROW,
        item_to_row_lambda=outputfileutils.track_to_row,
        output_filename=f"{gitutils.SNAPSHOTS_REPO_NAME}/saved_tracks.tsv",
    )
    print(f"Wrote {len(saved_tracks)} tracks to file")

    saved_albums = get_saved_albums(sp_client)
    outputfileutils.write_to_file(
        data=saved_albums,
        sort_lambda=lambda item: item["added_at"],
        header_row=outputfileutils.ALBUM_HEADER_ROW,
        item_to_row_lambda=outputfileutils.album_to_row,
        output_filename=f"{gitutils.SNAPSHOTS_REPO_NAME}/saved_albums.tsv",
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
        output_filename=f"{gitutils.SNAPSHOTS_REPO_NAME}/playlists.tsv",
    )

    # Snapshot the contents of each playlist too
    for playlist in playlists.values():
        playlist_tracks = get_tracks_from_playlist(sp_client, playlist)
        outputfileutils.write_to_file(
            data=playlist_tracks,
            sort_lambda=lambda item: item["added_at"],
            header_row=outputfileutils.TRACK_HEADER_ROW,
            item_to_row_lambda=outputfileutils.track_to_row,
            output_filename=f"{gitutils.SNAPSHOTS_REPO_NAME}/playlists/{playlist['name']} ({playlist['id']}).tsv",
        )

    gitutils.commit_files()


if __name__ == "__main__":
    main()
