import os
from datetime import datetime, timezone
from pathlib import Path
from sys import exit

import git
from git import Commit, NoSuchPathError
from rich.prompt import Prompt

from spotify_snapshot import spotify
from spotify_snapshot.spotify import DeletedPlaylist
from spotify_snapshot.spotify_datatypes import DeletedPlaylist
from spotify_snapshot.spotify_snapshot_output_manager import (
    SpotifySnapshotOutputManager,
)

from .config import SpotifySnapshotConfig
from .logging import get_colorized_logger

_repo_instance = None


def get_repo_filepath(is_test_mode: bool) -> Path:
    if is_test_mode:
        return Path("/tmp/SPOTIFY-VERSION-SNAPSHOTS-TEST-REPO")
    config = SpotifySnapshotConfig.load()
    if config.backup_dir is None:
        raise ValueError("Backup directory not set. This should not be possible.")
    return config.backup_dir


def get_repo(is_test_mode: bool = False) -> git.Repo:
    """Get or create a singleton instance of the git repository.

    Args:
        is_test_mode: Whether to use test repository path

    Returns:
        git.Repo: Repository instance
    """
    global _repo_instance
    if _repo_instance is None:
        _repo_instance = git.Repo(get_repo_filepath(is_test_mode))
    return _repo_instance


def create_readme_if_missing(repo_filepath: Path) -> None:
    """Create a README.md file if it doesn't exist in the repository.

    Args:
        repo_filepath: Path to the git repository
    """
    logger = get_colorized_logger()
    readme_path = repo_filepath / "README.md"
    if not readme_path.exists():
        logger.info("Creating README.md file")
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(
                """# Spotify Playlist Backup

This repository contains automated backups of your Spotify playlists and liked songs, created using [spotify-snapshot](https://github.com/alichtman/spotify-snapshot).

Each playlist is stored as a TSV (Tab Separated Values) file in the `playlists` directory, and liked songs are stored in `liked_songs.tsv`.

See the [README](https://github.com/alichtman/spotify-snapshot/blob/main/README.md) for more information."""
            )
        logger.info("Created README.md file")


def setup_git_repo_if_needed(is_test_mode) -> Path:
    repo_filepath = get_repo_filepath(is_test_mode)
    logger = get_colorized_logger()
    config = SpotifySnapshotConfig.load()

    try:
        # First check if the directory exists and is a git repo
        if os.path.exists(repo_filepath) and os.path.exists(repo_filepath / ".git"):
            repo = git.Repo(repo_filepath)
            logger.info(
                f"<yellow>Found existing repo at</yellow> <green><bold>{repo_filepath}</bold></green>"
            )
            create_readme_if_missing(repo_filepath)
        else:
            raise NoSuchPathError

    except (NoSuchPathError, git.InvalidGitRepositoryError):
        if config.git_remote_url:
            try:
                logger.info(
                    f"Cloning repo from <blue>{config.git_remote_url}</blue> to <green>{str(repo_filepath).strip()}</green>"
                )
                repo = git.Repo.clone_from(config.git_remote_url, repo_filepath)
                # Set up the remote properly after cloning
                if "origin" in [remote.name for remote in repo.remotes]:
                    repo.delete_remote(repo.remote("origin"))
                repo.create_remote("origin", config.git_remote_url)
            except git.GitCommandError:
                # If clone fails (e.g., empty remote), check if directory exists and is empty
                if os.path.exists(repo_filepath) and os.listdir(repo_filepath):
                    error_msg = f"Cannot create repository: Directory {repo_filepath} already exists and is not empty. You will need to manually delete it or move it to a different location."
                    logger.error(f"<red>{error_msg}</red>")
                    raise ValueError(error_msg)

                logger.info(
                    f"<yellow>Remote repo is empty. Creating new local repo at</yellow> <green><bold>{repo_filepath}</bold></green>"
                )
                os.makedirs(repo_filepath, exist_ok=True)
                git.Repo.init(repo_filepath)
        else:
            logger.info(
                f"<yellow>No repo found, making a new one at</yellow> <green><bold>{repo_filepath}</bold></green>"
            )
            os.makedirs(repo_filepath, exist_ok=True)
            git.Repo.init(repo_filepath)

    create_readme_if_missing(repo_filepath)
    return repo_filepath


def cleanup_repo() -> None:
    """Clean up the git repository instance."""
    if _repo_instance is not None:
        _repo_instance.close()


def commit_files(is_test_mode: bool, username: str) -> bool:
    """Commit the files in the repository.

    Returns:
        True if the commit was successful, False if there were no changes to commit
    """
    logger = get_colorized_logger()
    repo = get_repo(is_test_mode)

    is_first_commit = False
    try:
        repo.head.commit
    except ValueError:
        is_first_commit = True

    deleted_playlists = []
    if not is_first_commit:
        deleted_playlists = remove_deleted_playlists(repo)

    # Add all changes to the index first
    repo.git.add(A=True)
    
    # Check if there are any changes to commit after staging
    if not repo.index.diff("HEAD") and not repo.untracked_files:
        logger.info("<yellow>No changes to commit</yellow>")
        return False

    # A temp commit is needed to get stats etc - the library doesn't support it
    # otherwise
    commit = repo.index.commit("temp")
    commit_message = get_commit_message_for_amending(
        commit, deleted_playlists, username
    )
    logger.info(
        f"<green>Commit info:</green>\n\n<yellow><bold>{commit_message}</bold></yellow>"
    )
    repo.git.commit("--amend", "-m", commit_message)
    logger.info("<green>Changes committed. All done!</green>")
    return True

def get_deleted_playlists(
    repo: git.Repo,
) -> list[DeletedPlaylist]:
    """
    Returns a list of playlists that were deleted in the working directory changes
    """
    logger = get_colorized_logger()
    output_manager = SpotifySnapshotOutputManager.get_instance()

    # Get the working directory changes for the playlists file
    deleted_lines = []
    diff = repo.head.commit.diff(None)
    for diff_item in diff:
        # Convert both paths to strings for comparison
        if (
            diff_item.a_path is not None
            and output_manager.playlists_index_filename in diff_item.a_path
        ):
            # Read the old version of the file from the last commit
            if diff_item.a_blob is not None:
                old_content = (
                    diff_item.a_blob.data_stream.read().decode("utf-8").splitlines()
                )
            # Read the current version from the working directory
            with open(output_manager.playlists_index_path, encoding="utf-8") as f:
                new_content = f.read().splitlines()

            # Extract playlist IDs from both old and new content
            old_playlist_ids = {
                line.split("\t")[-1] for line in old_content if line.strip()
            }
            new_playlist_ids = {
                line.split("\t")[-1] for line in new_content if line.strip()
            }

            # Find playlists that were actually deleted (present in old but not in new)
            deleted_playlist_ids = old_playlist_ids - new_playlist_ids

            # Get the full playlist info for deleted playlists
            deleted_lines = [
                line
                for line in old_content
                if line.strip() and line.split("\t")[-1] in deleted_playlist_ids
            ]
            logger.info(f"\n<red>Found {len(deleted_lines)} deleted playlists</red>")

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
    repo: git.Repo,
) -> list[DeletedPlaylist]:
    """
    Removes the playlists that were deleted in the staged changes
    Returns: List of deleted playlists
    """
    logger = get_colorized_logger()
    try:
        _ = repo.head.commit  # Check if there are any commits
    except ValueError:  # No commits yet
        logger.info("<yellow>First commit detected. No playlists to delete.</yellow>")
        return []

    deleted_playlists = get_deleted_playlists(repo)
    for playlist in deleted_playlists:
        file_path_to_remove = spotify.get_playlist_file_name(playlist)
        logger.info(f"<red>Deleting <bold>{file_path_to_remove}</bold></red>")
        os.remove(file_path_to_remove)
    return deleted_playlists


# TODO: This method desperately needs some refactoring
def get_commit_message_for_amending(
    commit: Commit, deleted_playlists: list[DeletedPlaylist], username: str
) -> str:
    """
    Generate a contextually appropriate commit message (depending on whether this is the first commit or not)
    If it is the first commit, the git commit is a status report on how many playlists were backed up, how many tracks per playlist, and how many liked songs were backed up
    For all commits after, the git commit is a status report on how many playlists were added, removed, and how many tracks were added, removed
    """
    output_manager = SpotifySnapshotOutputManager.get_instance()
    is_first_commit = len(commit.parents) == 0
    current_time = datetime.now(tz=timezone.utc).strftime("%m/%d/%Y, %H:%M:%S %Z")
    if is_first_commit:
        commit_title = f"Initial Spotify Snapshot - {username} - {current_time}"
    else:
        commit_title = f"Spotify Snapshot - {username} - {current_time}"
    stats = commit.stats
    playlist_stats: dict[str, int | dict[str, int]] = {}
    liked_songs_add_remove_stats: int | dict[str, int] | None = None

    # Process playlist files and liked songs
    for changed_file in stats.files:
        file_stats = stats.files[changed_file]

        # Handle liked songs file
        if str(output_manager.liked_songs_filename) == str(changed_file):
            if is_first_commit:
                liked_songs_add_remove_stats = (
                    file_stats["insertions"] - 1
                )  # Subtract header
            else:
                liked_songs_add_remove_stats = {
                    "added": file_stats["insertions"],
                    "removed": file_stats["deletions"],
                }
            continue

        # Handle playlist files
        if changed_file.startswith("playlists/"):
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
        with open(liked_songs_file, encoding="utf-8") as f:
            liked_songs_count = len(f.readlines()) - 1

    commit_details = []
    # Always add Liked Songs section first if there is a liked songs file in the backup
    if liked_songs_add_remove_stats is not None:
        commit_details.append(f"Liked Songs        : {liked_songs_count} tracks")

        if not is_first_commit:
            commit_details.append(
                f"Liked Songs Changes: +{liked_songs_add_remove_stats['added']}, -{liked_songs_add_remove_stats['removed']}"
            )

    commit_details.append(f"Number of Playlists Changed: {len(playlist_stats)}")

    if is_first_commit:
        commit_details.append("\nPlaylist Details:")
        for playlist, track_count in sorted(playlist_stats.items()):
            commit_details.append(f"- {playlist}: {track_count} tracks")
    else:
        # Add detection of renamed playlists
        renamed_playlists = []
        renamed_playlist_ids = set()  # Track IDs of renamed playlists

        # Compare with parent commit to get changes
        for diff_item in commit.diff(commit.parents[0] if commit.parents else None):
            if (
                diff_item.renamed_file
                and diff_item.a_path is not None
                and diff_item.b_path is not None
                and diff_item.a_path.startswith("playlists/")
            ):
                # Extract everything before the last parenthetical for both old and new names
                old_name = str(diff_item.a_path).split("/")[-1].rsplit(" (", 1)[0]
                new_name = str(diff_item.b_path).split("/")[-1].rsplit(" (", 1)[0]
                # Extract playlist ID from the filename
                playlist_id = str(diff_item.a_path).rsplit("(", 1)[-1].rstrip(").tsv")
                renamed_playlists.append((old_name, new_name))
                renamed_playlist_ids.add(playlist_id)

        # Filter out renamed playlists from deleted_playlists
        filtered_deleted_playlists = [
            playlist
            for playlist in deleted_playlists
            if playlist.id not in renamed_playlist_ids
        ]

        # Compare with parent commit to get changes
        # TODO: This method is kind of a mess. Good enough though
        created_playlists = []
        for diff_item in commit.diff(commit.parents[0] if commit.parents else None):
            if (
                diff_item.b_path is not None
                and diff_item.b_path.startswith("playlists/")
                and diff_item.new_file  # This is crucial - file must be new
                and not diff_item.renamed_file  # Not a rename
                and
                # Don't count a playlist as created if it's in the deleted_playlists list
                not any(
                    playlist.name in diff_item.b_path for playlist in deleted_playlists
                )
            ):
                # Extract playlist name without the ID
                playlist_name = diff_item.b_path.split("/")[-1].rsplit(" (", 1)[0]
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


def set_remote_url(remote_url: str, is_test_mode: bool) -> None:
    """Set the remote URL for the git repository."""
    repo = get_repo(is_test_mode)
    try:
        remote = repo.remote("origin")
        remote.set_url(remote_url)
    except ValueError:
        # Remote doesn't exist, create it
        repo.create_remote("origin", remote_url)


def maybe_git_push(
    is_test_mode: bool, should_push_without_prompting_user: bool = False
) -> None:
    """Push changes to the remote repository."""
    logger = get_colorized_logger()
    repo = get_repo(is_test_mode)
    config = SpotifySnapshotConfig.load()

    # Verify remote exists and has URL
    try:
        if not repo.remote("origin").urls:
            if should_push_without_prompting_user:
                logger.error("No remote URL configured. Skipping push.")
                exit(1)
            else:
                logger.warning("No remote URL configured. Skipping push.")
                return
    except ValueError:
        logger.warning("No remote configured. Skipping push.")
        return

    # Determine if we should push
    if should_push_without_prompting_user:
        logger.info("Pushing changes to remote (due to --push flag)...")
    else:
        if (
            Prompt.ask(
                "\nPush changes to remote repository?", choices=["y", "N"], default="N"
            )
            != "y"
        ):
            cleanup_repo()
            exit(1)

    try:
        logger.info("Pushing changes to remote...")
        if repo.head.is_detached:
            logger.error(
                "Cannot push: HEAD is in a detached state. Please checkout a branch first."
            )
            cleanup_repo()
            exit(1)

        if not repo.remotes.origin.url.startswith("git@"):
            logger.error(
                "Only SSH URLs are supported for pushing to remote repositories."
            )
            cleanup_repo()
            exit(1)
        
        # If there are unpulled changes, pull them first
        if repo.remotes.origin.fetch():
            logger.info("Pulling changes from remote...")
            try:
                repo.remotes.origin.pull()
            except git.GitCommandError as e:
                logger.error(f"Failed to pull changes: {e!s}")
                logger.error(f"Git command failed with exit code {e.status}")
                logger.error(f"Git stderr: {e.stderr}")
                cleanup_repo()
                exit(1)

        # Use SSH key 
        logger.info(f"Using SSH key at: {config.ssh_key_path}")
        ssh_key_path = Path(config.ssh_key_path).expanduser()
        if not ssh_key_path.exists():
            logger.error(f"SSH key does not exist where the config file says it should: {ssh_key_path}")
            cleanup_repo()
            exit(1)

        ssh_cmd = f"ssh -i {ssh_key_path}"
        with repo.git.custom_environment(GIT_SSH_COMMAND=ssh_cmd):
            repo.remotes.origin.push()

        # Convert SSH URL to HTTPS URL for display
        ssh_url = repo.remotes.origin.url
        # Convert git@github.com:user/repo.git to https://github.com/user/repo
        https_url = ssh_url.replace(":", "/").replace("git@", "https://").rstrip(".git")
        success_msg = f"Successfully pushed changes to {ssh_url}"
        success_msg = f"See your changes at {https_url}"
        logger.info(success_msg)
    except git.GitCommandError as e:
        error_msg = f"Failed to push changes: {e!s}"
        logger.error(error_msg)
        logger.error(f"Git command failed with exit code {e.status}")
        logger.error(f"Git stderr: {e.stderr}")
        # TODO: This can be a misleading error message if the repo does not exist maybe?
        if (
            "Permission denied (publickey)" in e.stderr
            or "Could not read from remote repository" in e.stderr
        ):
            logger.error(
                "SSH key authentication failed. Please check your SSH key configuration."
            )
            if config.ssh_key_path:
                logger.error(f"Using SSH key at: {config.ssh_key_path}")
        logger.error(f"[red]{error_msg}[/red]")
