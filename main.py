import spotipy
import time
import git
import csv

from spotipy.oauth2 import SpotifyOAuth
from spotipy import Spotify
from git import NoSuchPathError
from typing import Callable
from credentials import CLIENT_ID, CLIENT_SECRET

API_REQUEST_SLEEP_TIME_SEC = 0.5
SNAPSHOTS_REPO_NAME = "spotify-snapshots-repo"

# General TODOs:
# - Error handling
# - Refactor fetch code to share more logic
# - Debug mode (limited fetching for quicker testing)
# - Turn print statements into real (and higher quality) logging


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
        # to prevent duplicated tracks appearing if the library was dded to
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
        # to prevent duplicated albums appearing if the library was dded to
        # while being fetched
        for item in result_items:
            saved_albums[item["album"]["id"]] = item

        if len(result_items) is not limit:
            break
        offset += limit

        # Prevent rate limiting. Maybe not needed, playing it safe for now
        time.sleep(API_REQUEST_SLEEP_TIME_SEC)

    return saved_albums


# Takes in a dict of dicts (data), sorts into a list based on sort_key for each
# dict, and then outputs each item to the file specified. Overwrites any such
# existing file.
def output_to_file(
    data: dict,
    sort_lambda: Callable,
    item_to_row_lambda: Callable,
    header_row: list[str],
    output_filename: str,
) -> None:
    sorted_list = sorted(list(data.values()), key=sort_lambda)
    output_rows = [header_row]
    for item in sorted_list:
        output_rows.append(item_to_row_lambda(item))

    with open(output_filename, "wt") as out_file:
        tsv_writer = csv.writer(out_file, delimiter="\t")
        tsv_writer.writerows(output_rows)


def setup_git_repo_if_needed() -> None:
    try:
        my_repo = git.Repo(SNAPSHOTS_REPO_NAME)
        print("Found existing repo")
    except NoSuchPathError as e:
        print("No repo, making a new one")
        new_repo = git.Repo.init(SNAPSHOTS_REPO_NAME)


# Assumes repo already exists etc
def commit_files() -> None:
    repo = git.Repo(SNAPSHOTS_REPO_NAME)
    repo.index.add(items="*")
    # TODO: make this message something meaningful
    repo.index.commit('test commit')



def track_to_row(item) -> list:
    track_obj = item["track"]
    return [
        track_obj["name"],
        ", ".join(map(lambda artist: artist["name"], track_obj["artists"])),
        track_obj["album"]["name"],
        item["added_at"],
        track_obj["id"],
    ]


def album_to_row(item) -> list:
    album_obj = item["album"]
    return [
        album_obj["name"],
        ", ".join(map(lambda artist: artist["name"], album_obj["artists"])),
        item["added_at"],
        album_obj["id"],
    ]


def main():
    sp_client = spotipy.Spotify(
        auth_manager=SpotifyOAuth(
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            redirect_uri="http://localhost:8888/callback",
            scope="user-library-read",
        )
    )

    setup_git_repo_if_needed()

    saved_tracks = get_saved_tracks(sp_client)
    output_to_file(
        data=saved_tracks,
        sort_lambda=lambda item: item["added_at"],
        header_row=["TRACK NAME", "TRACK ARTIST(S)", "ALBUM", "DATE ADDED", "TRACK ID"],
        item_to_row_lambda=track_to_row,
        output_filename=f"{SNAPSHOTS_REPO_NAME}/saved_tracks",
    )
    print(f"Wrote {len(saved_tracks)} tracks to file")

    saved_albums = get_saved_albums(sp_client)
    output_to_file(
        data=saved_albums,
        sort_lambda=lambda item: item["added_at"],
        header_row=["ALBUM NAME", "ALBUM ARTIST(S)", "DATE ADDED", "ALBUM ID"],
        item_to_row_lambda=album_to_row,
        output_filename=f"{SNAPSHOTS_REPO_NAME}/saved_albums",
    )
    print(f"Wrote {len(saved_albums)} albums to file")

    commit_files()


if __name__ == "__main__":
    main()
