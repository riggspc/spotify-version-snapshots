import time
from os import chmod, getenv
from pathlib import Path

import requests
import spotipy

from spotify_snapshot import outputfileutils
from spotify_snapshot.logging import get_colorized_logger
from spotify_snapshot.spotify_datatypes import (
    DeletedPlaylist,
    SpotifyPlaylist,
    SpotifyPlaylistsResponse,
    SpotifyPlaylistTrackItem,
    SpotifyPlaylistTracksResponse,
)
from spotify_snapshot.spotify_snapshot_output_manager import (
    SpotifySnapshotOutputManager,
)
from spotify_snapshot.exceptions import InvalidSpotifyCredentialsError
from dataclasses import dataclass
import keyring
from rich.prompt import Prompt


#####
# Spotify Operations
#####

API_REQUEST_SLEEP_TIME_SEC = 0.5
# For albums, playlists, etc - the Spotify API has a (current) max of 50 things
# it can fetch at a time
API_REQUEST_LIMIT = 50




@dataclass
class SpotifyCredentials:
    """Container for Spotify API credentials."""

    client_id: str
    client_secret: str


class SpotifyCredentialsManager:
    """Manager for Spotify API credentials."""

    SERVICE_NAME = "spotify-snapshot"

    @classmethod
    def get_credentials(cls) -> SpotifyCredentials:
        """Get Spotify API credentials from keyring or environment."""
        # Try to get from keyring
        client_id = keyring.get_password(SpotifyCredentialsManager.SERVICE_NAME, "client_id")
        client_secret = keyring.get_password(SpotifyCredentialsManager.SERVICE_NAME, "client_secret")

        # If either credential is missing, prompt user
        if not client_id or not client_secret:
            return cls.prompt_and_store_credentials()

        return SpotifyCredentials(client_id, client_secret)

    @classmethod
    def prompt_and_store_credentials(cls) -> SpotifyCredentials:
        """Prompt user for credentials and store them."""
        logger = get_colorized_logger()
        logger.info("Please enter your Spotify API credentials.")
        logger.info("To get these credentials:")
        logger.info("1. Go to https://developer.spotify.com/dashboard")
        logger.info("2. Create a new application")
        logger.info("3. Set the callback URL to http://localhost:8000/callback")
        logger.info("4. Copy the Client ID and Client Secret\n")

        client_id = Prompt.ask("Enter your Spotify Client ID")
        client_secret = Prompt.ask("Enter your Spotify Client Secret", password=True)

        # Store credentials
        SpotifyCredentialsManager.store_credentials(client_id, client_secret)
        return SpotifyCredentials(client_id, client_secret)

    @classmethod
    def store_credentials(cls, client_id: str, client_secret: str) -> None:
        """Store Spotify API credentials in system keyring."""
        logger = get_colorized_logger()
        logger.info("Storing credentials in keyring...")
        keyring.set_password(SpotifyCredentialsManager.SERVICE_NAME, "client_id", client_id)
        keyring.set_password(SpotifyCredentialsManager.SERVICE_NAME, "client_secret", client_secret)
        logger.info("<green>Credentials stored successfully!</green>")

    @classmethod
    def remove_stored_credentials(cls) -> None:
        """Remove stored credentials from system keyring."""
        logger = get_colorized_logger()
        try:
            keyring.delete_password(SpotifyCredentialsManager.SERVICE_NAME, "client_id")
            keyring.delete_password(SpotifyCredentialsManager.SERVICE_NAME, "client_secret")
            logger.info("<green>Credentials removed successfully!</green>")
        except keyring.errors.PasswordDeleteError:
            logger.info("<yellow>No credentials found to remove.</yellow>")

    @classmethod
    def ensure_spotify_credentials(cls) -> SpotifyCredentials:
        """Ensure Spotify credentials are available in keyring."""
        logger = get_colorized_logger()

        credentials = SpotifyCredentialsManager.get_credentials()
        if credentials.client_id and credentials.client_secret:
            return credentials

        logger.info(
            "\n<yellow>Spotify API credentials not found. Let's set them up!</yellow>"
        )
        credentials = SpotifyCredentialsManager.prompt_and_store_credentials()

        if credentials.client_id and credentials.client_secret:
            logger.info("<green>✓ Spotify API credentials set up successfully!</green>")
            return credentials
        else:
            logger.error("<red>Failed to set up Spotify API credentials.</red>")
            exit(1)


def _fetch_paginated_tracks(
    sp_client: spotipy.Spotify,
    initial_results: SpotifyPlaylistTracksResponse,
    max_retries: int = 3,
    retry_delay: float = 2.0,
) -> dict:
    """Helper function to handle paginated track fetching from Spotify API.

    Args:
        sp_client: Authenticated Spotify client
        initial_results: First page of results from API
        max_retries: Maximum number of retry attempts for failed requests
        retry_delay: Delay in seconds between retries

    Returns:
        Dictionary of track_id -> track_item
    """
    logger = get_colorized_logger()
    tracks_dict = {}
    total_tracks_fetched = 0
    results = initial_results
    skipped_tracks = []

    while True:
        result_items: list[SpotifyPlaylistTrackItem] = results["items"]
        total_tracks_fetched += len(result_items)
        logger.info(
            f"<green>Fetched</green> {total_tracks_fetched} / {results['total']} <green>tracks</green>"
        )

        for item in result_items:
            track = item["track"]
            if track is None:
                skipped_tracks.append(item)
                continue
            tracks_dict[track["id"]] = item

        if results["next"]:
            time.sleep(API_REQUEST_SLEEP_TIME_SEC)

            # Add retry logic for the next() call
            for attempt in range(max_retries):
                try:
                    results = sp_client.next(results)
                    break
                except requests.exceptions.ReadTimeout:
                    if attempt == max_retries - 1:
                        logger.exception(
                            f"<red>Failed to fetch tracks after {max_retries} attempts due to timeout</red>"
                        )
                        logger.warning(
                            f"<yellow>Successfully fetched {total_tracks_fetched} tracks before error. Continuing...</yellow>"
                        )
                        return tracks_dict

                    wait_time = retry_delay * (attempt + 1)
                    logger.info(
                        f"<yellow>Request timed out. Retrying in {wait_time} seconds... (Attempt {attempt + 1}/{max_retries})</yellow>"
                    )
                    time.sleep(wait_time)
        else:
            break

    if skipped_tracks:
        logger.info(f"<red>Skipped</red> {len(skipped_tracks)} tracks")
        for track in skipped_tracks:
            logger.info(f"<red>  • {track}</red>")
    return tracks_dict


def get_liked_songs(sp_client: spotipy.Spotify) -> dict:
    logger = get_colorized_logger()
    logger.info("<blue>Getting liked songs</blue>...")
    initial_results = sp_client.current_user_saved_tracks(API_REQUEST_LIMIT)
    liked_songs = _fetch_paginated_tracks(sp_client, initial_results)
    return liked_songs


def get_tracks_from_playlist(
    sp_client: spotipy.Spotify,
    playlist: SpotifyPlaylist,
) -> dict:
    logger = get_colorized_logger()
    logger.info(
        f"<blue>Backing up playlist:</blue> <yellow><bold>{playlist['name']}</bold></yellow>"
    )
    initial_results = sp_client.playlist_tracks(
        playlist_id=playlist["id"],
        fields="items(added_at,added_by(id),track(name,id,artists(name),album(name,id))),next,total",
        limit=API_REQUEST_LIMIT,
    )
    return _fetch_paginated_tracks(sp_client, initial_results)


def get_saved_albums(sp_client: spotipy.Spotify) -> dict:
    logger = get_colorized_logger()
    saved_albums = {}
    results = sp_client.current_user_saved_albums(API_REQUEST_LIMIT)

    while True:
        result_items = results["items"]
        logger.info(f"<green>Fetched</green> {len(result_items)} <green>albums</green>")

        for item in result_items:
            saved_albums[item["album"]["id"]] = item

        if results["next"]:
            time.sleep(API_REQUEST_SLEEP_TIME_SEC)
            results = sp_client.next(results)
        else:
            break

    return saved_albums


def get_playlists(sp_client: spotipy.Spotify) -> dict[str, SpotifyPlaylist]:
    logger = get_colorized_logger()
    saved_playlists = {}
    results: SpotifyPlaylistsResponse = sp_client.current_user_playlists(
        API_REQUEST_LIMIT
    )

    logger.info(
        f"<green>Fetching</green> {results['total']} <green>playlists</green>..."
    )

    while True:
        playlists: list[SpotifyPlaylist] = results["items"]
        logger.info(f"<green>Fetched</green> {len(playlists)} playlists")

        for playlist in playlists:
            saved_playlists[playlist["id"]] = playlist

        if results["next"]:
            time.sleep(API_REQUEST_SLEEP_TIME_SEC)
            results = sp_client.next(results)
        else:
            break

    return saved_playlists


def get_username(sp_client: spotipy.Spotify) -> str:
    return sp_client.current_user()["display_name"]


def create_spotify_client() -> spotipy.Spotify:
    """Create and return an authenticated Spotify client.

    Raises:
        InvalidSpotifyCredentialsError: If the provided credentials are invalid
    """
    logger = get_colorized_logger()
    logger.info("<blue>Creating Spotify client...</blue>")

    creds = SpotifyCredentialsManager.get_credentials()

    base_cache_path = Path(getenv("XDG_CACHE_HOME", Path.home() / ".cache"))
    cache_path = base_cache_path / "spotify-backup" / ".auth_cache"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_handler = spotipy.cache_handler.CacheFileHandler(cache_path=str(cache_path))

    try:
        client = spotipy.Spotify(
            auth_manager=spotipy.oauth2.SpotifyOAuth(
                client_id=creds.client_id,
                client_secret=creds.client_secret,
                redirect_uri="http://localhost:8000/callback",
                cache_handler=cache_handler,
                scope=[
                    "user-library-read",
                    "playlist-read-private",
                    "playlist-read-collaborative",
                ],
            )
        )
    except Exception as e:
        raise InvalidSpotifyCredentialsError(f"Invalid credentials: {e}")

    # Spotipy does not set the permissions on the cache file correctly, so we do it manually
    # I filed https://github.com/spotipy-dev/spotipy/security/advisories/GHSA-pwhh-q4h6-w599
    chmod(cache_path, 0o600)
    logger.info("<green>Successfully created Spotify client!</green>")
    return client


#####
# Wrappers for use in main
#####


def get_playlist_file_name(playlist: SpotifyPlaylist | DeletedPlaylist) -> Path:
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
    output_manager = SpotifySnapshotOutputManager.get_instance()
    return output_manager.playlists_dir_path / Path(
        f"{escaped_playlist_name} ({playlist_id}).tsv"
    )


def write_liked_songs_to_git_repo(sp_client: spotipy.Spotify) -> None:
    logger = get_colorized_logger()
    liked_songs = get_liked_songs(sp_client)
    output_manager = SpotifySnapshotOutputManager.get_instance()
    dest_file = output_manager.liked_songs_path
    outputfileutils.write_to_file(
        data=liked_songs,
        sort_lambda=lambda item: (item["added_at"], item["track"]["name"]),
        header_row=outputfileutils.TRACK_HEADER_ROW,
        item_to_row_lambda=outputfileutils.track_to_row,
        output_filename=dest_file,
    )
    logger.info(
        f"<green>Wrote</green> {len(liked_songs)} <green>liked songs to</green> {dest_file}"
    )


def write_saved_albums_to_git_repo(sp_client: spotipy.Spotify) -> None:
    logger = get_colorized_logger()
    saved_albums = get_saved_albums(sp_client)
    output_manager = SpotifySnapshotOutputManager.get_instance()
    dest_file = output_manager.albums_path
    outputfileutils.write_to_file(
        data=saved_albums,
        sort_lambda=lambda item: (item["added_at"], item["album"]["name"]),
        header_row=outputfileutils.ALBUM_HEADER_ROW,
        item_to_row_lambda=outputfileutils.album_to_row,
        output_filename=dest_file,
    )
    logger.info(
        f"<green>Wrote</green> {len(saved_albums)} <green>albums to</green> {dest_file}"
    )


def write_playlists_to_git_repo(sp_client: spotipy.Spotify) -> None:
    """
    Extracts a list of all playlists the user owns or is subscribed to, and writes them to a file. Then, for each playlist,
    it fetches all the tracks on the playlist and writes them to a separate file.
    """
    logger = get_colorized_logger()
    playlists = get_playlists(sp_client)
    output_manager = SpotifySnapshotOutputManager.get_instance()
    playlists_file = output_manager.playlists_index_path
    outputfileutils.write_to_file(
        data=playlists,
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
        playlist_tracks_file = get_playlist_file_name(playlist)
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
        logger.info(
            f"<yellow>Skipped {len(skipped_playlists)} empty playlists:</yellow>"
        )
        for playlist_name in sorted(skipped_playlists):
            logger.info(f"<red>  • {playlist_name}</red>")

    logger.info(
        f"<green>Successfully backed up</green> {total_playlists_backed_up} playlists"
    )
