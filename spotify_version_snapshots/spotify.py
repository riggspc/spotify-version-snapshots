from spotify_version_snapshots import outputfileutils, constants, credentials
import spotipy
import time
from os import getenv, chmod
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional, Dict
from rich import print as rprint

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


@dataclass
class SpotifyAlbum:
    name: str
    id: str


@dataclass
class SpotifyArtist:
    name: str


@dataclass
class SpotifyTrack:
    album: SpotifyAlbum
    artists: List[SpotifyArtist]
    name: str
    id: str


@dataclass
class SpotifyAddedBy:
    id: str


@dataclass
class SpotifyPlaylistTrackItem:
    track: SpotifyTrack
    added_by: SpotifyAddedBy
    added_at: str


@dataclass
class SpotifyPlaylistTracksResponse:
    items: List[SpotifyPlaylistTrackItem]
    next: Optional[str]
    total: int


@dataclass
class SpotifyPlaylistsResponse:
    items: List[SpotifyPlaylist]
    next: Optional[str]
    total: int


@dataclass
class DeletedPlaylist:
    name: str
    id: str


#####
# Spotify Operations
#####

API_REQUEST_SLEEP_TIME_SEC = 0.5
# For albums, playlists, etc - the Spotify API has a (current) max of 50 things
# it can fetch at a time
API_REQUEST_LIMIT = 50


def _fetch_paginated_tracks(
    sp_client: spotipy.Spotify,
    initial_results: SpotifyPlaylistTracksResponse,
) -> dict:
    """Helper function to handle paginated track fetching from Spotify API.

    Args:
        sp_client: Authenticated Spotify client
        initial_results: First page of results from API
        test_mode: If True, only fetch first page

    Returns:
        Dictionary of track_id -> track_item
    """
    tracks_dict = {}
    total_tracks_fetched = 0
    results = initial_results
    skipped_tracks = []

    while True:
        result_items: List[SpotifyPlaylistTrackItem] = results["items"]
        total_tracks_fetched += len(result_items)
        rprint(
            f"[green]Fetched[/green] {total_tracks_fetched} / {results['total']} [green]tracks[/green]"
        )

        for item in result_items:
            track = item.get("track")
            if track is None:
                skipped_tracks.append(item)
                continue
            tracks_dict[track["id"]] = item

        if results["next"]:
            time.sleep(API_REQUEST_SLEEP_TIME_SEC)
            results = sp_client.next(results)
        else:
            break

    if skipped_tracks:
        rprint(f"[red]Skipped[/red] {len(skipped_tracks)} tracks")
        for track in skipped_tracks:
            rprint(f"[red]  • {track}[/red]")
    return tracks_dict


def get_liked_songs(sp_client: spotipy.Spotify) -> dict:
    rprint("[blue]Getting liked songs[/blue]...")
    initial_results = sp_client.current_user_saved_tracks(API_REQUEST_LIMIT)
    liked_songs = _fetch_paginated_tracks(sp_client, initial_results)
    return liked_songs


def get_tracks_from_playlist(
    sp_client: spotipy.Spotify,
    playlist: SpotifyPlaylist,
) -> dict:
    rprint(
        f"[blue]Getting tracks from playlist[/blue] [green][bold]{playlist['name']}[/bold][/green]..."
    )
    initial_results = sp_client.playlist_tracks(
        playlist_id=playlist["id"],
        fields="items(added_at,added_by(id),track(name,id,artists(name),album(name,id))),next,total",
        limit=API_REQUEST_LIMIT,
    )
    return _fetch_paginated_tracks(sp_client, initial_results)


def get_saved_albums(sp_client: spotipy.Spotify) -> dict:
    saved_albums = {}
    results = sp_client.current_user_saved_albums(API_REQUEST_LIMIT)

    while True:
        result_items = results["items"]
        rprint(f"[green]Fetched[/green] {len(result_items)} [green]albums[/green]")

        for item in result_items:
            saved_albums[item["album"]["id"]] = item

        if results["next"]:
            time.sleep(API_REQUEST_SLEEP_TIME_SEC)
            results = sp_client.next(results)
        else:
            break

    return saved_albums


def get_playlists(sp_client: spotipy.Spotify) -> dict:
    saved_playlists = {}
    results: SpotifyPlaylistsResponse = sp_client.current_user_playlists(
        API_REQUEST_LIMIT
    )

    rprint(f"[green]Fetching[/green] {results['total']} [green]playlists[/green]...")

    while True:
        playlists: List[SpotifyPlaylist] = results["items"]
        rprint(f"[green]Fetched[/green] {len(playlists)} playlists")

        for playlist in playlists:
            saved_playlists[playlist["id"]] = playlist

        if results["next"]:
            time.sleep(API_REQUEST_SLEEP_TIME_SEC)
            results = sp_client.next(results)
        else:
            break

    return saved_playlists


def create_spotify_client() -> spotipy.Spotify:
    """Create and return an authenticated Spotify client.

    Args:
        client_id: Spotify API client ID
        client_secret: Spotify API client secret

    Returns:
        An authenticated Spotify client instance
    """
    client_id = credentials.get_required_env_var("SPOTIFY_BACKUP_CLIENT_ID")
    client_secret = credentials.get_required_env_var("SPOTIFY_BACKUP_CLIENT_SECRET")

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

    # Spotipy does not set the permissions on the cache file correctly, so we do it manually
    # I filed https://github.com/spotipy-dev/spotipy/security/advisories/GHSA-pwhh-q4h6-w599
    chmod(cache_path, 0o600)
    return client


#####
# Wrappers for use in main
#####


def get_playlist_file_name(
    snapshots_repo_name: Path, playlist: SpotifyPlaylist | DeletedPlaylist
) -> Path:
    """Generate the file path for a playlist's tracks file.

    Args:
        snapshots_repo_name: Base directory for snapshots
        playlist: Either a Spotify playlist dict or DeletedPlaylist object

    Returns:
        Path object for the playlist's tracks file
    """
    # Handle both dict and dataclass access patterns
    playlist_name = playlist["name"] if isinstance(playlist, dict) else playlist.name
    playlist_id = playlist["id"] if isinstance(playlist, dict) else playlist.id

    escaped_playlist_name = playlist_name.replace("/", "\u2215")
    return (
        snapshots_repo_name
        / Path("playlists")
        / Path(f"{escaped_playlist_name} ({playlist_id}).tsv")
    )


def write_liked_songs_to_git_repo(
    sp_client: spotipy.Spotify, snapshots_repo_name: Path
):
    liked_songs = get_liked_songs(sp_client)
    dest_file = snapshots_repo_name / FILENAMES["liked_songs"]
    outputfileutils.write_to_file(
        data=liked_songs,
        sort_lambda=lambda item: (item["added_at"], item["track"]["name"]),
        header_row=outputfileutils.TRACK_HEADER_ROW,
        item_to_row_lambda=outputfileutils.track_to_row,
        output_filename=dest_file,
    )
    rprint(
        f"[green]Wrote[/green] {len(liked_songs)} [green]liked songs to[/green] {dest_file}"
    )


def write_saved_albums_to_git_repo(
    sp_client: spotipy.Spotify, snapshots_repo_name: Path
):
    saved_albums = get_saved_albums(sp_client)
    dest_file = snapshots_repo_name / FILENAMES["albums"]
    outputfileutils.write_to_file(
        data=saved_albums,
        sort_lambda=lambda item: (item["added_at"], item["album"]["name"]),
        header_row=outputfileutils.ALBUM_HEADER_ROW,
        item_to_row_lambda=outputfileutils.album_to_row,
        output_filename=dest_file,
    )
    rprint(
        f"[green]Wrote[/green] {len(saved_albums)} [green]albums to[/green] {dest_file}"
    )


def write_playlists_to_git_repo(sp_client: spotipy.Spotify, snapshots_repo_name: Path):
    """
    Extracts a list of all playlists the user owns or is subscribed to, and writes them to a file. Then, for each playlist,
    it fetches all the tracks on the playlist and writes them to a separate file.
    """
    # Playlists are a bit more complicated. Start by fetching all playlists the # user owns or is subscribed to
    playlists = get_playlists(sp_client)
    # Eventually we'll fetch all the songs on those playlists and snapshot those too.
    # But for now, just list the playlists in the library
    # We will also use this file to track which playlists have been removed
    playlists_file = snapshots_repo_name / FILENAMES["playlists"]
    outputfileutils.write_to_file(
        data=playlists,
        # Sorting by id seems weird but this is to make sure order stays stable
        # even if a playlist is renamed etc
        sort_lambda=lambda item: item["id"],
        header_row=outputfileutils.PLAYLIST_HEADER_ROW,
        item_to_row_lambda=outputfileutils.playlist_to_row,
        output_filename=playlists_file,
    )

    # Keep track of skipped playlists
    skipped_playlists = []
    total_playlists_backed_up = 0

    # Snapshot the contents of each playlist too
    for playlist in playlists.values():
        playlist_tracks = get_tracks_from_playlist(sp_client, playlist)
        # If the playlist is empty, skip it and log a warning
        if not playlist_tracks:
            skipped_playlists.append(playlist["name"])
            continue
        playlist_tracks_file = get_playlist_file_name(snapshots_repo_name, playlist)
        outputfileutils.write_to_file(
            data=playlist_tracks,
            sort_lambda=lambda item: (item["added_at"], item["track"]["name"]),
            header_row=outputfileutils.TRACK_IN_PLAYLIST_HEADER_ROW,
            item_to_row_lambda=outputfileutils.playlist_track_to_row,
            # Note that the playlist name needs to have slashes replaced with
            # a Unicode character that looks just like a slash
            output_filename=playlist_tracks_file,
        )
        total_playlists_backed_up += 1

    # Print summary of skipped playlists with rich styling
    if skipped_playlists:
        rprint(f"\n[yellow]Skipped {len(skipped_playlists)} empty playlists:[/yellow]")
        for playlist_name in sorted(skipped_playlists):
            rprint(f"[red]  • {playlist_name}[/red]")

    rprint(
        f"[green]Successfully backed up[/green] {total_playlists_backed_up} playlists"
    )
