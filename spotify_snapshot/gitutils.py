import git
from datetime import datetime
from rich import print as rprint
import os
from git import NoSuchPathError, Commit
from pathlib import Path
from spotify_snapshot import spotify
from spotify_snapshot.spotify_snapshot_output_manager import (
    SpotifySnapshotOutputManager,
)


def get_repo_name(is_test_mode: bool) -> Path:
    if is_test_mode:
        return Path("/tmp/SPOTIFY-VERSION-SNAPSHOTS-TEST-REPO")
    else:
        return Path("spotify-snapshots-repo")


def setup_git_repo_if_needed(is_test_mode) -> None:
    repo_name = get_repo_name(is_test_mode)
    try:
        git.Repo(repo_name)
        rprint(
            f"[yellow]Found existing repo at[/yellow] [green][bold]{repo_name}[/bold][/green]"
        )
    except NoSuchPathError as e:
        rprint(
            f"[yellow]No repo found, making a new one at[/yellow] [green][bold]{repo_name}[/bold][/green]"
        )
        git.Repo.init(repo_name)


# Requires that setup_git_repo_if_needed has already been called
def commit_files(is_test_mode) -> None:
    repo = git.Repo(get_repo_name(is_test_mode))

    is_first_commit = False
    try:
        repo.head.commit
    except ValueError:
        is_first_commit = True

    deleted_playlists = []
    if not is_first_commit:
        deleted_playlists = remove_deleted_playlists(repo, is_test_mode)

    # Check if there are any changes to commit
    if not repo.is_dirty(untracked_files=True):
        rprint("[yellow]No changes to commit[/yellow]")
        return

    repo.git.add(A=True)
    # A temp commit is needed to get stats etc - the library doesn't support it
    # otherwise
    commit = repo.index.commit("temp")
    commit_message = get_commit_message_for_amending(repo, commit, deleted_playlists)
    rprint(
        f"[green]Commit info:[/green]\n\n[yellow][bold]{commit_message}[/bold][/yellow]"
    )
    repo.git.commit("--amend", "-m", commit_message)
    rprint("[green]Changes committed. All done![/green]")


def get_deleted_playlists(
    repo: git.Repo, is_test_mode: bool
) -> list[spotify.DeletedPlaylist]:
    """
    Returns a list of playlists that were deleted in the working directory changes
    """
    output_manager = SpotifySnapshotOutputManager.get_instance()

    # Get the working directory changes for the playlists file
    deleted_lines = []
    diff = repo.head.commit.diff(None)
    for diff_item in diff:
        # Convert both paths to strings for comparison
        if output_manager.playlists_index_filename in diff_item.a_path:
            # Read the old version of the file from the last commit
            old_content = (
                diff_item.a_blob.data_stream.read().decode("utf-8").splitlines()
            )
            # Read the current version from the working directory
            with open(output_manager.playlists_index_path, "r", encoding="utf-8") as f:
                new_content = f.read().splitlines()

            # TODO: Handle the case where the new version has no playlists

            # Find lines that were in the old content but not in the new content
            deleted_lines = [line for line in old_content if line not in new_content]
            rprint(f"\n[red]Found {len(deleted_lines)} deleted playlists[/red]")

    # Get the playlists that were deleted
    deleted_playlists = []
    for deleted_playlist in deleted_lines:
        if not deleted_playlist.strip():  # Skip empty lines
            continue
        # Get the playlist name from the first column
        playlist_name = deleted_playlist.split("\t")[0]
        # Get the playlist ID from the last column
        playlist_id = deleted_playlist.split("\t")[-1]
        deleted_playlists.append(
            spotify.DeletedPlaylist(name=playlist_name, id=playlist_id)
        )
    return deleted_playlists


def remove_deleted_playlists(
    repo: git.Repo, is_test_mode: bool
) -> list[spotify.DeletedPlaylist]:
    """
    Removes the playlists that were deleted in the staged changes
    Returns: List of deleted playlists
    """
    try:
        repo.head.commit  # Check if there are any commits
    except ValueError:  # No commits yet
        rprint("[yellow]First commit detected. No playlists to delete.[/yellow]")
        return []

    deleted_playlists = get_deleted_playlists(repo, is_test_mode)
    for playlist in deleted_playlists:
        file_path_to_remove = spotify.get_playlist_file_name(
            get_repo_name(is_test_mode), playlist
        )
        rprint(f"[red]Deleting [bold]{file_path_to_remove}[/bold][/red]")
        os.remove(file_path_to_remove)
    return deleted_playlists


def get_commit_message_for_amending(
    repo: git.Repo, commit: Commit, deleted_playlists: list[spotify.DeletedPlaylist]
) -> str:
    """
    Generate a contextually appropriate commit message (depending on whether this is the first commit or not)
    If it is the first commit, the git commit is a status report on how many playlists were backed up, how many tracks per playlist, and how many liked songs were backed up
    For all commits after, the git commit is a status report on how many playlists were added, removed, and how many tracks were added, removed
    """
    output_manager = SpotifySnapshotOutputManager.get_instance()
    is_first_commit = len(commit.parents) == 0
    current_time = datetime.now().strftime("%m/%d/%Y, %H:%M:%S")
    if is_first_commit:
        commit_title = f"Initial Spotify Snapshot - {current_time}"
    else:
        commit_title = f"Spotify Snapshot - {current_time}"
    stats = commit.stats
    playlist_stats = {}
    liked_songs_add_remove_stats = None

    # Process playlist files and liked songs
    for changed_file in stats.files:
        # print(f"changed_file: {changed_file}")
        if (output_manager.liked_songs_filename) != changed_file:
            continue

        file_stats = stats.files[changed_file]
        if is_first_commit:
            liked_songs_add_remove_stats = (
                file_stats["insertions"] - 1
            )  # Subtract header
        else:
            liked_songs_add_remove_stats = {
                "added": file_stats["insertions"],
                "removed": file_stats["deletions"],
            }

        playlist_name = changed_file.split("/")[-1].replace(".tsv", "")
        if is_first_commit:
            playlist_stats[playlist_name] = (
                file_stats["insertions"] - 1
            )  # Subtract header
        else:
            playlist_stats[playlist_name] = {
                "added": file_stats["insertions"],
                "removed": file_stats["deletions"],
            }

    # If liked songs file is present, grab the count of tracks
    liked_songs_count = None
    liked_songs_file = output_manager.liked_songs_path
    if os.path.exists(liked_songs_file):
        with open(liked_songs_file, "r", encoding="utf-8") as f:
            liked_songs_count = len(f.readlines()) - 1

    commit_details = []
    # Always add Liked Songs section first if there is a liked songs file in the backup
    if liked_songs_add_remove_stats is not None:
        commit_details.append(f"Liked Songs        : {liked_songs_count} tracks")

        if not is_first_commit:
            commit_details.append(
                f"Liked Songs Changes: +{liked_songs_add_remove_stats['added']}, -{liked_songs_add_remove_stats['removed']}"
            )

    if is_first_commit:
        commit_details.append(f"Number of Playlists: {len(playlist_stats)}")
        commit_details.append("\nPlaylist Details:")
        for playlist, track_count in sorted(playlist_stats.items()):
            commit_details.append(f"- {playlist}: {track_count} tracks")
    else:
        # Add detection of renamed playlists
        renamed_playlists = []
        renamed_playlist_ids = set()  # Track IDs of renamed playlists

        # Compare with parent commit to get changes
        for diff_item in commit.diff(commit.parents[0] if commit.parents else None):
            if diff_item.renamed_file and diff_item.a_path.startswith("playlists/"):
                old_name = diff_item.a_path.split("/")[-1].split(" (")[0]
                new_name = diff_item.b_path.split("/")[-1].split(" (")[0]
                # Extract playlist ID from the filename
                playlist_id = diff_item.a_path.split("(")[-1].rstrip(").tsv")
                renamed_playlists.append((old_name, new_name))
                renamed_playlist_ids.add(playlist_id)

        # Filter out renamed playlists from deleted_playlists
        filtered_deleted_playlists = [
            playlist
            for playlist in deleted_playlists
            if playlist.id not in renamed_playlist_ids
        ]

        # Compare with parent commit to get changes
        created_playlists = []
        for diff_item in commit.diff(commit.parents[0] if commit.parents else None):
            if (
                not diff_item.renamed_file
                and diff_item.new_file
                and diff_item.b_path.startswith("playlists/")
            ):
                playlist_name = diff_item.b_path.split("/")[-1].split(" (")[0]
                created_playlists.append(playlist_name)

        if created_playlists:
            commit_details.append("\nCreated Playlists:")
            for playlist in created_playlists:
                commit_details.append(f"- {playlist}")

        if filtered_deleted_playlists:
            commit_details.append("\nDeleted Playlists:")
            for playlist in filtered_deleted_playlists:
                commit_details.append(f"- {playlist.name}")

        if renamed_playlists:
            commit_details.append("\nRenamed Playlists:")
            for old_name, new_name in renamed_playlists:
                commit_details.append(f"- {old_name} → {new_name}")

        commit_details.append("\nChanged Playlists:")
        has_changes = False
        for playlist, changes in sorted(playlist_stats.items()):
            if changes["added"] > 0 or changes["removed"] > 0:
                has_changes = True
                commit_details.append(
                    f"- {playlist}: +{changes['added']} -{changes['removed']}"
                )
        if not has_changes:
            commit_details.pop()

    commit_message_body = "\n".join(commit_details)
    return "\n\n".join([commit_title, commit_message_body])
