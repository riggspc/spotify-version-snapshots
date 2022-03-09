import git
from datetime import datetime

from git import NoSuchPathError, Commit
from main import TEST_MODE

if TEST_MODE:
    SNAPSHOTS_REPO_NAME = "TEST-REPO"
else:
    SNAPSHOTS_REPO_NAME = "spotify-snapshots-repo"


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
    # A temp commit is needed to get stats etc - the library doesn't support it
    # otherwise
    commit = repo.index.commit("temp")
    commit_message = get_commit_message_for_amending(commit)
    repo.git.commit("--amend", "-m", commit_message)


def get_commit_message_for_amending(commit: Commit) -> str:
    is_first_commit = len(commit.parents) == 0
    if is_first_commit:
        commit_title = "Initial Spotify Snapshot"
    else:
        commit_title = (
            f'Spotify Snapshot - {datetime.now().strftime("%m/%d/%Y, %H:%M:%S")}'
        )
    stats = commit.stats
    playlist_additions = 0
    playlist_removals = 0
    for changed_file in stats.files:
        if changed_file in {"playlists.tsv", "saved_albums.tsv", "saved_tracks.tsv"}:
            continue
        playlist_additions += stats.files[changed_file]["insertions"]
        playlist_removals += stats.files[changed_file]["deletions"]
    commit_details = []
    if "saved_tracks.tsv" in stats.files:
        track_stats = stats.files["saved_tracks.tsv"]
        if is_first_commit:
            # Subtract 1 to not count the first line (eg. the header in the TSV)
            commit_details.append(f"Tracks In Library: {track_stats['insertions'] - 1}")
        else:
            commit_details.extend(
                [
                    f"Added Tracks: {track_stats['insertions']}",
                    f"Removed Tracks: {track_stats['deletions']}",
                ]
            )
    if "saved_albums.tsv" in stats.files:
        album_stats = stats.files["saved_albums.tsv"]
        if is_first_commit:
            # Subtract 1 to not count the first line (eg. the header in the TSV)
            commit_details.append(f"Albums In Library: {album_stats['insertions'] - 1}")
        else:
            commit_details.extend(
                [
                    f"Added Albums: {album_stats['insertions']}",
                    f"Removed Albums: {album_stats['deletions']}",
                ]
            )
    if "playlists.tsv" in stats.files:
        playlist_stats = stats.files["playlists.tsv"]
        if is_first_commit:
            # Subtract 1 to not count the first line (eg. the header in the TSV)
            commit_details.append(
                f"Playlists In Library: {playlist_stats['insertions'] - 1}"
            )
        else:
            commit_details.extend(
                [
                    f"Added Playlists: {playlist_stats['insertions']}",
                    f"Removed Playlists: {playlist_stats['deletions']}",
                ]
            )
    if is_first_commit:
        num_playlists = 0
        # This file should always exist in the first commit, but just be safe
        if stats.files["playlists.tsv"]:
            # Subtract 1 to not count the first line (eg. the header in the TSV)
            num_playlists = stats.files["playlists.tsv"]["insertions"] - 1
        commit_details.append(
            f"Tracks Across All Playlists {playlist_additions - num_playlists}"
        )
    else:
        commit_details.extend(
            [
                f"Total Additions Across Playlists: {playlist_additions}",
                f"Total Removals Across Playlists: {playlist_removals}",
            ]
        )

    commit_message_body = "\n".join(commit_details)

    return "\n\n".join([commit_title, commit_message_body])
