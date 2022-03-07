import csv
import os

from typing import Callable

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

# Takes in a dict of dicts (data), sorts into a list based on sort_key for each
# dict, and then outputs each item to the file specified. Overwrites any such
# existing file. Will create directories if needed.
# TODO: something in this function is breaking for playlists that have slashes
# in the name
def write_to_file(
    data: dict,
    sort_lambda: Callable,
    item_to_row_lambda: Callable,
    header_row: list[str],
    output_filename: str,
) -> None:
    # Make sure the dirs in the filepath exist, create if needed
    os.makedirs(os.path.dirname(output_filename), exist_ok=True)

    sorted_list = sorted(list(data.values()), key=sort_lambda)
    output_rows = [header_row]
    for item in sorted_list:
        output_rows.append(item_to_row_lambda(item))

    with open(output_filename, "wt") as out_file:
        tsv_writer = csv.writer(out_file, delimiter="\t")
        tsv_writer.writerows(output_rows)


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


def playlist_to_row(item) -> list:
    return [
        item["name"],
        item["description"],
        item["tracks"]["total"],
        item["owner"]["id"],
        item["collaborative"],
        item["id"],
    ]
