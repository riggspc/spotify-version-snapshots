import time
from spotipy import Spotify
import spotipy
from os import getenv
from pathlib import Path

API_REQUEST_SLEEP_TIME_SEC = 0.5
# For albums, playlists, etc - the Spotify API has a (current) max of 50 things
# it can fetch at a time
API_REQUEST_LIMIT = 50

def get_saved_tracks(sp_client: Spotify, test_mode: bool = False) -> dict:
    saved_tracks = {}
    results = sp_client.current_user_saved_tracks(API_REQUEST_LIMIT)

    while True:
        result_items = results["items"]
        print(
            f"Fetched {len(result_items)} tracks (pg {results['offset'] // API_REQUEST_LIMIT})"
        )

        for item in result_items:
            saved_tracks[item["track"]["id"]] = item

        if results["next"]:
            time.sleep(API_REQUEST_SLEEP_TIME_SEC)
            results = sp_client.next(results)
        else:
            break

        if test_mode:
            break

    return saved_tracks

def get_tracks_from_playlist(sp_client: Spotify, playlist, test_mode: bool = False) -> dict:
    playlist_tracks = {}
    offset = 0
    
    # TODO: This does not fetch all the tracks from the playlist. It stops at 50

    while True:
        results = sp_client.playlist_tracks(
            playlist_id=playlist["id"],
            fields="items(added_at,added_by(id),track(name,id,artists(name),album(name,id))),next,offset,total",
            limit=API_REQUEST_LIMIT,
            offset=offset
        )
        
        result_items = results["items"]
        print(
            f"Fetched {len(result_items)} tracks from playlist {playlist['name']} "
            f"(pg {offset // API_REQUEST_LIMIT}, total: {results['total']})"
        )

        for item in result_items:
            track = item["track"]
            if track is None:
                continue
            playlist_tracks[track["id"]] = item

        if not results["items"]:
            break
            
        offset += API_REQUEST_LIMIT
        
        if test_mode:
            break
            
        time.sleep(API_REQUEST_SLEEP_TIME_SEC)

    return playlist_tracks

def get_saved_albums(sp_client: Spotify, test_mode: bool = False) -> dict:
    saved_albums = {}
    results = sp_client.current_user_saved_albums(API_REQUEST_LIMIT)

    while True:
        result_items = results["items"]
        print(
            f"Fetched {len(result_items)} albums (pg {results['offset'] // API_REQUEST_LIMIT})"
        )

        for item in result_items:
            saved_albums[item["album"]["id"]] = item

        if results["next"]:
            time.sleep(API_REQUEST_SLEEP_TIME_SEC)
            results = sp_client.next(results)
        else:
            break

        if test_mode:
            break

    return saved_albums

def get_playlists(sp_client: Spotify, test_mode: bool = False) -> dict:
    saved_playlists = {}
    results = sp_client.current_user_playlists(API_REQUEST_LIMIT)

    while True:
        result_items = results["items"]
        print(
            f"Fetched {len(result_items)} playlists (pg {results['offset'] // API_REQUEST_LIMIT})"
        )

        for item in result_items:
            saved_playlists[item["id"]] = item

        if results["next"]:
            time.sleep(API_REQUEST_SLEEP_TIME_SEC)
            results = sp_client.next(results)
        else:
            break

        if test_mode:
            break

    return saved_playlists

def create_spotify_client(client_id: str, client_secret: str) -> spotipy.Spotify:
    """Create and return an authenticated Spotify client.
    
    Args:
        client_id: Spotify API client ID
        client_secret: Spotify API client secret
        
    Returns:
        An authenticated Spotify client instance
    """
    base_cache_path = Path(getenv("XDG_CACHE_HOME", Path.home() / ".cache"))
    cache_path = base_cache_path / "spotify-backup/.auth_cache"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_handler = spotipy.cache_handler.CacheFileHandler(cache_path=str(cache_path))

    return spotipy.Spotify(
        auth_manager=spotipy.oauth2.SpotifyOAuth(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri="http://localhost:8000/callback",
            cache_handler=cache_handler,
            scope=[
                "user-library-read",
                "playlist-read-private",
                "playlist-read-collaborative",
            ],
        )
    ) 