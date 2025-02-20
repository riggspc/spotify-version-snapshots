from spotify_version_snapshots import outputfileutils, constants
import spotipy
import time
from os import getenv, chmod
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional, Dict
from rich import print as rprint
from rich.style import Style

FILENAMES = constants.FILENAMES


@dataclass
class SpotifyImage:
    height: Optional[int]
    width: Optional[int]
    url: str


@dataclass
class SpotifyUser:
    display_name: str
    external_urls: Dict[str, str]
    href: str
    id: str
    type: str
    uri: str


@dataclass
class SpotifyTracks:
    href: str
    total: int


@dataclass
class SpotifyPlaylist:
    collaborative: bool
    description: str
    external_urls: Dict[str, str]
    href: str
    id: str
    images: List[SpotifyImage]
    name: str
    owner: SpotifyUser
    primary_color: Optional[str]
    public: bool
    snapshot_id: str
    tracks: SpotifyTracks
    type: str
    uri: str


#####
# Spotify Operations
#####

API_REQUEST_SLEEP_TIME_SEC = 0.5
# For albums, playlists, etc - the Spotify API has a (current) max of 50 things
# it can fetch at a time
API_REQUEST_LIMIT = 50


def get_liked_songs(sp_client: spotipy.Spotify) -> dict:
    liked_songs = {}
    results = sp_client.current_user_saved_tracks(API_REQUEST_LIMIT)
    total_count = 0
    print("Getting liked songs...")

    while True:
        result_items = results["items"]
        total_count += len(result_items)
        print(
            f"Fetched {len(result_items)} more tracks (pg {results['offset'] // API_REQUEST_LIMIT})"
        )

        for item in result_items:
            liked_songs[item["track"]["id"]] = item

        if results["next"]:
            time.sleep(API_REQUEST_SLEEP_TIME_SEC)
            results = sp_client.next(results)
        else:
            break

    print(f"Fetched {total_count} liked songs")

    return liked_songs


def get_tracks_from_playlist(
    sp_client: spotipy.Spotify, playlist, test_mode: bool = False
) -> dict:
    playlist_tracks = {}
    results = sp_client.playlist_tracks(
        playlist_id=playlist["id"],
        fields="items(added_at,added_by(id),track(name,id,artists(name),album(name,id))),next,total",
        limit=API_REQUEST_LIMIT,
    )

    while True:
        result_items = results["items"]
        print(
            f"Fetched {len(result_items)} tracks from playlist {playlist['name']} "
            f"(pg {results.get('offset', 0) // API_REQUEST_LIMIT}, total: {results['total']})"
        )

        for item in result_items:
            track = item["track"]
            if track is None:
                continue
            playlist_tracks[track["id"]] = item

        if results["next"]:
            time.sleep(API_REQUEST_SLEEP_TIME_SEC)
            results = sp_client.next(results)
        else:
            break

        if test_mode:
            break

    return playlist_tracks


def get_saved_albums(sp_client: spotipy.Spotify, test_mode: bool = False) -> dict:
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


def get_playlists(sp_client: spotipy.Spotify, test_mode: bool = False) -> dict:
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

    client = spotipy.Spotify(
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

    # Spotipy does not set the permissions on the cache file correctly, so we need to do it manually
    chmod(cache_path, 0o600)
    return client


#####
# Wrappers for use in main
#####


def write_liked_songs_to_git_repo(sp_client: spotipy.Spotify, snapshots_repo_name: str):
    saved_tracks = get_liked_songs(sp_client)
    outputfileutils.write_to_file(
        data=saved_tracks,
        sort_lambda=lambda item: (item["added_at"], item["track"]["name"]),
        header_row=outputfileutils.TRACK_HEADER_ROW,
        item_to_row_lambda=outputfileutils.track_to_row,
        output_filename=f"{snapshots_repo_name}/{FILENAMES['tracks']}",
    )
    print(f"Wrote {len(saved_tracks)} tracks to file")


def write_saved_albums_to_git_repo(
    sp_client: spotipy.Spotify, snapshots_repo_name: str
):
    saved_albums = get_saved_albums(sp_client)
    outputfileutils.write_to_file(
        data=saved_albums,
        sort_lambda=lambda item: (item["added_at"], item["album"]["name"]),
        header_row=outputfileutils.ALBUM_HEADER_ROW,
        item_to_row_lambda=outputfileutils.album_to_row,
        output_filename=f"{snapshots_repo_name}/{FILENAMES['albums']}",
    )
    print(f"Wrote {len(saved_albums)} albums to file")


def write_playlists_to_git_repo(sp_client: spotipy.Spotify, snapshots_repo_name: str):
    # Playlists are a bit more complicated. Start by fetching all playlists the # user owns or is subscribed to
    playlists = get_playlists(sp_client)
    # Eventually we'll fetch all the songs on those playlists and snapshot those too.
    # But for now, just list the playlists in the library
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
            output_filename=f"{snapshots_repo_name}/{FILENAMES['playlists']}/{escaped_playlist_name} ({playlist['id']}).tsv",
        )
