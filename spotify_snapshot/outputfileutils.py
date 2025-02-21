import csv
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

from rich.console import Console
from rich.table import Table

from spotify_snapshot.logging import get_colorized_logger
from spotify_snapshot.spotify_datatypes import (
    SpotifyAlbum,
    SpotifyPlaylist,
    SpotifyPlaylistTrackItem,
)

TRACK_HEADER_ROW = ["TRACK NAME", "TRACK ARTIST(S)", "ALBUM", "DATE ADDED", "TRACK ID"]
ALBUM_HEADER_ROW = ["ALBUM NAME", "ALBUM ARTIST(S)", "DATE ADDED", "ALBUM ID"]
PLAYLIST_HEADER_ROW = [
    "PLAYLIST NAME",
    "PLAYLIST DESCRIPTION",
    "LENGTH",
    "OWNER",
    "COLLABORATIVE",
    "PLAYLIST ID",
]
TRACK_IN_PLAYLIST_HEADER_ROW = [
    *TRACK_HEADER_ROW[:-1],
    "ADDED BY",
    *TRACK_HEADER_ROW[-1:],
]

T = TypeVar('T')

def write_to_file(
    data: dict[str, T],
    sort_lambda: Callable[[T], Any],
    item_to_row_lambda: Callable[[T], list[str]],
    header_row: list[str],
    output_filename: Path,
) -> None:
    """
    Takes in a dict of dicts (data), sorts into a list based on sort_key for each
    dict, and then outputs each item to the file specified. Overwrites any such
    existing file. Will create directories if needed.
    """
    logger = get_colorized_logger()
    logger.info(
        f"<blue>Writing to</blue> <green><bold>{output_filename}</bold></green>"
    )

    sorted_list = sorted(data.values(), key=sort_lambda)
    output_rows = [header_row]
    output_rows.extend([item_to_row_lambda(item) for item in sorted_list])

    with open(output_filename, "w") as out_file:
        tsv_writer = csv.writer(out_file, delimiter="\t")
        tsv_writer.writerows(output_rows)


def track_to_row(item: SpotifyPlaylistTrackItem) -> list[str]:
    track_obj = item["track"]
    return [
        track_obj["name"],
        ", ".join(artist["name"] for artist in track_obj["artists"]),
        track_obj["album"]["name"],
        item["added_at"],
        track_obj["id"],
    ]


def playlist_track_to_row(item: SpotifyPlaylistTrackItem) -> list[str]:
    track_row = track_to_row(item)
    added_by_id = item["added_by"]["id"]
    if added_by_id == "":
        # This has come up in debugging with Spotify owned ("official") playlists,
        # presumably because they're built different than "regular" playlists
        added_by_id = "<unknown>"
    return [*track_row[:-1], added_by_id, *track_row[-1:]]


def album_to_row(item: dict[str, str | SpotifyAlbum]) -> list[str]:
    album_obj = item["album"]
    return [
        album_obj["name"],
        ", ".join(map(lambda artist: artist["name"], album_obj["artists"])),
        item["added_at"],
        album_obj["id"],
    ]


def playlist_to_row(item: SpotifyPlaylist) -> list[str]:
    return [
        item["name"],
        item["description"],
        item["tracks"]["total"],
        item["owner"]["id"],
        item["collaborative"],
        item["id"],
    ]


def pretty_print_tsv_table(tsv_data_path: Path) -> None:
    with open(tsv_data_path) as tsv_file:
        tsv_data = [line.strip().split("\t") for line in tsv_file.readlines()]
    table = Table(show_header=True, header_style="bold magenta")
    for header in tsv_data[0]:
        table.add_column(header)
    for row in tsv_data[1:]:
        table.add_row(*row)
    console = Console()
    console.print(table)
