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


def get_saved_tracks(sp_client: Spotify) -> dict:
    # Can only get 50 tracks at a time, iterate through the library until we've
    # got them all
    limit = 50
    offset = 0
    saved_tracks = {}
    while True:
        results = sp_client.current_user_saved_tracks(limit, offset)
        result_items = results["items"]
        print(f"Fetched {len(result_items)} tracks")

        # result_items is a list. Add them to the saved_tracks dict by track ID
        # to prevent duplicated tracks appearing if the library was added to
        # while being fetched
        for item in result_items:
            saved_tracks[item["track"]["id"]] = item

        if len(result_items) is not limit:
            break
        offset += limit

        # Prevent rate limiting. Maybe not needed, playing it safe for now
        time.sleep(API_REQUEST_SLEEP_TIME_SEC)

    return saved_tracks


def get_saved_albums(sp_client: Spotify) -> dict:
    # Can only get 50 albums at a time, iterate through the library until we've
    # got them all
    limit = 50
    offset = 0
    saved_albums = {}
    while True:
        results = sp_client.current_user_saved_albums(limit, offset)
        result_items = results["items"]
        print(f"Fetched {len(result_items)} albums")

        # result_items is a list. Add them to the saved_albums dict by album ID
        # to prevent duplicated albums appearing if the library was added to
        # while being fetched
        for item in result_items:
            saved_albums[item["album"]["id"]] = item

        if len(result_items) is not limit:
            break
        offset += limit

        # Prevent rate limiting. Maybe not needed, playing it safe for now
        time.sleep(API_REQUEST_SLEEP_TIME_SEC)

    return saved_albums


def get_playlists(sp_client: Spotify) -> dict:
    # Can only get 50 playlists at a time, iterate through the library until
    # we've got them all
    limit = 50
    offset = 0
    saved_playlists = {}
    while True:
        results = sp_client.current_user_playlists(limit, offset)
        result_items = results["items"]
        print(f"Fetched {len(result_items)} playlists")

        # result_items is a list. Add them to the saved_playlists dict by album
        # ID to prevent duplicated playlists appearing if new playlists were
        # made while being fetched
        for item in result_items:
            saved_playlists[item["id"]] = item

        if len(result_items) is not limit:
            break
        offset += limit

        # Prevent rate limiting. Maybe not needed, playing it safe for now
        time.sleep(API_REQUEST_SLEEP_TIME_SEC)

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
        output_filename=f"{gitutils.SNAPSHOTS_REPO_NAME}/saved_tracks",
    )
    print(f"Wrote {len(saved_tracks)} tracks to file")

    saved_albums = get_saved_albums(sp_client)
    outputfileutils.write_to_file(
        data=saved_albums,
        sort_lambda=lambda item: item["added_at"],
        header_row=outputfileutils.ALBUM_HEADER_ROW,
        item_to_row_lambda=outputfileutils.album_to_row,
        output_filename=f"{gitutils.SNAPSHOTS_REPO_NAME}/saved_albums",
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
        output_filename=f"{gitutils.SNAPSHOTS_REPO_NAME}/playlists",
    )

    gitutils.commit_files()


if __name__ == "__main__":
    main()
