import spotipy
import time

from spotipy.oauth2 import SpotifyOAuth
from spotipy import Spotify
from credentials import CLIENT_ID, CLIENT_SECRET

API_REQUEST_SLEEP_TIME_SEC = 0.5

# General TODOs:
# - Error handling
# - Refactor fetch code to share more logic


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


def main():
    sp_client = spotipy.Spotify(
        auth_manager=SpotifyOAuth(
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            redirect_uri="http://localhost:8888/callback",
            scope="user-library-read",
        )
    )
    saved_tracks = get_saved_tracks(sp_client)
    print(len(saved_tracks))

    saved_albums = get_saved_albums(sp_client)
    print(len(saved_albums))


if __name__ == "__main__":
    main()
